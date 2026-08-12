"""e2e（FakeEngine）：UI 薄層→application→port 全鏈路。

上傳 fixture PDF → JobService.create_job（複製進 outputs/<job_id>/）→
start（FakeEngine 把 mono/dual 寫進任務資料夾）→ wait → build_job_card
產出下載/預覽 URL，且對應檔案真實存在（靜態伺服真的送得出）。
"""

from pathlib import Path

from paper_kit.application.job_service import JobService
from paper_kit.application.ports import EngineError
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.presentation.handlers import build_job_card

FAKE_MONO = b"%PDF-1.4 fake mono output"
FAKE_DUAL = b"%PDF-1.4 fake dual output"


class FileWritingFakeEngine:
    """模擬 pdf2zh 行為：把 mono/dual 以 {stem}.zh.mono/.dual.pdf 命名寫進任務資料夾。"""

    def __init__(self, error: str | None = None):
        self._error = error
        self.received: list[TranslationJob] = []

    def translate(self, job: TranslationJob) -> JobResult:
        self.received.append(job)
        if self._error:
            raise EngineError(self._error)
        out_dir = Path(job.source_path).parent
        stem = Path(job.source_path).stem
        mono = out_dir / f"{stem}.zh.mono.pdf"
        dual = out_dir / f"{stem}.zh.dual.pdf"
        mono.write_bytes(FAKE_MONO)
        dual.write_bytes(FAKE_DUAL)
        return JobResult(mono_path=str(mono), dual_path=str(dual))


def upload_and_translate(tmp_path: Path, engine) -> tuple[JobService, TranslationJob]:
    upload = tmp_path / "upload" / "paper.pdf"
    upload.parent.mkdir()
    upload.write_bytes(b"%PDF-1.4 source")
    service = JobService(jobs=InMemoryJobRepository(), outputs_dir=tmp_path / "outputs")
    job = service.create_job(upload_path=upload)
    service.start(job.job_id, engine)
    service.wait(job.job_id, timeout=5)
    return service, job


def test_upload_to_download_links_end_to_end(tmp_path: Path):
    service, job = upload_and_translate(tmp_path, FileWritingFakeEngine())

    view = build_job_card(job)
    assert view.status_label == "完成"
    assert view.mono_url and view.dual_url
    # URL 對應的檔案真實存在（static files 送得出）
    assert Path(job.result.mono_path).exists()
    assert Path(job.result.dual_path).exists()
    assert Path(job.result.mono_path).read_bytes() == FAKE_MONO
    assert view.file_name == "paper.pdf"
    # 任務列表依建立順序可取
    assert [j.job_id for j in service.list_jobs()] == [job.job_id]


def test_upload_failure_shows_friendly_error(tmp_path: Path):
    _, job = upload_and_translate(tmp_path, FileWritingFakeEngine(error="API key 無效或已過期"))
    view = build_job_card(job)
    assert view.status_label == "失敗"
    assert view.error == "API key 無效或已過期"
    assert view.mono_url is None
