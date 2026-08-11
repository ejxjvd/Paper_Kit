"""StartTranslation 指令：把 queued 任務送進引擎，結果/錯誤存回 repo。"""

from paper_kit.application.ports import EngineError, JobRepository, TranslationEnginePort
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class StartTranslation:
    def __init__(self, engine: TranslationEnginePort, jobs: JobRepository):
        self._engine = engine
        self._jobs = jobs

    def run(self, job: TranslationJob) -> TranslationJob:
        job.transition(JobStatus.TRANSLATING)  # 非法起點（如已完成）在此被拒
        try:
            result = self._engine.translate(job)
        except EngineError as e:
            job.transition(JobStatus.FAILED)
            job.error = str(e)
            self._jobs.save(job)
            return job
        job.transition(JobStatus.COMPLETED)
        job.result = result
        self._jobs.save(job)
        return job
