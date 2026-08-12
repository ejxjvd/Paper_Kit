"""JobService（application）：上傳→輸出目錄、背景翻譯、狀態查詢。

紅→綠 slice A/B：create_job 把上傳檔複製進 outputs/<job_id>/ 並建立 queued 任務；
start 在背景 thread 跑 StartTranslation（FakeEngine 注入，主接縫）。
"""

import time
from pathlib import Path

import pytest

from paper_kit.application.job_service import JobService
from paper_kit.application.ports import EngineError
from paper_kit.application.start_translation import StartTranslation
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class InMemoryJobRepository:
    def __init__(self):
        self._jobs = {}

    def add(self, job: TranslationJob) -> None:
        self._jobs[job.job_id] = job

    def get(self, job_id: str) -> TranslationJob | None:
        return self._jobs.get(job_id)

    def save(self, job: TranslationJob) -> None:
        self._jobs[job.job_id] = job


class FakeEngine:
    def __init__(self, result: JobResult | None = None, error: str | None = None):
        self._result = result
        self._error = error
        self.received: list[TranslationJob] = []

    def translate(self, job: TranslationJob) -> JobResult:
        self.received.append(job)
        if self._error:
            raise EngineError(self._error)
        return self._result


@pytest.fixture()
def upload_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4 fake content for upload test")
    return p


def make_service(tmp_path: Path) -> tuple[JobService, InMemoryJobRepository]:
    repo = InMemoryJobRepository()
    return JobService(jobs=repo, outputs_dir=tmp_path / "outputs"), repo


# ── slice A：create_job ──────────────────────────────────────────────


def test_create_job_copies_upload_into_output_dir(tmp_path: Path, upload_pdf: Path):
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)

    assert job.status == JobStatus.QUEUED
    src = Path(job.source_path)
    assert src.exists(), "上傳檔要複製到任務資料夾"
    assert src.parent.parent == tmp_path / "outputs"
    assert src.name == "paper.pdf"
    assert src.read_bytes() == upload_pdf.read_bytes()
    assert repo.get(job.job_id) is job


def test_create_job_defaults_to_traditional_chinese(upload_pdf: Path, tmp_path: Path):
    service, _ = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    assert job.target_lang == "zh-TW"


def test_create_job_each_gets_own_directory(tmp_path: Path, upload_pdf: Path):
    service, _ = make_service(tmp_path)
    j1 = service.create_job(upload_path=upload_pdf)
    j2 = service.create_job(upload_path=upload_pdf)
    assert j1.job_id != j2.job_id
    assert Path(j1.source_path).parent != Path(j2.source_path).parent


# ── slice B：start（背景執行） ───────────────────────────────────────


def test_start_runs_engine_in_background_and_completes(tmp_path: Path, upload_pdf: Path):
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    engine = FakeEngine(
        result=JobResult(mono_path="/out/a.mono.pdf", dual_path="/out/a.dual.pdf")
    )

    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status == JobStatus.COMPLETED
    assert done.result.mono_path == "/out/a.mono.pdf"
    assert engine.received == [job]  # 引擎收到的正是這個任務


def test_start_failure_marks_job_failed_with_message(tmp_path: Path, upload_pdf: Path):
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    service.start(job.job_id, FakeEngine(error="SiliconFlow 上游 500"))
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status == JobStatus.FAILED
    assert "SiliconFlow" in done.error


def test_start_unknown_job_raises(tmp_path: Path):
    service, _ = make_service(tmp_path)
    with pytest.raises(KeyError):
        service.start("no-such-job", FakeEngine())


def test_start_is_non_blocking(tmp_path: Path, upload_pdf: Path):
    """start 要立即回傳（背景執行），等太久代表沒上 thread。"""
    service, _ = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    slow = _SlowEngine(delay=0.3)
    t0 = time.monotonic()
    service.start(job.job_id, slow)
    assert time.monotonic() - t0 < 0.2, "start 不能阻塞"
    service.wait(job.job_id, timeout=5)


class _SlowEngine:
    def __init__(self, delay: float):
        self._delay = delay

    def translate(self, job: TranslationJob) -> JobResult:
        time.sleep(self._delay)
        return JobResult(mono_path="/out/a.mono.pdf")
