"""StartTranslation 指令：以 FakeEngine 注入測試（主接縫）。

驗證：任務被正確送出（FakeEngine 收到 job）、結果被正確存回（repo 可取出）、
引擎失敗 → failed 並記錄錯誤。完全不碰真實引擎。
"""

import pytest

from paper_kit.application.ports import EngineError, TranslationEnginePort
from paper_kit.application.start_translation import StartTranslation
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class InMemoryJobRepository:
    """測試用記憶體 repo（實作 JobRepository 埠）。"""

    def __init__(self):
        self._jobs = {}

    def add(self, job: TranslationJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> TranslationJob | None:
        return self._jobs.get(job_id)

    def save(self, job: TranslationJob) -> None:
        self._jobs[job.job_id] = job


class FakeEngine:
    """記錄收到什麼任務、回傳固定結果或丟引擎錯誤。"""

    def __init__(self, result: JobResult | None = None, error: str | None = None):
        self._result = result
        self._error = error
        self.received: list[TranslationJob] = []

    def translate(self, job: TranslationJob) -> JobResult:
        self.received.append(job)
        if self._error:
            raise EngineError(self._error)
        return self._result


def run_success() -> tuple[TranslationJob, FakeEngine, InMemoryJobRepository]:
    job = TranslationJob(job_id="job-1")
    repo = InMemoryJobRepository()
    repo.add(job)
    engine = FakeEngine(
        result=JobResult(mono_path="/out/job-1.mono.pdf", dual_path="/out/job-1.dual.pdf")
    )
    StartTranslation(engine=engine, jobs=repo).run(job)
    return job, engine, repo


def test_job_sent_to_engine_and_completed():
    job, engine, _ = run_success()
    assert engine.received == [job]  # 任務被正確送出
    assert job.status == JobStatus.COMPLETED


def test_result_stored_back_with_tokens():
    job = TranslationJob(job_id="job-1")
    repo = InMemoryJobRepository()
    repo.add(job)
    engine = FakeEngine(
        result=JobResult(
            mono_path="/out/job-1.mono.pdf",
            dual_path="/out/job-1.dual.pdf",
            input_tokens=7127,
            output_tokens=2219,
        )
    )
    StartTranslation(engine=engine, jobs=repo).run(job)
    stored = repo.get("job-1")
    assert stored.result.mono_path == "/out/job-1.mono.pdf"
    assert stored.result.dual_path == "/out/job-1.dual.pdf"
    assert stored.result.input_tokens == 7127  # 實際用量存回（成本紀錄用）


def test_engine_failure_marks_job_failed_with_error():
    job = TranslationJob(job_id="job-1")
    repo = InMemoryJobRepository()
    repo.add(job)
    engine = FakeEngine(error="SiliconFlow 上游 500")
    StartTranslation(engine=engine, jobs=repo).run(job)
    assert job.status == JobStatus.FAILED
    assert "SiliconFlow" in job.error
    assert repo.get("job-1").status == JobStatus.FAILED  # 失敗也存回


def test_cannot_start_completed_job():
    job = TranslationJob(job_id="job-1")
    job.transition(JobStatus.TRANSLATING)
    job.transition(JobStatus.COMPLETED)
    repo = InMemoryJobRepository()
    repo.add(job)
    engine = FakeEngine(result=JobResult(mono_path="/x.pdf"))
    with pytest.raises(Exception):
        StartTranslation(engine=engine, jobs=repo).run(job)
    assert engine.received == []  # 沒送出
