"""handlers：UI 薄層邏輯（viewmodel 產生）。純函式、不 import nicegui。

app.py 只做 widget 綁定；這裡的對映可單元測試（application 即 UI 的接縫）。
"""

from dataclasses import dataclass
from pathlib import Path

from paper_kit.domain.translation_job import JobStatus, TranslationJob

STATUS_LABELS = {
    JobStatus.QUEUED: "排隊中",
    JobStatus.TRANSLATING: "翻譯中",
    JobStatus.COMPLETED: "完成",
    JobStatus.FAILED: "失敗",
    JobStatus.CANCELLED: "已取消",
}


@dataclass(frozen=True)
class JobCardView:
    """任務卡片 viewmodel——UI 需要的欄位，一次算好。"""

    job_id: str
    file_name: str
    status: JobStatus
    status_label: str
    is_running: bool
    progress: float | None  # None = 不確定進度（引擎尚無顆粒度回報）
    mono_url: str | None
    dual_url: str | None
    preview_url: str | None
    error: str | None = None
    usage_label: str | None = None   # 票 06：完成後顯示估算 vs 實際成本


def _result_url(files_base: str, job_id: str, result_path: str | None) -> str | None:
    if not result_path:
        return None
    return f"{files_base}/{job_id}/{Path(result_path).name}"


def build_job_card(
    job: TranslationJob, files_base: str = "/files", usage_label: str | None = None
) -> JobCardView:
    """任務 → 卡片 viewmodel（純函式）。"""
    running = job.status in (JobStatus.QUEUED, JobStatus.TRANSLATING)
    urls = None
    if job.result is not None:
        mono_url = _result_url(files_base, job.job_id, job.result.mono_path)
        urls = (
            mono_url,
            _result_url(files_base, job.job_id, job.result.dual_path),
            mono_url,
        )
    return JobCardView(
        job_id=job.job_id,
        file_name=Path(job.source_path).name if job.source_path else "",
        status=job.status,
        status_label=STATUS_LABELS[job.status],
        is_running=running,
        progress=1.0 if job.status is JobStatus.COMPLETED else None,
        mono_url=urls[0] if urls else None,
        dual_url=urls[1] if urls else None,
        preview_url=urls[2] if urls else None,
        error=job.error,
        usage_label=usage_label,
    )
