"""JobService（application）：上傳→輸出目錄、背景翻譯、狀態查詢。

UI 薄層只依賴 JobService；引擎換插頭＝換 engine 參數（Ports & Adapters）。
"""

import logging
import shutil
import threading
import uuid
from pathlib import Path

from paper_kit.application.errors import to_user_message
from paper_kit.application.fingerprint import fingerprint
from paper_kit.application.ocr import OcrService
from paper_kit.application.ports import EngineError, JobRepository, TranslationEnginePort
from paper_kit.application.start_translation import StartTranslation
from paper_kit.application.translation_cache import CachedResult, TranslationCache
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.infrastructure.logging_setup import format_error_chain

logger = logging.getLogger("paper_kit.application.job_service")  # 票 09：事件 log 帶 job_id


class JobService:
    """任務服務：建立（複製上傳檔進 outputs/<job_id>/）、背景執行、等待。"""

    def __init__(self, jobs: JobRepository, outputs_dir: str | Path,
                 ocr: OcrService | None = None, cache: TranslationCache | None = None):
        """cache：任務層快取（票 24）——None＝無快取（無頭模式）；enabled=False＝關閉開關。"""
        self._jobs = jobs
        self._outputs = Path(outputs_dir)
        self._threads: dict[str, threading.Thread] = {}
        self._engines: dict[str, TranslationEnginePort] = {}  # 票 08：cancel 要摸得到引擎
        self._lock = threading.Lock()  # 票 08：cancel vs worker 終態判定互斥（review 修正）
        self._ocr = ocr  # 票 12：掃描件 OCR（None＝未啟用；呼叫端組裝注入）
        self._cache = cache  # 票 24：翻譯快取（None＝未注入；快取是優化不是依賴）
        # 票 08：重啟後從 repo 載入歷史（SQLite 才有記憶；InMemory 回傳空）
        self._order = [job.job_id for job in jobs.list()]
        self._reclaim_stuck_jobs(jobs)

    def create_job(
        self,
        upload_path: str | Path,
        target_lang: str = "zh-TW",
        pages: str | None = None,
        output_dir: str = "",
        sensitive: bool = False,
        ocr: bool = False,
    ) -> TranslationJob:
        """把上傳檔複製進任務資料夾，建立 queued 任務。

        pages：頁面範圍（票 07，None=全部）；output_dir：完成後產出複製到的目錄
        （票 07，空白=留在預設 outputs/<job_id>/）；sensitive：機密文件
        （票 10——只准純文字引擎，start 時強制檢查）；ocr：掃描件
        （票 12——執行前先本機 OCR 內嵌文字層，既有翻譯管線零改動）。
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
            sensitive=sensitive,
            ocr=ocr,
        )
        self._jobs.add(job)
        self._order.append(job_id)
        logger.info("任務已建立", extra={"job_id": job_id})
        return job

    def list_jobs(self) -> list[TranslationJob]:
        """任務列表（建立順序，UI 輪詢用）。"""
        return [self._jobs.get(job_id) for job_id in self._order if self._jobs.get(job_id)]

    @staticmethod
    def _assert_sensitive_allowed(job: TranslationJob, engine_allows_sensitive: bool | None) -> None:
        """票 10 紅線（fail-closed）：機密任務只放行「明確聲明相容」的引擎。

        None（未聲明）也拒絕——紅線不依賴呼叫端記得傳 flag（spec review 修正）；
        application 層不查 ENGINE_SPECS（保持不依賴 infrastructure 引擎註冊表，
        相容性由有 registry 的呼叫端聲明）。
        """
        if job.sensitive and engine_allows_sensitive is not True:
            raise ValueError("機密文件只可使用純文字引擎（DeepSeek）；已阻止使用視覺引擎")

    def start(
        self,
        job_id: str,
        engine: TranslationEnginePort,
        engine_id: str | None = None,
        *,
        engine_allows_sensitive: bool | None = None,
    ) -> None:
        """背景 thread 執行翻譯；立即回傳。engine_id 記在任務上（票 06 計價）。

        engine_allows_sensitive（票 10 紅線）：呼叫端（有 ENGINE_SPECS 的 UI 層）
        聲明引擎的機密相容性——機密任務只放行 True（fail-closed：None/False 都拒絕，
        任務維持 queued、引擎不被呼叫）。
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        self._assert_sensitive_allowed(job, engine_allows_sensitive)
        job.engine_id = engine_id
        self._engines[job_id] = engine
        thread = threading.Thread(target=self._run, args=(job, engine), daemon=True)
        thread.start()
        self._threads[job_id] = thread
        logger.info("任務開始翻譯", extra={"job_id": job_id, "engine": engine_id})

    def retry(
        self,
        job_id: str,
        engine: TranslationEnginePort,
        engine_id: str | None = None,
        *,
        engine_allows_sensitive: bool | None = None,
    ) -> None:
        """票 08：失敗任務重試——回 queued 再跑一次（不需重新上傳）。

        engine_id 省略（spec review 防護）→ 沿用任務原本的引擎 id，
        不把 job.engine_id 覆寫成 None。
        engine_allows_sensitive（票 10）：機密任務重試同 start 的紅線檢查——
        standards review 修正：檢查先於狀態變更（被拒的重試不該把任務弄成 queued）。
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        self._assert_sensitive_allowed(job, engine_allows_sensitive)
        job.transition(JobStatus.QUEUED)  # 非 FAILED → InvalidTransition
        job.error = None
        self._jobs.save(job)
        self.start(
            job_id, engine,
            engine_id=engine_id if engine_id is not None else job.engine_id,
            engine_allows_sensitive=engine_allows_sensitive,
        )

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
        logger.info("任務已取消", extra={"job_id": job_id})

    def delete(self, job_id: str) -> None:
        """票 18：永久刪除任務——執行中拒絕、移除 repo 記錄與輸出目錄。

        執行中＝ live thread 存在 或 狀態為排隊/翻譯中（review 修正：start() 在
        QUEUED 就 spawn thread、轉換發生在 StartTranslation.run 內——QUEUED 任務
        也可能有活 thread 在寫）。判定與移除包在 _lock 內、對齊 cancel 的
        check-then-act race 修正（worker 的狀態轉換持同一把鎖）。未知任務 KeyError。
        """
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        with self._lock:
            if (
                job_id in self._threads
                or job.status in (JobStatus.QUEUED, JobStatus.TRANSLATING)
            ):
                raise ValueError("執行中的任務不可刪除")
            self._jobs.remove(job_id)
            self._order.remove(job_id)
        self._threads.pop(job_id, None)
        self._engines.pop(job_id, None)
        out_dir = self._outputs / job_id
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        logger.info("任務已刪除", extra={"job_id": job_id})

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

    def _prepare_ocr(self, job: TranslationJob) -> None:
        """票 12：掃描件執行前先本機 OCR——把無文字層 PDF 變成有文字層。

        OCR 產出（ocr-*.pdf）放任務資料夾；有文字層時 ensure_text_layer
        回 None（不動原檔）。失敗丟 EngineError → 既有 FAILED 路徑接手。
        """
        if not job.ocr:
            return
        if self._ocr is None:  # spec review：未注入（無頭模式）→ 明確失敗，不靜默照翻
            raise EngineError("掃描件 OCR 未啟用（無頭模式未注入 OCR 服務）")
        prepared = self._ocr.ensure_text_layer(Path(job.source_path))
        if prepared is not None:
            job.source_path = str(prepared)  # 引擎翻 OCR 版；完成時 save 一併持久化

    def _run(self, job: TranslationJob, engine: TranslationEnginePort) -> None:
        try:
            self._prepare_ocr(job)
            fp = self._fingerprint(job)
            if fp is not None:
                hit = self._cache.get(fp)  # type: ignore[union-attr]
                if hit is not None:
                    self._apply_cache_hit(job, hit)
                    return
            done = StartTranslation(
                engine=engine, jobs=self._jobs, lock=self._lock
            ).run(job)
            if fp is not None and done.status is JobStatus.COMPLETED:
                self._cache.put(  # type: ignore[union-attr]
                    fp, done.result.mono_path, done.result.dual_path
                )
            self._copy_outputs(done)
            if done.status is JobStatus.COMPLETED:
                logger.info("任務完成", extra={"job_id": job.job_id})
            elif done.status is JobStatus.CANCELLED:
                logger.info("任務已取消", extra={"job_id": job.job_id})
            else:
                logger.error(
                    "任務失敗",
                    extra={"job_id": job.job_id, "error": done.error or "(無訊息)"},
                )
        except Exception as exc:
            # 票 09 spec review：非 EngineError 的意外例外（引擎 bug、記憶體…）
            # 不讓 daemon thread 連 traceback 直接死——job 標 FAILED＋log 錯誤鏈。
            with self._lock:
                if job.status is not JobStatus.CANCELLED:  # 取消後引擎才爆 → 維持 cancelled
                    job.transition(JobStatus.FAILED)
                    job.error = to_user_message(exc)  # 不吐原始 traceback
                    self._jobs.save(job)
            logger.error(
                "任務失敗（未預期例外）",
                extra={"job_id": job.job_id, "error_chain": format_error_chain(exc)},
            )
        finally:
            # 票 08 review：thread/engine 引用收尾清理（歷史任務無界增長）
            self._threads.pop(job.job_id, None)
            self._engines.pop(job.job_id, None)

    def _fingerprint(self, job: TranslationJob) -> str | None:
        """票 24：快取指紋——cache 未注入或開關關閉 → None（不查不寫）。

        在 _prepare_ocr 之後呼叫：job.source_path 已是引擎實際讀取的檔、
        engine_id 已由 start() 寫入、glossary_files 已由 UI 附加。
        """
        if self._cache is None or not self._cache.enabled:
            return None
        return fingerprint(
            source_path=job.source_path,
            engine_id=job.engine_id or "",
            target_lang=job.target_lang,
            pages=job.pages,
            sensitive=job.sensitive,
            glossary_files=job.glossary_files,
        )

    def _apply_cache_hit(self, job: TranslationJob, hit: CachedResult) -> None:
        """票 24：快取命中——複製快取檔進任務目錄（慣例檔名，下載/輸出機制零改動）。

        檔名對齊引擎產出慣例 {stem}.{lang}.mono.pdf（pdf2zh 系）；副檔名取自
        快取檔（LaTeX/PPT 路線產出不同型別）。複製失敗＝磁碟問題 → 外層 except
        接手標 FAILED（任務可重試，快取下次仍可命中）。
        """
        dest_dir = Path(job.source_path).parent
        stem = Path(job.source_path).stem
        mono = self._restore(hit.mono_path, dest_dir / f"{stem}.{job.target_lang}.mono")
        dual = self._restore(hit.dual_path, dest_dir / f"{stem}.{job.target_lang}.dual")
        job.result = JobResult(
            mono_path=str(mono) if mono else None,
            dual_path=str(dual) if dual else None,
            from_cache=True,
        )
        # 2026-08-12 實測 bug：QUEUED→COMPLETED 是非法轉換（狀態機：QUEUED→
        # TRANSLATING→COMPLETED）——快取命中跳過引擎但不能跳過狀態機，
        # 先標 TRANSLATING（語意：進行中→完成，只是瞬間完成）再 COMPLETED。
        job.transition(JobStatus.TRANSLATING)
        job.transition(JobStatus.COMPLETED)
        self._jobs.save(job)
        logger.info("任務命中快取（引擎未呼叫）", extra={"job_id": job.job_id})

    @staticmethod
    def _restore(cache_path: str | None, dest: Path) -> Path | None:
        if not cache_path:
            return None
        out = dest.with_suffix(Path(cache_path).suffix)
        shutil.copy2(cache_path, out)
        return out

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
