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
    can_delete: bool = False         # #74：終態任務可刪除（清掉舊任務不堆積）
    sensitive: bool = False          # 票 10：機密文件（卡片顯示 🔒）
    ocr: bool = False                # 票 12：掃描件（卡片顯示 🔍）
    from_cache: bool = False         # 票 26：快取命中（引擎未呼叫——卡片顯示 ⚡）
    pages_label: str = "全文"        # 票 17：#27 歷史表格「頁數」欄（「N/M 頁」組字在 build_job_card）
    total_pages: int | None = None   # #27：翻譯頁數（進度框「N/M 頁」的 N）
    pdf_pages: int | None = None     # #27：PDF 總頁數（歷史頁「N/M 頁」的 M）
    pages_raw: str | None = None     # #27：原始選取頁碼（歷史表格 hover 顯示用）


def _result_url(files_base: str, job_id: str, result_path: str | None) -> str | None:
    if not result_path:
        return None
    return f"{files_base}/{job_id}/{Path(result_path).name}"


def _pages_summary(job: TranslationJob) -> str:
    """#27：歷史表格「頁數」欄組字——「N/M 頁」（N＝翻譯頁數、M＝PDF 總頁數）。

    使用者實測：挑 2 頁翻譯歷史頁卻只顯示頁號「29,30」，看不出總頁數；
    改顯示「2/58 頁」。舊任務（無 total_pages）維持既有「選取頁碼／全文」；
    有翻譯頁數無總頁數 → 「N 頁」。
    """
    if job.total_pages:
        if job.pdf_pages:
            return f"{job.total_pages}/{job.pdf_pages} 頁"
        return f"{job.total_pages} 頁"
    return job.pages or "全文"


def build_job_card(
    job: TranslationJob,
    files_base: str = "/files",
    usage_label: str | None = None,
    engine_labels: dict[str, str] | None = None,
    estimated_label: str | None = None,  # 2026-08-13：app 層算好傳入（handlers 純函式不碰 CostService）
) -> JobCardView:
    """任務 → 卡片 viewmodel（純函式）。

    engine_labels：engine_id → 顯示名（app 層傳 ENGINE_SPECS 對映；handlers
    保持純函式不碰 infrastructure——spec review 修正：顯示 label 而非 raw id）。
    未知 id（如引擎已下架）回退 raw id。
    """
    running = job.status in (JobStatus.QUEUED, JobStatus.TRANSLATING)
    # #72：QUEUED 無進度（還沒開始）；TRANSLATING 有引擎進度就顯示、無則 None
    # （UI 對 None 渲染 indeterminate bar）；COMPLETED 固定 100%。
    progress = (
        1.0
        if job.status is JobStatus.COMPLETED
        else (job.progress if job.status is JobStatus.TRANSLATING else None)
    )
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
        progress=progress,
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
        can_delete=job.can_delete,  # #74：非執行中任務可刪除
        sensitive=job.sensitive,   # 票 10：機密標記顯示（🔒）
        ocr=job.ocr,               # 票 12：掃描件標記顯示（🔍）
        from_cache=bool(job.result and job.result.from_cache),  # 票 26：快取命中（⚡）
        pages_label=_pages_summary(job),  # 票 17：#27「N/M 頁」組字（選取頁碼／全文 fallback）
        total_pages=job.total_pages,  # #27：翻譯頁數（進度框「N/M 頁」的 N）
        pdf_pages=job.pdf_pages,      # #27：PDF 總頁數（歷史頁「N/M 頁」的 M）
        pages_raw=job.pages,          # #27：原始選取頁碼（hover 顯示）
    )


def progress_label(view: JobCardView) -> str | None:
    """#15：進度框文字——完成「完成 100% · N/N 頁」；翻譯中「翻譯中 X% · n/N 頁」；
    不確定進度「翻譯中… · 共 N 頁」；無 total_pages（舊任務）頁數部分省略；
    QUEUED 無進度框（#72 明確區分）→ None。

    純函式：UI 只呼叫渲染，組字邏輯在此單一測試點（避免 inline 字串散落）。
    """
    m = view.total_pages
    if view.status is JobStatus.COMPLETED:
        return f"完成 100% · {m}/{m} 頁" if m else "完成 100%"
    if view.status is JobStatus.TRANSLATING:
        if view.progress is not None:
            pct = round(view.progress * 100)
            if m:
                return f"翻譯中 {pct}% · {round(view.progress * m)}/{m} 頁"
            return f"翻譯中 {pct}%"
        return f"翻譯中… · 共 {m} 頁" if m else "翻譯中…"
    return None


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
