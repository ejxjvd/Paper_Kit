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
from paper_kit.domain.translation_job import InvalidTransition, JobStatus, TranslationJob
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository


class FakeEngine:
    def __init__(
        self,
        result: JobResult | None = None,
        error: str | None = None,
        delay: float = 0.0,
        honor_cancel: bool = True,
    ):
        self._result = result
        self._error = error
        self._delay = delay
        self._honor_cancel = honor_cancel
        self.received: list[TranslationJob] = []
        self.cancelled = False

    def translate(self, job: TranslationJob) -> JobResult:
        self.received.append(job)
        time.sleep(self._delay)
        if self.cancelled and self._honor_cancel:
            raise EngineError("已取消")  # 真實引擎取消後會失敗
        if self._error:
            raise EngineError(self._error)
        return self._result

    def cancel(self) -> None:
        self.cancelled = True


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


# ── 票 08：歷史持久化（重啟存活） ──────────────────────────────


def test_history_survives_restart(tmp_path: Path, upload_pdf: Path):
    """票 08：SQLite 歷史——重啟 app 後任務仍在（含結果與成本）。"""
    from paper_kit.infrastructure.job_repo import SqliteJobRepository

    db = tmp_path / "app.db"
    service = JobService(
        jobs=SqliteJobRepository(db), outputs_dir=tmp_path / "outputs"
    )
    job = service.create_job(upload_path=upload_pdf)
    service.start(
        job.job_id,
        FakeEngine(result=JobResult(mono_path="/out/a.mono.pdf", input_tokens=100)),
        engine_id="deepseek",
    )
    service.wait(job.job_id, timeout=5)

    restarted = JobService(
        jobs=SqliteJobRepository(db), outputs_dir=tmp_path / "outputs"
    )
    jobs = restarted.list_jobs()
    assert [j.job_id for j in jobs] == [job.job_id]
    done = jobs[0]
    assert done.status == JobStatus.COMPLETED
    assert done.result.input_tokens == 100
    assert done.engine_id == "deepseek"


def test_job_records_created_at(tmp_path: Path, upload_pdf: Path):
    """票 08：歷史列表要顯示時間——任務建立即記錄。"""
    service, _ = make_service(tmp_path)
    j1 = service.create_job(upload_path=upload_pdf)
    j2 = service.create_job(upload_path=upload_pdf)
    assert j1.created_at > 0
    assert j2.created_at >= j1.created_at


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
    slow = FakeEngine(delay=0.3, result=JobResult(mono_path="/out/a.mono.pdf"))
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


# ── 票 08：重試＋取消 ───────────────────────────────────────────


def test_retry_failed_job_runs_again_without_reupload(tmp_path: Path, upload_pdf: Path):
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    service.start(job.job_id, FakeEngine(error="SiliconFlow 上游 500"))
    service.wait(job.job_id, timeout=5)
    assert repo.get(job.job_id).status == JobStatus.FAILED

    engine = FakeEngine(result=JobResult(mono_path="/out/a.mono.pdf"))
    service.retry(job.job_id, engine, engine_id="deepseek")
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status == JobStatus.COMPLETED
    assert done.result.mono_path == "/out/a.mono.pdf"
    assert done.engine_id == "deepseek"
    assert engine.received[0].source_path == job.source_path  # 不需重新上傳
    assert done.error is None  # 舊錯誤清除


def test_retry_non_failed_job_raises(tmp_path: Path, upload_pdf: Path):
    service, _ = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)  # QUEUED，非 FAILED
    with pytest.raises(InvalidTransition):
        service.retry(job.job_id, FakeEngine())


def test_cancel_translating_job_notifies_engine(tmp_path: Path, upload_pdf: Path):
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    engine = FakeEngine(delay=0.5, result=JobResult(mono_path="/out/a.mono.pdf"))
    service.start(job.job_id, engine)
    time.sleep(0.1)  # 等 worker 進 translating（delay 0.5 ≫ 0.1）

    service.cancel(job.job_id)

    assert repo.get(job.job_id).status is JobStatus.CANCELLED
    assert engine.cancelled is True
    service.wait(job.job_id, timeout=5)  # thread 收尾不崩
    assert repo.get(job.job_id).status is JobStatus.CANCELLED


