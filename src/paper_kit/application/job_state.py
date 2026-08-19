"""任務狀態守門：轉換與持久化是同一個不可拆的動作（架構深化候選 4，2026-08-19）。

**為什麼存在**：先前 `JobService` 擁有那把 `_lock`，卻把**同一把鎖傳進**
`StartTranslation`，由後者負責終態轉換的原子性。於是「任務狀態何時被安全地寫回」
這個並行不變式，需要同時讀兩個 module 才看得完整——而缺口就出現在中間：

    job.transition(JobStatus.TRANSLATING)   # 只改了記憶體物件
    result = self._engine.translate(job)    # 沒有 save()

UI 的 `list_jobs()` 是從 repo 讀的，那一列整段翻譯期間都還是「排隊中」，直到終態
才被寫入（2026-08-19 使用者回報「翻譯時只顯示排隊中，結束才直接跳完成」）。
兩邊各自看起來都合理，缺口出現在中間——這是 locality 缺失的標準症狀。

**這個 module 的形狀**（grilling Q4／Q9 定案）：住在 application 層（不讓純領域
物件沾上 IO，也不把並行不變式藏進 infrastructure），而且**鎖完全內化、不外借**。
呼叫端只能說「這個任務現在要進入 X 狀態」，拿不到把轉換與持久化拆開的機會——
今天那個 bug 在這個 interface 下不可能被寫出來。

守門的範圍涵蓋四處原本各自用鎖的地方：狀態轉換、取消、刪除、進度寫入。
留一半在外面等於問題只解一半。
"""

import threading
import time

from paper_kit.application.ports import JobRepository
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class JobStateGate:
    """任務狀態的單一守門人。所有狀態寫入都經過這裡，鎖不外借。"""

    def __init__(self, jobs: JobRepository):
        self._jobs = jobs
        self._lock = threading.Lock()
        self._active: set[str] = set()  # 有 live worker 的任務（delete 的原子判定用）

    # ── 狀態轉換 ─────────────────────────────────────────

    def to(self, job: TranslationJob, status: JobStatus, **fields) -> None:
        """轉換到 status 並持久化——一個動作，不可拆。

        fields：隨轉換一起寫入的欄位（error／result…）。它們必須和狀態同時落地，
        否則 UI 會讀到「已失敗但沒有錯誤訊息」這種半套狀態。
        """
        with self._lock:
            job.transition(status)  # 非法轉換在此被領域狀態機拒絕
            for name, value in fields.items():
                setattr(job, name, value)
            self._jobs.save(job)

    def to_unless_cancelled(self, job: TranslationJob, status: JobStatus, **fields) -> bool:
        """若任務尚未被取消則轉換；已取消回 False 且不動它。

        票 08 的既有語意：取消後引擎才回報完成／失敗 → 產出拋棄、維持 cancelled。
        檢查與轉換必須在同一個鎖內，否則就是 check-then-act race——這正是原本
        `_finalize()` 存在的理由，只是那時鎖是借來的。
        """
        with self._lock:
            if job.status is JobStatus.CANCELLED:
                return False
            job.transition(status)
            for name, value in fields.items():
                setattr(job, name, value)
            self._jobs.save(job)
            return True

    def cancel(self, job: TranslationJob) -> None:
        """取消：狀態→cancelled 並持久化（僅 translating/queued→cancelled 合法）。"""
        self.to(job, JobStatus.CANCELLED)

    # ── 進度 ─────────────────────────────────────────────

    def progress_writer(self, job: TranslationJob):
        """#72：引擎進度回調 → 寫回 repo（throttle：值變動 ≥0.02 或 ≥2s 才存）。

        串流 runner 每行輸出都會觸發；逐行寫 SQLite 太重，值跳動也不值得——
        UI 1s 輪詢，這個節流綽綽有餘。
        """
        last = {"value": -1.0, "t": 0.0}

        def write(progress: float) -> None:
            now = time.monotonic()
            if progress is None or (
                abs(progress - last["value"]) < 0.02 and now - last["t"] < 2.0
            ):
                return
            with self._lock:
                job.progress = progress
                self._jobs.save(job)
            last["value"] = progress
            last["t"] = now

        return write

    # ── 生命週期（delete 的原子判定）───────────────────────

    def mark_active(self, job_id: str) -> None:
        """登記「這個任務有 live worker」——delete 要據此拒絕。

        必須在 spawn thread 時就登記，不能等狀態變成 TRANSLATING：start() 在
        QUEUED 就 spawn，那個窗口內任務也是動不得的（票 18 review 教訓）。
        """
        with self._lock:
            self._active.add(job_id)

    def mark_done(self, job_id: str) -> None:
        with self._lock:
            self._active.discard(job_id)

    def remove(self, job_id: str, job: TranslationJob) -> None:
        """票 18：刪除任務——執行中拒絕。判定與移除原子，對齊 cancel 的 race 修正。"""
        with self._lock:
            if job_id in self._active or job.status in (
                JobStatus.QUEUED,
                JobStatus.TRANSLATING,
            ):
                raise ValueError("執行中的任務不可刪除")
            self._jobs.remove(job_id)
