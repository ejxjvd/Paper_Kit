"""JobService（application）：上傳→輸出目錄、背景翻譯、狀態查詢。

UI 薄層只依賴 JobService；引擎換插頭＝換 engine 參數（Ports & Adapters）。
"""

import shutil
import threading
import uuid
from pathlib import Path

from paper_kit.application.ports import JobRepository, TranslationEnginePort
from paper_kit.application.start_translation import StartTranslation
from paper_kit.domain.translation_job import TranslationJob


class JobService:
    """任務服務：建立（複製上傳檔進 outputs/<job_id>/）、背景執行、等待。"""

    def __init__(self, jobs: JobRepository, outputs_dir: str | Path):
        self._jobs = jobs
        self._outputs = Path(outputs_dir)
        self._threads: dict[str, threading.Thread] = {}
        self._order: list[str] = []

    def create_job(self, upload_path: str | Path, target_lang: str = "zh-TW") -> TranslationJob:
        """把上傳檔複製進任務資料夾，建立 queued 任務。"""
        job_id = uuid.uuid4().hex
        src = Path(upload_path)
        dest_dir = self._outputs / job_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / src.name
        shutil.copy2(src, dest)
        job = TranslationJob(job_id=job_id, source_path=str(dest), target_lang=target_lang)
        self._jobs.add(job)
        self._order.append(job_id)
        return job

    def list_jobs(self) -> list[TranslationJob]:
        """任務列表（建立順序，UI 輪詢用）。"""
        return [self._jobs.get(job_id) for job_id in self._order if self._jobs.get(job_id)]

    def start(self, job_id: str, engine: TranslationEnginePort) -> None:
        """背景 thread 執行翻譯；立即回傳。"""
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        thread = threading.Thread(target=self._run, args=(job, engine), daemon=True)
        thread.start()
        self._threads[job_id] = thread

    def wait(self, job_id: str, timeout: float = 10.0) -> None:
        """等待背景執行結束（測試／無頭執行用）。"""
        thread = self._threads.get(job_id)
        if thread is not None:
            thread.join(timeout)

    def _run(self, job: TranslationJob, engine: TranslationEnginePort) -> None:
        StartTranslation(engine=engine, jobs=self._jobs).run(job)
