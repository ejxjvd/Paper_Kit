"""SqliteJobRepository（infra）：任務歷史持久化（票 08）。

紅→綠：欄位全保真 roundtrip（含 list/Decimal/JSON）、save 更新、重啟存活、順序。
"""

from decimal import Decimal
from pathlib import Path

import pytest

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
    # SQLite REAL 存 IEEE double——time.time() 極小尾差容許（CI 實測 7e-6 差）
    assert got.created_at == pytest.approx(job.created_at)


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


# ── 票 10：機密標記隨任務持久化 ──────────────────────────


def test_sensitive_flag_survives_roundtrip_and_restart(tmp_path: Path):
    """票 10：機密標記隨任務記錄（SQLite 欄位），重啟也在。"""
    job = sample_job()
    job.sensitive = True

    db = tmp_path / "app.db"
    repo1 = SqliteJobRepository(db)
    repo1.add(job)
    assert repo1.get("abc123").sensitive is True

    repo2 = SqliteJobRepository(db)  # 重啟
    assert repo2.get("abc123").sensitive is True


def test_sensitive_defaults_false_in_db(tmp_path: Path):
    repo = make_repo(tmp_path)
    repo.add(TranslationJob(job_id="plain", source_path="/out/plain/a.pdf"))
    assert repo.get("plain").sensitive is False


def test_old_schema_migrates_missing_column(tmp_path: Path):
    """票 10 standards review（硬問題）：舊 DB（無 sensitive 欄位）開啟後要能寫入
    ——_COLUMNS 驅動的遷移（PRAGMA table_info → ALTER TABLE）。"""
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, created_at TEXT, status TEXT, "
        "source_path TEXT, target_lang TEXT, pages TEXT, output_dir TEXT, "
        "glossary_files TEXT, auto_extract TEXT, engine_id TEXT, "
        "estimated_cost TEXT, result TEXT, error TEXT)"
    )
    conn.execute(
        "INSERT INTO jobs (job_id, created_at, status, source_path) VALUES (?, ?, ?, ?)",
        ("legacy1", "1755000000.0", "QUEUED", "/out/legacy1/a.pdf"),
    )
    conn.commit()
    conn.close()

    repo = SqliteJobRepository(db)  # 開啟舊 DB → 自動 ALTER TABLE 補欄位
    job = TranslationJob(job_id="new1", source_path="/out/new1/a.pdf", sensitive=True)
    repo.add(job)  # 寫入路徑不再崩（INSERT 含 sensitive 欄位）

    assert repo.get("legacy1").sensitive is False  # 舊列讀取安全
    assert repo.get("new1").sensitive is True


def test_ocr_flag_survives_roundtrip_and_restart(tmp_path: Path):
    """票 12：掃描件標記隨任務記錄（SQLite 欄位），重啟也在。"""
    job = sample_job()
    job.ocr = True

    db = tmp_path / "app.db"
    repo1 = SqliteJobRepository(db)
    repo1.add(job)
    assert repo1.get("abc123").ocr is True

    repo2 = SqliteJobRepository(db)  # 重啟
    assert repo2.get("abc123").ocr is True


def test_ocr_defaults_false_in_db(tmp_path: Path):
    repo = make_repo(tmp_path)
    repo.add(TranslationJob(job_id="plain", source_path="/out/plain/a.pdf"))
    assert repo.get("plain").ocr is False


# ── 2026-08-13 成本顯示改版：estimated_tokens 隨任務持久化 ──


def test_estimated_tokens_survives_roundtrip_and_restart(tmp_path: Path):
    """上傳時估算的總 tokens 隨任務記錄（UI 預估顯示用），重啟也在。"""
    job = sample_job()
    job.estimated_tokens = 50_000

    db = tmp_path / "app.db"
    repo1 = SqliteJobRepository(db)
    repo1.add(job)
    assert repo1.get("abc123").estimated_tokens == 50_000

    repo2 = SqliteJobRepository(db)  # 重啟
    assert repo2.get("abc123").estimated_tokens == 50_000


def test_estimated_tokens_none_stays_none(tmp_path: Path):
    """舊任務無 tokens 估算 → 讀回 None（不造假 token 數字）。"""
    repo = make_repo(tmp_path)
    repo.add(TranslationJob(job_id="plain", source_path="/out/plain/a.pdf"))
    assert repo.get("plain").estimated_tokens is None


