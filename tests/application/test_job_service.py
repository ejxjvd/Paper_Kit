"""JobService（application）：上傳→輸出目錄、背景翻譯、狀態查詢。

紅→綠 slice A/B：create_job 把上傳檔複製進 outputs/<job_id>/ 並建立 queued 任務；
start 在背景 thread 跑 StartTranslation（FakeEngine 注入，主接縫）。
"""

import time
from pathlib import Path

import pytest

from paper_kit.application.job_service import JobService
from paper_kit.application.pages import page_count_in_range, parse_pages
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


# ── 票 07：頁面範圍＋輸出目錄 ────────────────────────────────


@pytest.mark.parametrize(
    "text,expected",
    [
        ("", None),        # 空白 = 全部
        ("   ", None),
        (None, None),      # Quasar clearable 清空給 null → 等同空白（review 修正）
        ("1-2", "1-2"),
        ("3-5", "3-5"),
        ("1", "1"),
        ("1-2,4-6", "1-2,4-6"),
        (" 3-5 ", "3-5"),
    ],
)
def test_parse_pages_accepts_valid_ranges(text, expected):
    assert parse_pages(text) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "abc", "1-2-3", "1--2", "-1", "1-", "1.5", "1-2,", "，",
        "0-5", "5-2", "0", "1-0", "10-2",  # 語義檢查（review 修正）：頁≥1、起≤終
    ],
)
def test_parse_pages_rejects_invalid_ranges(bad):
    with pytest.raises(ValueError):
        parse_pages(bad)


@pytest.mark.parametrize(
    "spec,expected",
    [
        ("1-2", 2),
        ("3-5", 3),
        ("1", 1),
        ("10", 1),        # 單頁 = 第 10 頁
        ("1-2,4-6", 5),   # 2 + 3
        ("1-10,20-25", 16),  # 10 + 6
    ],
)
def test_page_count_in_range(spec, expected):
    """票 07 review：範圍規格 → 頁數（成本估算按範圍縮放用）。"""
    assert page_count_in_range(spec) == expected


def test_create_job_records_pages_and_output_dir(tmp_path: Path, upload_pdf: Path):
    service, _ = make_service(tmp_path)
    job = service.create_job(
        upload_path=upload_pdf, pages="1-2", output_dir="/out/custom"
    )
    assert job.pages == "1-2"
    assert job.output_dir == "/out/custom"


def test_completed_job_copies_outputs_to_configured_dir(tmp_path: Path, upload_pdf: Path):
    """票 07：完成任務把 mono/dual 複製到設定的輸出目錄。"""
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf, output_dir=str(tmp_path / "out"))
    src_dir = Path(job.source_path).parent
    mono = src_dir / "a.zh.mono.pdf"
    dual = src_dir / "a.zh.dual.pdf"
    mono.write_bytes(b"mono")
    dual.write_bytes(b"dual")
    engine = FakeEngine(result=JobResult(mono_path=str(mono), dual_path=str(dual)))

    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)

    assert repo.get(job.job_id).status == JobStatus.COMPLETED
    assert (tmp_path / "out" / "a.zh.mono.pdf").read_bytes() == b"mono"
    assert (tmp_path / "out" / "a.zh.dual.pdf").read_bytes() == b"dual"


def test_no_output_dir_keeps_files_in_job_dir(tmp_path: Path, upload_pdf: Path):
    """輸出目錄空白 = 留在預設（~/.paper_kit/outputs/<job_id>）。"""
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    src_dir = Path(job.source_path).parent
    mono = src_dir / "a.zh.mono.pdf"
    mono.write_bytes(b"mono")
    engine = FakeEngine(result=JobResult(mono_path=str(mono), dual_path=""))

    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)

    assert repo.get(job.job_id).status == JobStatus.COMPLETED
    assert mono.read_bytes() == b"mono"  # 原位置沒被搬走


def test_copy_failure_records_error_and_keeps_completed(tmp_path: Path, upload_pdf: Path):
    """review 修正：產出複製失敗（輸出目錄位置是檔案）→ job.error 記錄、thread 不靜默死。"""
    service, repo = make_service(tmp_path)
    blocker = tmp_path / "out"
    blocker.write_bytes(b"i am a file, not a dir")  # mkdir 會 FileExistsError
    job = service.create_job(upload_path=upload_pdf, output_dir=str(blocker))
    src_dir = Path(job.source_path).parent
    mono = src_dir / "a.zh.mono.pdf"
    mono.write_bytes(b"mono")
    engine = FakeEngine(result=JobResult(mono_path=str(mono), dual_path=""))

    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status == JobStatus.COMPLETED
    assert "複製失敗" in done.error


def test_output_dir_equals_job_dir_skips_copy(tmp_path: Path, upload_pdf: Path):
    """review 修正：輸出目錄＝任務自己的目錄 → 略過複製（防 SameFileError）。"""
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    # job 目錄 = outputs/<job_id>；把 output_dir 指向它自己
    job.output_dir = str(Path(job.source_path).parent)
    src_dir = Path(job.source_path).parent
    mono = src_dir / "a.zh.mono.pdf"
    mono.write_bytes(b"mono")
    engine = FakeEngine(result=JobResult(mono_path=str(mono), dual_path=""))

    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status == JobStatus.COMPLETED
    assert done.error is None
    assert mono.read_bytes() == b"mono"


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


def test_start_records_engine_id_on_job(tmp_path: Path, upload_pdf: Path):
    """票 06：任務要記得用哪個引擎，事後才能算實際成本。"""
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    service.start(
        job.job_id,
        FakeEngine(result=JobResult(mono_path="/out/a.mono.pdf")),
        engine_id="deepseek",
    )
    service.wait(job.job_id, timeout=5)
    assert repo.get(job.job_id).engine_id == "deepseek"


def test_engine_receives_glossary_selection_and_auto_extract(tmp_path: Path, upload_pdf: Path):
    """票 05：挑選的術語表組合＋自動提取開關隨任務帶給引擎（FakeEngine 驗證）。"""
    service, _ = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    job.glossary_files = ["/gl/dl.csv", "/gl/img.csv"]
    job.auto_extract = True
    engine = FakeEngine(result=JobResult(mono_path="/out/a.mono.pdf"))

    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)

    received = engine.received[0]
    assert received.glossary_files == ["/gl/dl.csv", "/gl/img.csv"]
    assert received.auto_extract is True


class _SlowEngine:
    def __init__(self, delay: float):
        self._delay = delay

    def translate(self, job: TranslationJob) -> JobResult:
        time.sleep(self._delay)
        return JobResult(mono_path="/out/a.mono.pdf")
