"""InMemoryJobRepository：測試與現階段 UI 共用的記憶體 repo。

正式持久化（SQLite）在票 08（任務歷史）。"""

from paper_kit.domain.translation_job import TranslationJob


class InMemoryJobRepository:
    """實作 JobRepository 埠（add/get/save）。"""

    def __init__(self):
        self._jobs: dict[str, TranslationJob] = {}

    def add(self, job: TranslationJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> TranslationJob | None:
        return self._jobs.get(job_id)

    def save(self, job: TranslationJob) -> None:
        self._jobs[job.job_id] = job
