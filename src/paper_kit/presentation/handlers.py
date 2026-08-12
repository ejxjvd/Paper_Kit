"""handlers：UI 薄層邏輯（viewmodel 產生）。純函式、不 import nicegui。

app.py 只做 widget 綁定；這裡的對映可單元測試（application 即 UI 的接縫）。
"""

import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
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
    estimated_label: str | None = None  # 票 08 review：未完成任務顯示「翻之前先估價」
    created_label: str = ""          # 票 08：歷史列表顯示建立時間
    engine_label: str | None = None  # 票 08：顯示用哪個引擎
    can_retry: bool = False          # 票 08：失敗任務可重試
    can_cancel: bool = False         # 票 08：進行中任務可取消
    sensitive: bool = False          # 票 10：機密文件（卡片顯示 🔒）
    ocr: bool = False                # 票 12：掃描件（卡片顯示 🔍）
    pages_label: str = "全文"        # 票 17：歷史表格「頁數」欄（None→「全文」對映在 build_job_card）


def _result_url(files_base: str, job_id: str, result_path: str | None) -> str | None:
    if not result_path:
        return None
    return f"{files_base}/{job_id}/{Path(result_path).name}"


def build_job_card(
    job: TranslationJob,
    files_base: str = "/files",
    usage_label: str | None = None,
    engine_labels: dict[str, str] | None = None,
) -> JobCardView:
    """任務 → 卡片 viewmodel（純函式）。

    engine_labels：engine_id → 顯示名（app 層傳 ENGINE_SPECS 對映；handlers
    保持純函式不碰 infrastructure——spec review 修正：顯示 label 而非 raw id）。
    未知 id（如引擎已下架）回退 raw id。
    """
    running = job.status in (JobStatus.QUEUED, JobStatus.TRANSLATING)
    urls = None
    if job.result is not None:
        mono_url = _result_url(files_base, job.job_id, job.result.mono_path)
        urls = (
            mono_url,
            _result_url(files_base, job.job_id, job.result.dual_path),
            mono_url,
        )
    # spec review：未完成任務也要有成本欄——上傳時存的估算（「翻之前先估價」）
    estimated_label = None
    if usage_label is None and job.estimated_cost is not None:
        estimated_label = f"估算 ${job.estimated_cost}"
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
        estimated_label=estimated_label,
        created_label=datetime.fromtimestamp(job.created_at).strftime("%Y-%m-%d %H:%M"),
        engine_label=(
            engine_labels.get(job.engine_id, job.engine_id) if engine_labels else job.engine_id
        ),
        can_retry=job.can_retry,   # 規則單一真相＝領域轉換表（review 修正）
        can_cancel=job.can_cancel,
        sensitive=job.sensitive,   # 票 10：機密標記顯示（🔒）
        ocr=job.ocr,               # 票 12：掃描件標記顯示（🔍）
        pages_label=job.pages or "全文",  # 票 17：頁數欄（"1-2" 或全文）
    )


def build_batch_zip(
    jobs: list[TranslationJob],
    kind: str,
    dest_dir: str | Path,
) -> Path | None:
    """票 18：勾選任務的 mono／dual 檔打包成 zip（純函式；路由只是薄殼）。

    kind="mono"（僅譯文）或 "dual"（雙語）——兩鍵獨立、都要有（使用者明定
    「雙語不可退化」）。只收完成且有產出的任務；arcname 帶 job_id[:8] 前綴
    防同名 PDF 衝突。全無可打包 → None（UI 提示）。
    """
    files = []
    for job in jobs:
        if job.result is None:
            continue
        path = Path(job.result.mono_path if kind == "mono" else job.result.dual_path)
        if not path.exists():
            continue
        files.append((path, f"{job.job_id[:8]}-{path.name}"))
    if not files:
        return None
    # uuid 前綴：暫存檔名唯一（review 修正——固定名會讓並行下載互相覆寫，
    # 且第一個 response 的送完即刪會刪掉第二個的暫存）
    zip_path = Path(dest_dir) / f"paper-kit-{kind}-{uuid.uuid4().hex[:8]}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in files:
            zf.write(path, arcname)
    return zip_path
