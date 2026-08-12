"""StartTranslation 指令：把 queued 任務送進引擎，結果/錯誤存回 repo。"""

from __future__ import annotations  # threading.Lock 在 <3.13 是函數，| 註解需延後求值

import threading
from contextlib import nullcontext

from paper_kit.application.ports import EngineError, JobRepository, TranslationEnginePort
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class StartTranslation:
    """lock 可注入（JobService 共用同一把）：cancel 與 worker 終態判定互斥，
    消除 check-then-act race（review 修正——UI 線程 cancel 與 worker 無鎖共享 job）。"""

    def __init__(
        self,
        engine: TranslationEnginePort,
        jobs: JobRepository,
        lock: threading.Lock | None = None,
    ):
        self._engine = engine
        self._jobs = jobs
        self._lock = lock

    def _finalize(self) -> nullcontext | threading.Lock:
        """鎖住終態判定（檢查 cancelled + transition + save 為原子段）。"""
        return self._lock if self._lock is not None else nullcontext()

    def run(self, job: TranslationJob) -> TranslationJob:
        job.transition(JobStatus.TRANSLATING)  # 非法起點（如已完成）在此被拒
        try:
            result = self._engine.translate(job)
        except EngineError as e:
            with self._finalize():
                if job.status is JobStatus.CANCELLED:
                    return job  # 票 08：取消後引擎才失敗 → 維持 cancelled
                job.transition(JobStatus.FAILED)
                job.error = str(e)
                self._jobs.save(job)
                return job
        with self._finalize():
            if job.status is JobStatus.CANCELLED:
                return job  # 票 08：取消後引擎才完成 → 產出拋棄（維持 cancelled）
            job.transition(JobStatus.COMPLETED)
            job.result = result
            self._jobs.save(job)
            return job