def test_old_schema_migrates_estimated_tokens_column(tmp_path: Path):
    """舊 DB（無 estimated_tokens 欄位，如 2026-08-13 改版前的 DB）開啟後要能寫入
    ——_COLUMNS 驅動的遷移（PRAGMA table_info → ALTER TABLE）自動補欄。"""
    import sqlite3

    db = tmp_path / "old.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, created_at TEXT, status TEXT, "
        "source_path TEXT, target_lang TEXT, pages TEXT, output_dir TEXT, "
        "glossary_files TEXT, auto_extract TEXT, engine_id TEXT, "
        "estimated_cost TEXT, result TEXT, error TEXT)"
    )
    conn.execute(
        "INSERT INTO jobs (job_id, created_at, status, source_path) VALUES (?, ?, ?, ?)",
        ("legacy1", "1755000000.0", "QUEUED", "/out/legacy1/a.pdf"),
    )
    conn.commit()
    conn.close()

    repo = SqliteJobRepository(db)  # 開啟舊 DB → 自動 ALTER TABLE 補欄位
    new_job = TranslationJob(job_id="new1", source_path="/out/new1/a.pdf")
    new_job.estimated_tokens = 15_700
    repo.add(new_job)  # 寫入路徑不再崩（INSERT 含 estimated_tokens 欄位）

    assert repo.get("legacy1").estimated_tokens is None  # 舊列讀取安全
    assert repo.get("new1").estimated_tokens == 15_700


# ── #85 BabelDOC 風格介面：only_selected_pages 隨任務持久化 ──


def test_only_selected_pages_survives_roundtrip_and_restart(tmp_path: Path):
    """#85：「僅選中頁面」toggle 狀態隨任務記錄（SQLite 欄位），重啟也在。"""
    job = sample_job()
    job.only_selected_pages = False

    db = tmp_path / "app.db"
    repo1 = SqliteJobRepository(db)
    repo1.add(job)
    assert repo1.get("abc123").only_selected_pages is False

    repo2 = SqliteJobRepository(db)  # 重啟
    assert repo2.get("abc123").only_selected_pages is False


def test_only_selected_pages_defaults_true_in_db(tmp_path: Path):
    """#85：舊任務/預設 → 僅選中頁面 ON（不送 flag 的唯二時機是 toggle OFF 或無頁面）。"""
    repo = make_repo(tmp_path)
    repo.add(TranslationJob(job_id="plain", source_path="/out/plain/a.pdf"))
    assert repo.get("plain").only_selected_pages is True


# ── #85 切片C：babeldoc 進階選項持久化 ──


def test_advanced_options_survive_roundtrip_and_restart(tmp_path: Path):
    """#85 切片C：相容模式／行號增強／非公式線條／字體隨任務記錄，重啟也在。"""
    job = sample_job()
    job.enhance_compatibility = True
    job.merge_alternating_line_numbers = False
    job.remove_non_formula_lines = True
    job.font_family = "script"

    db = tmp_path / "app.db"
    repo1 = SqliteJobRepository(db)
    repo1.add(job)
    restored = repo1.get("abc123")
    assert restored.enhance_compatibility is True
    assert restored.merge_alternating_line_numbers is False
    assert restored.remove_non_formula_lines is True
    assert restored.font_family == "script"

    repo2 = SqliteJobRepository(db)  # 重啟
    restored = repo2.get("abc123")
    assert restored.enhance_compatibility is True
    assert restored.merge_alternating_line_numbers is False
    assert restored.remove_non_formula_lines is True
    assert restored.font_family == "script"


def test_advanced_options_default_in_db(tmp_path: Path):
    """#85 切片C：舊任務/預設 → 相容模式關／行號增強開／不移除線條／serif。"""
    repo = make_repo(tmp_path)
    repo.add(TranslationJob(job_id="plain", source_path="/out/plain/a.pdf"))
    job = repo.get("plain")
    assert job.enhance_compatibility is False
    assert job.merge_alternating_line_numbers is True
    assert job.remove_non_formula_lines is False
    assert job.font_family == "serif"


# ── #15：total_pages 持久化（進度框「N/M 頁」的 M） ─────────────


def test_total_pages_survives_roundtrip_and_restart(tmp_path: Path):
    repo = make_repo(tmp_path)
    job = sample_job()
    job.total_pages = 12
    repo.add(job)
    repo2 = make_repo(tmp_path)  # 重啟：新連線（auto-migrate 補欄）
    assert repo2.get("abc123").total_pages == 12


def test_total_pages_none_stays_none(tmp_path: Path):
    repo = make_repo(tmp_path)
    repo.add(sample_job())
    assert repo.get("abc123").total_pages is None


# ── #27：pdf_pages 持久化（PDF 總頁數，歷史頁「N/M 頁」的 M） ─────


def test_pdf_pages_survives_roundtrip_and_restart(tmp_path: Path):
    repo = make_repo(tmp_path)
    job = sample_job()
    job.total_pages = 2
    job.pdf_pages = 58
    repo.add(job)
    repo2 = make_repo(tmp_path)  # 重啟：新連線（auto-migrate 補欄）
    assert repo2.get("abc123").total_pages == 2
    assert repo2.get("abc123").pdf_pages == 58