def test_cancel_after_engine_completes_drops_result(tmp_path: Path, upload_pdf: Path):
    """取消後引擎才完成 → 維持 cancelled、產出拋棄（無 crash）。"""
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    engine = FakeEngine(
        delay=0.3,
        honor_cancel=False,  # 這引擎無視取消、照常回結果
        result=JobResult(mono_path="/out/a.mono.pdf"),
    )
    service.start(job.job_id, engine)
    time.sleep(0.1)
    service.cancel(job.job_id)
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status is JobStatus.CANCELLED
    assert done.result is None  # 產出拋棄


def test_cancel_unknown_job_raises(tmp_path: Path):
    service, _ = make_service(tmp_path)
    with pytest.raises(KeyError):
        service.cancel("no-such-job")


# ── spec review 修正回歸 ────────────────────────────────────────


def test_init_reclaims_stuck_jobs(tmp_path: Path):
    """spec review：重啟時回收卡死的進行中任務（進度條永不結束、cancel 殺不到）。

    翻譯程序隨 app 死亡 → queued/translating 標 FAILED＋說明；完成任務不受影響。
    """
    repo = InMemoryJobRepository()
    stuck_translating = TranslationJob(
        job_id="t1", source_path="a.pdf", status=JobStatus.TRANSLATING
    )
    stuck_queued = TranslationJob(job_id="q1", source_path="b.pdf")
    finished = TranslationJob(
        job_id="c1", source_path="c.pdf", status=JobStatus.COMPLETED
    )
    for j in (stuck_translating, stuck_queued, finished):
        repo.add(j)

    service = JobService(jobs=repo, outputs_dir=tmp_path / "outputs")

    assert repo.get("t1").status is JobStatus.FAILED
    assert repo.get("t1").error == "應用重啟，翻譯中斷（請重試）"
    assert repo.get("q1").status is JobStatus.FAILED
    assert repo.get("c1").status is JobStatus.COMPLETED  # 完成任務不受影響
    assert service.list_jobs()[0].can_retry is True  # 回收後可重試


def test_retry_without_engine_id_keeps_original_engine(tmp_path: Path, upload_pdf: Path):
    """spec review：retry 不帶 engine_id 時沿用任務原本引擎（不覆寫成 None）。"""
    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    service.start(job.job_id, FakeEngine(error="上游 500"))
    service.wait(job.job_id, timeout=5)
    assert repo.get(job.job_id).status is JobStatus.FAILED

    service.retry(job.job_id, FakeEngine(result=JobResult(mono_path="/out/a.mono.pdf")))
    service.wait(job.job_id, timeout=5)

    assert repo.get(job.job_id).status is JobStatus.COMPLETED
    assert repo.get(job.job_id).engine_id == job.engine_id


# ── 票 09 spec review：意外例外的兜底 ──────────────────────────


def test_unexpected_exception_in_worker_marks_failed(tmp_path: Path, upload_pdf: Path):
    """非 EngineError 意外例外（引擎 bug）不讓 daemon thread 帶 traceback 死亡：
    job 標 FAILED＋使用者訊息，不再卡 TRANSLATING。"""
    class ExplodingEngine:
        def translate(self, job):
            raise RuntimeError("boom at engine internals")

        def cancel(self):
            pass

    service, repo = make_service(tmp_path)
    job = service.create_job(upload_path=upload_pdf)
    service.start(job.job_id, ExplodingEngine())
    service.wait(job.job_id, timeout=5)

    done = repo.get(job.job_id)
    assert done.status is JobStatus.FAILED, "意外例外也要收斂到 FAILED"
    assert "boom" in done.error
    assert "Traceback" not in done.error  # 不吐原始 traceback
    assert done.can_retry is True  # 之後可重試
