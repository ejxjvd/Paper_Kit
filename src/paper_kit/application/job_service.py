"""JobService（application）：上傳→輸出目錄、背景翻譯、狀態查詢。

UI 薄層只依賴 JobService；引擎換插頭＝換 engine 參數（Ports & Adapters）。
"""

import shutil
import threading
import uuid
from pathlib import Path

from paper_kit.application.ports import JobRepository, TranslationEnginePort
from paper_kit.application.start_translation import StartTranslation
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class JobService:
    """任務服務：建立（複製上傳檔進 outputs/<job_id>/）、背景執行、等待。"""

    def __init__(self, jobs: JobRepository, outputs_dir: str | Path):
        self._jobs = jobs
        self._outputs = Path(outputs_dir)
        self._threads: dict[str, threading.Thread] = {}
        self._engines: dict[str, TranslationEnginePort] = {}  # 票 08：cancel 要摸得到引擎
        self._lock = threading.Lock()  # 票 08：cancel vs worker 終態判定互斥（review 修正）
        # 票 08：重啟後從 repo 載入歷史（SQLite 才有記憶；InMemory 回傳空）
        self._order = [job.job_id for job in jobs.list()]
        self._reclaim_stuck_jobs(jobs)

    def create_job(
        self,
        upload_path: str | Path,
        target_lang: str = "zh-TW",
        pages: str | None = None,
        output_dir: str = "",
    ) -> TranslationJob:
        """把上傳檔複製進任務資料夾，建立 queued 任務。

        pages：頁面範圍（票 07，None=全部）；output_dir：完成後產出複製到的目錄
        （票 07，空白=留在預設 outputs/<job_id>/）。
        """
        job_id = uuid.uuid4().hex
        src = Path(upload_path)
        dest_dir = self._outputs / job_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        job = TranslationJob(
            job_id=job_id,
            source_path=str(dest),
            target_lang=target_lang,
            pages=pages,
            output_dir=output_dir,
        )
        self._jobs.add(job)
        self._order.append(job_id)
        return job

    def list_jobs(self) -> list[TranslationJob]:
        """任務列表（建立順序，UI 輪詢用）。"""
        return [self._jobs.get(job_id) for job_id in self._order if self._jobs.get(job_id)]

    def start(
        self, job_id: str, engine: TranslationEnginePort, engine_id: str | None = None
    ) -> None:
        """背景 thread 執行翻譯；立即回傳。engine_id 記在任務上（票 06 計價）。"""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        job.engine_id = engine_id
        self._engines[job_id] = engine
        thread = threading.Thread(target=self._run, args=(job, engine), daemon=True)
        thread.start()
        self._threads[job_id] = thread

    def retry(self, job_id: str, engine: TranslationEnginePort, engine_id: str | None = None) -> None:
        """票 08：失敗任務重試——回 queued 再跑一次（不需重新上傳）。

        engine_id 省略（spec review 防護）→ 沿用任務原本的引擎 id，
        不把 job.engine_id 覆寫成 None。
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        job.transition(JobStatus.QUEUED)  # 非 FAILED → InvalidTransition
        job.error = None
        self._jobs.save(job)
        self.start(job_id, engine, engine_id=engine_id if engine_id is not None else job.engine_id)

    def cancel(self, job_id: str) -> None:
        """票 08：進行中任務取消——狀態→cancelled、通知引擎中止、產出拋棄。"""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        with self._lock:  # 與 worker 的終態判定互斥（review 修正：check-then-act race）
            job.transition(JobStatus.CANCELLED)  # 僅 translating→cancelled 合法（領域狀態機）
            self._jobs.save(job)
        engine = self._engines.get(job_id)
        if engine is not None:
            engine.cancel()

    def wait(self, job_id: str, timeout: float = 10.0) -> None:
        """等待背景執行結束（測試／無頭執行用）。"""
        thread = self._threads.get(job_id)
        if thread is not None:
            thread.join(timeout)

    def _reclaim_stuck_jobs(self, jobs: JobRepository) -> None:
        """票 08 spec review：重啟時回收卡死的進行中任務（進度條永不結束、
        cancel 殺不到子程序）。翻譯程序隨 app 死亡 → 標 FAILED＋說明，使用者可重試。
        """
        for job in jobs.list():
            if job.status in (JobStatus.QUEUED, JobStatus.TRANSLATING):
                job.transition(JobStatus.FAILED)  # 領域：排隊/翻譯中可被系統中斷
                job.error = "應用重啟，翻譯中斷（請重試）"
                jobs.save(job)

    def _run(self, job: TranslationJob, engine: TranslationEnginePort) -> None:
        try:
            done = StartTranslation(
                engine=engine, jobs=self._jobs, lock=self._lock
            ).run(job)
            self._copy_outputs(done)
        finally:
            # 票 08 review：thread/engine 引用收尾清理（歷史任務無界增長）
            self._threads.pop(job.job_id, None)
            self._engines.pop(job.job_id, None)

    def _copy_outputs(self, job: TranslationJob) -> None:
        """票 07：完成的任務把 mono/dual 複製到設定的輸出目錄（空白=留在預設）。

        複製失敗（無權限、磁碟滿、目標是檔案）→ job.error 記錄，不讓
        daemon thread 靜默死亡（review 修正：失敗要有訊號）。
        """
        if job.status is not JobStatus.COMPLETED or not job.output_dir or not job.result:
            return
        dest = Path(job.output_dir)
        try:
            dest.mkdir(parents=True, exist_ok=True)
            for path in (job.result.mono_path, job.result.dual_path):
                if not path:
                    continue
                if Path(path).resolve().parent == dest.resolve():
                    continue  # 輸出目錄＝任務目錄自己 → 略過（防 SameFileError）
                shutil.copy2(path, dest)
        except Exception as exc:
            job.error = f"產出複製失敗：{exc}"
