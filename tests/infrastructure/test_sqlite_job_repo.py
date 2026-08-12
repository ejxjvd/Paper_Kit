"""SqliteJobRepository（infra）：任務歷史持久化（票 08）。

紅→綠：欄位全保真 roundtrip（含 list/Decimal/JSON）、save 更新、重啟存活、順序。
"""

from decimal import Decimal
from pathlib import Path

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.infrastructure.job_repo import SqliteJobRepository


def make_repo(tmp_path: Path) -> SqliteJobRepository:
    return SqliteJobRepository(tmp_path / "app.db")


def sample_job() -> TranslationJob:
    job = TranslationJob(
        job_id="abc123",
        source_path="/out/abc123/paper.pdf",
        target_lang="zh-TW",
        pages="1-2",
        output_dir="/out/custom",
        glossary_files=["/gl/dl.csv", "/gl/img.csv"],
        auto_extract=True,
        engine_id="deepseek",
        estimated_cost=Decimal("0.004609"),
        error="先前錯誤",
    )
    job.result = JobResult(
        mono_path="/out/abc123/a.zh.mono.pdf",
        dual_path="/out/abc123/a.zh.dual.pdf",
        input_tokens=7127,
        output_tokens=2219,
    )
    return job


def test_add_get_roundtrip_full_fidelity(tmp_path: Path):
    repo = make_repo(tmp_path)
    job = sample_job()
    repo.add(job)

    got = repo.get("abc123")
    assert got is not None
    assert got.job_id == "abc123"
    assert got.status is JobStatus.QUEUED
    assert got.pages == "1-2" and got.output_dir == "/out/custom"
    assert got.glossary_files == ["/gl/dl.csv", "/gl/img.csv"]
    assert got.auto_extract is True
    assert got.engine_id == "deepseek"
    assert got.estimated_cost == Decimal("0.004609")
    assert got.error == "先前錯誤"
    assert got.result.mono_path == "/out/abc123/a.zh.mono.pdf"
    assert got.result.input_tokens == 7127
    assert got.created_at == job.created_at


def test_save_updates_existing_job(tmp_path: Path):
    repo = make_repo(tmp_path)
    job = sample_job()
    repo.add(job)
    job.transition(JobStatus.TRANSLATING)  # 依領域狀態機逐段走
    job.transition(JobStatus.COMPLETED)
    repo.save(job)

    assert repo.get("abc123").status is JobStatus.COMPLETED


def test_history_survives_restart(tmp_path: Path):
    db = tmp_path / "app.db"
    repo1 = SqliteJobRepository(db)
    repo1.add(sample_job())

    repo2 = SqliteJobRepository(db)  # 新連線 = 重啟
    got = repo2.get("abc123")
    assert got is not None
    assert got.result.dual_path == "/out/abc123/a.zh.dual.pdf"
    assert got.estimated_cost == Decimal("0.004609")


def test_list_returns_jobs_in_creation_order(tmp_path: Path):
    repo = make_repo(tmp_path)
    for i in range(3):
        job = TranslationJob(job_id=f"j{i}", source_path=f"/out/j{i}/a.pdf")
        repo.add(job)

    assert [j.job_id for j in repo.list()] == ["j0", "j1", "j2"]


def test_list_empty_db(tmp_path: Path):
    assert make_repo(tmp_path).list() == []


def test_get_unknown_returns_none(tmp_path: Path):
    assert make_repo(tmp_path).get("nope") is None
