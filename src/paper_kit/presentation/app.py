"""Paper_Kit NiceGUI 介面（薄層：widget ↔ handlers ↔ JobService）。

widget 邏輯盡量薄——狀態對映在 handlers（純函式可測）、業務在 application。
NiceGUI 走 WebSocket 推送 → 事件驅動、無整頁重載（ui.timer 輪詢狀態）。

啟動：`uv run paper-kit` → http://localhost:8080（設定頁 /settings）
"""

import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace

import pypdf  # #85：選檔即讀頁數（BabelDOC 風格「N of M」頁面範圍下拉）

from nicegui.elements.upload_files import FileUpload  # 票 21：拖放僅選檔（pending）

from fastapi.responses import FileResponse, JSONResponse  # 票 18：批量下載 zip 路由
from nicegui import app, ui
from starlette.background import BackgroundTask  # 票 18：zip 送完即刪

from paper_kit.application.cost_service import CostService
from paper_kit.application.errors import to_user_message
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.ocr import (  # 票 12：掃描件 OCR
    OcrService,
    has_text_layer,
    is_pdf_path,
)
from paper_kit.application.pages import parse_pages
from paper_kit.application.ports import EngineError, TranslationEnginePort
from paper_kit.application.settings_service import SettingsService
from paper_kit.application.translation_cache import TranslationCache  # 票 25：設定頁快取區
from paper_kit.domain.translation_job import InvalidTransition, JobStatus, TranslationJob
from paper_kit.domain.cost_calculator import CostEstimate
from paper_kit.domain.glossary import GlossaryFormatError
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS, build_engine
from paper_kit.infrastructure.glossary_repo import GlossaryNameError, GlossaryRepository
from paper_kit.infrastructure.job_repo import SqliteJobRepository
from paper_kit.infrastructure.logging_setup import format_log_line, recent_log_entries, setup_logging
from paper_kit.infrastructure.rapidocr_adapter import RapidOcrAdapter  # 票 12：本機 OCR
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.handlers import JobCardView, build_batch_zip, build_job_card
from paper_kit.presentation.theme import apply_theme

APP_DIR = Path.home() / ".paper_kit"
OUTPUTS_DIR = APP_DIR / "outputs"
GLOSSARIES_DIR = APP_DIR / "glossaries"
DB_PATH = APP_DIR / "paper_kit.db"
FILES_BASE = "/files"

BADGE_COLORS = {
    JobStatus.QUEUED: "blue-grey",
    JobStatus.TRANSLATING: "indigo",
    JobStatus.COMPLETED: "green",
    JobStatus.FAILED: "red",
    JobStatus.CANCELLED: "grey",
}

# 票 19：主頁引擎三選卡（ticket 明定三支 PDF 主引擎；latex／ppt-vision 走特化路線）
ENGINE_CARDS = (
    ("siliconflow", "gemma 視覺模型（圖表精準；預設引擎）"),
    ("deepseek", "純文字模型（機密文件唯一可用）"),
    ("babeldoc", "OpenAI 相容雲端（DeepSeek 後端）"),
)


def _real_path(view_url: str) -> Path:
    """/files/<job_id>/<name> → 磁碟真實路徑（下載用）。"""
    return OUTPUTS_DIR / view_url.split(FILES_BASE + "/", 1)[1]


def _download_output(view_url: str) -> None:
    """#83：產出檔不存在 → 不下載、改 ui.notify 警示。

    真因鏈末端（2026-08-13 實測）：ghost COMPLETED（引擎零產出＋假路徑）或
    產出遺失時，ui.download(缺檔路徑) → NiceGUI helpers.is_file=False → fallback
    from_url → 瀏覽器 fetch 失敗、服務端回 HTML →「失敗 - 沒有檔案」+ .htm。
    守衛：檔案真實存在才下載（mono/dual 皆經此函）。
    """
    path = _real_path(view_url)
    if not path.is_file():
        ui.notify(f"檔案不存在：{path.name}（產出遺失或未生成）", type="warning")
        return
    ui.download(str(path))


def _resolve_task_engine(
    settings: SettingsService, engine_id: str | None
) -> tuple[str, TranslationEnginePort]:
    """票 19：本任務引擎解析——override（主頁引擎卡點選）或設定頁 global。

    override 缺 key 給相同友善錯誤（不 fallback 到 global——使用者明確選了
    引擎卻被換成別支翻譯是靜默誤動作）。回傳 (engine_id, engine)。
    """
    if engine_id is None:
        return settings.engine_id(), settings.resolve_engine()
    spec = ENGINE_SPECS.get(engine_id)
    if spec is None:
        raise EngineError(f"未知引擎：{engine_id}")
    if spec.needs_key and not settings.api_key(spec.id):
        raise EngineError(f"尚未設定 {spec.label} 的 API key（設定頁填入後再翻譯）")
    return spec.id, build_engine(spec, api_key=settings.api_key(spec.id))


def _engine_picker(pick, eid: str):
    """票 19：0 參數 picker factory——`lambda eid=eid:` 會被 event 參數覆寫
    （handle_event 依簽名參數數目傳 event；1 參數 lambda 收到的是事件物件）。
    迴圈內閉包捕獲也要即時綁定（否則三個 handler 全看最後一個 eid）。
    """
    def pick_engine() -> None:
        pick(eid)
    return pick_engine


def _pages_for_file(selected: list[str], file_pages: int) -> str | None:
    """#85：頁面範圍（多選頁碼）套用單一檔案——選中頁碼 ∩ 1..file_pages。

    空選擇／全選 → None（全部頁面）；檔案頁數不足 → 交集為空 → None（全文，
    不把越界頁碼漏到引擎才爆）。回傳 "1,3,5" 式頁面範圍（parse_pages 合法格式）。"""
    if not selected:
        return None
    pages = sorted({int(p) for p in selected if 1 <= int(p) <= file_pages})
    if not pages or len(pages) >= file_pages:
        return None  # 空交集或全選＝全部頁面
    return ",".join(str(p) for p in pages)


# #85 切片D：免費額度資訊條——BabelDOC 風格（沉浸式翻譯 UI 的 0/500,000 Tokens）。
# 本地工具無真正額度──聚合已完成任務 tokens 顯示「已用」參考值，不強制限流。
FREE_TOKEN_QUOTA = 500_000


def _aggregate_used_tokens(jobs: list[TranslationJob]) -> int:
    """已用 tokens＝全部已完成任務 in+out 加總（失敗/排隊/翻譯中不計）。"""
    return sum(
        (job.result.input_tokens or 0) + (job.result.output_tokens or 0)
        for job in jobs
        if job.status is JobStatus.COMPLETED and job.result
    )


def _quota_label(used: int) -> str:
    """額度條文字：`免費額度 10,000/500,000 Tokens`（千分位）。"""
    return f"免費額度 {used:,}/{FREE_TOKEN_QUOTA:,} Tokens"


def _start_job(
    service: JobService,
    settings: SettingsService,
    cost: CostService,
    glossaries: GlossaryService,
    file_path: Path,
    file_name: str,
    pages_text: str = "",
    sensitive: bool = False,
    ocr: bool = False,
    engine_id: str | None = None,    # 票 19：引擎卡點選（None=設定頁 global）
    target_lang: str | None = None,  # 票 19：語言下拉就地選（None=設定頁值）
    only_selected_pages: bool = True,  # #85：僅翻譯選中頁面 toggle
    # #85 切片C：babeldoc 進階選項（僅 babeldoc 引擎消費；其他引擎忽略）
    enhance_compatibility: bool = False,
    merge_alternating_line_numbers: bool = True,
    remove_non_formula_lines: bool = False,
    font_family: str = "serif",
) -> bool:
    """送暫存檔建立翻譯任務。成功（含引擎已啟動）回 True——呼叫方清理暫存。

    #85 改版：暫存寫入從「選檔時」提前發生（auto_upload=True 暫存流程）——
    本函只收已暫存的 file_path，不再碰 FileUpload。"""
    # 票 07：頁面範圍輸入驗證（空白=全部）；非法格式不建任務（驗證先於建任務）
    try:
        pages = parse_pages(pages_text)
    except ValueError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return False
    try:
        engine_id, engine = _resolve_task_engine(settings, engine_id)
    except EngineError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return False
    # 票 10 紅線：機密文件＋視覺引擎 → 連任務都不建（UI 早攔，service.start 再兜底）。
    # .get()：未知引擎保守視為視覺（機密 fail-closed）
    spec = ENGINE_SPECS.get(engine_id)
    if sensitive and (spec is None or not spec.sensitive_ok):
        ui.notify("機密文件只可使用 DeepSeek 純文字引擎（先到設定切換引擎）", type="negative")
        return False
    # 票 14 spec review：OCR 只適用 PDF——勾了但上傳非 PDF → 警告＋忽略旗標
    # （ensure_text_layer 同層兜底安全跳過；視覺路徑不需要文字層）
    if ocr and not is_pdf_path(file_name):
        ui.notify("🔍 掃描件 OCR 僅適用 PDF——已忽略（PPT 走視覺翻譯）", type="warning")
        ocr = False
    job = service.create_job(
        file_path,
        target_lang=target_lang or settings.target_lang(),  # 票 19：下拉就地選覆寫
        pages=pages,
        output_dir=settings.output_dir(),
        sensitive=sensitive,
        ocr=ocr,
        only_selected_pages=only_selected_pages,  # #85：僅翻譯選中頁面
        # #85 切片C：babeldoc 進階選項透傳（其他引擎忽略）
        enhance_compatibility=enhance_compatibility,
        merge_alternating_line_numbers=merge_alternating_line_numbers,
        remove_non_formula_lines=remove_non_formula_lines,
        font_family=font_family,
    )
    # 票 12 AC1：掃描件偵測——無文字層且未勾 OCR → 提示（照常建立，使用者可重試）。
    # 票 14：只對 PDF 偵測（pptx 上傳不誤報掃描件——has_text_layer 對非 PDF 回 False）
    if (
        not ocr
        and job.source_path
        and is_pdf_path(job.source_path)
        and not has_text_layer(job.source_path)
    ):
        ui.notify(
            "⚠️ 偵測為掃描件（無文字層）——翻譯可能產出空白；建議勾選 🔍 OCR 重試",
            type="warning",
        )
    # 票 05：挑選的術語表組合＋自動提取開關隨任務記錄（之後改設定不影響舊任務）
    names = settings.selected_glossary_names(glossaries.list_glossaries())  # 預設全選
    job.glossary_files = glossaries.paths_for(names)
    job.auto_extract = settings.auto_extract()
    # 票 07：指定頁面範圍時估價按範圍縮放（規格書 story 4「只為需要的部分付費」）
    # 2026-08-13：挑選術語表 → 預估 tokens 依 ×1.57 倍率更新（research 實測值）
    est = cost.estimate_for_pdf(
        engine_id, file_path, pages=pages, glossary=bool(job.glossary_files)
    )
    if est is not None:
        job.estimated_cost = est.cost  # 存下前置估算：完成後比對的是「使用者看到的」數字
        job.estimated_tokens = est.total_tokens  # 2026-08-13：UI 預估顯示用（隨任務持久化）
    _notify_estimate(cost, engine_id, est)
    ui.notify(f"任務已建立：{file_name}", type="positive")
    # 票 10：engine_allows_sensitive 由 UI 層查 ENGINE_SPECS 傳入（service 兜底防衛）
    service.start(
        job.job_id, engine, engine_id=engine_id,
        engine_allows_sensitive=spec.sensitive_ok if spec else False,
    )
    return True


def _notify_estimate(
    cost: CostService, engine_id: str, est: CostEstimate | None
) -> None:
    """票 06：上傳時顯示成本估算（頁數、引擎、單價明細）。不可估就靜默跳過。

    2026-08-13 改版：顯示預估 tokens 數＋美元/台幣並列（成本比較報告風格）；
    est.pages 保留原頁數（術語表倍率後不可用 total//per_page 倒推）。"""
    if est is None:
        return
    cfg = cost.pricing_for(engine_id)
    if est.pages <= 0:
        return
    if cfg.input_per_1k == 0 and cfg.output_per_1k == 0:
        ui.notify(
            f"已估算：{est.pages} 頁 · {engine_id} ≈ {est.total_tokens:,} tokens · 免費引擎無費用",
            type="info",
        )
    else:
        ui.notify(
            f"已估算：{est.pages} 頁 · {engine_id} ≈ {est.total_tokens:,} tokens"
            f" ≈ {cost.usd_twd_label(est.cost)}",
            type="info",
        )


def _retry_job(service: JobService, settings: SettingsService, job_id: str) -> None:
    """票 08：失敗任務重試（回 queued 再跑，不需重新上傳）。"""
    try:
        engine = settings.resolve_engine()
    except EngineError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    try:
        engine_id = settings.engine_id()
        # 票 10：機密任務重試也用目前的引擎判定（視覺引擎 → ValueError 拒絕）。
        # .get()：未知引擎保守視為視覺（機密 fail-closed）
        spec = ENGINE_SPECS.get(engine_id)
        service.retry(
            job_id, engine, engine_id=engine_id,
            engine_allows_sensitive=spec.sensitive_ok if spec else False,
        )
        ui.notify("已重新排隊", type="positive")
    except InvalidTransition as exc:
        ui.notify(to_user_message(exc), type="negative")
    except ValueError as exc:
        ui.notify(to_user_message(exc), type="negative")  # 票 10：機密＋視覺引擎（統一入口）
    except KeyError:
        ui.notify("找不到此任務", type="negative")  # KeyError 語境由呼叫端決定（票 09 review）


def _delete_jobs(service: JobService, ids: list[str]) -> tuple[int, int]:
    """票 18：批量刪除——回傳 (成功數, 執行中被拒數)；執行中跳過不中斷其餘。

    module-level（standards review：巢狀 handler 的迴圈邏輯不可測；UI 層只
    notify＋重繪）。執行中任務維持原狀，由呼叫端提示。
    """
    deleted = blocked = 0
    for jid in ids:
        try:
            service.delete(jid)
            deleted += 1
        except ValueError:
            blocked += 1
    return deleted, blocked


def _confirm_delete_one(
    service: JobService, job_id: str, dialog, state: dict
) -> None:
    """#74：主頁卡片單一刪除——頁面級確認 dialog 的開啟（破壞性：含輸出檔）。

    #82 修復：dialog 為 `_index_page` 建置的**頁面級單例**（重複使用）。
    舊版在此 handler 內 `with ui.dialog()` 建立——NiceGUI handle_event 以
    sender 的 parent slot（＝卡片 slot，events.py）執行 handler，Dialog
    建構時的 canary 元素掛該 slot；卡片每 1s 被 _refresh 的 cards.clear()
    刪除 → canary finalize 連坐 dialog.delete()＝「刪除欄位不到 2 秒就消失」
    （使用者 3 次回報）。頁面級單例的 canary 掛 content slot（永存）不隨
    卡片死；執行中任務理論上不會出現此按鈕（view.can_delete 已擋），
    service.delete 紅線仍會兜底。
    """
    state["job_id"] = job_id
    dialog.open()


def _do_delete_one(service: JobService, job_id: str) -> None:
    """#74：單一刪除執行——重用 _delete_jobs 的 (deleted, blocked) 語義。"""
    deleted, blocked = _delete_jobs(service, [job_id])
    if blocked:
        ui.notify("執行中的任務無法刪除", type="warning")
    elif deleted:
        ui.notify("已刪除任務", type="positive")


def _batch_retry(service: JobService, settings: SettingsService, ids: list[str]) -> int:
    """票 18：批量重試——只處理可重試任務（can_retry），回傳重試數。"""
    retried = 0
    for jid in ids:
        job = next((j for j in service.list_jobs() if j.job_id == jid), None)
        if job is not None and job.can_retry:
            _retry_job(service, settings, jid)
            retried += 1
    return retried


def _batch_cancel(service: JobService, ids: list[str]) -> int:
    """票 18：批量取消——只處理可取消任務（can_cancel），回傳取消數。"""
    cancelled = 0
    for jid in ids:
        job = next((j for j in service.list_jobs() if j.job_id == jid), None)
        if job is not None and job.can_cancel:
            _cancel_job(service, jid)
            cancelled += 1
    return cancelled


def _cancel_job(service: JobService, job_id: str) -> None:
    """票 08：進行中任務取消（狀態→cancelled、產出拋棄）。"""
    try:
        service.cancel(job_id)
        ui.notify("已取消", type="warning")
    except InvalidTransition as exc:
        ui.notify(to_user_message(exc), type="negative")
    except KeyError:
        ui.notify("找不到此任務", type="negative")  # KeyError 語境由呼叫端決定（票 09 review）


def _render_card(
    view: JobCardView,
    service: JobService,
    settings: SettingsService,
    delete_dialog=None,
    delete_state: dict | None = None,
    preview_dialog=None,
    preview_box=None,
) -> None:
    # 票 19 review：marker 供測試鎖定任務卡——引擎卡也有 spec.label，
    # 純 content 匹配會假陽性（被引擎卡自身滿足），任務卡必須可獨立定位
    with ui.card().mark("job-card").classes("w-full pk-card"):  # 票 11：卡片主題 class（圓角/陰影/背景變數）
        with ui.row().classes("items-center justify-between w-full"):
            with ui.column().classes("gap-0"):
                with ui.row().classes("items-center gap-2"):
                    ui.label(view.file_name).classes("text-lg font-semibold")
                    if view.sensitive:  # 票 10：機密標記顯示
                        ui.badge("🔒 機密").props("outline color=orange")
                    if view.ocr:  # 票 12：掃描件標記顯示
                        ui.badge("🔍 掃描件").props("outline color=teal")
                # 票 08：歷史卡片顯示建立時間＋引擎
                meta = f"任務 {view.job_id[:8]} · {view.created_label}"
                if view.engine_label:
                    meta += f" · {view.engine_label}"
                ui.label(meta).classes("text-xs pk-meta")  # 票 11：muted 變數
            ui.badge(view.status_label).props(f"color={BADGE_COLORS[view.status]}")
        # #72：排隊中＝還沒開始（不顯示進度條，與翻譯中明確區分——使用者要求
        # 「排隊中跟翻譯中完全不同」）；翻譯中＝有引擎進度顯示確定值、無則
        # indeterminate（動畫＝正在跑）；完成＝100%。
        if view.status is JobStatus.QUEUED:
            pass
        elif view.status is JobStatus.TRANSLATING:
            if view.progress is not None:
                # 票 11：進度條納入主題變數（深色下保持對比）
                ui.linear_progress(value=view.progress).classes("w-full pk-progress")
            else:
                ui.linear_progress(value=0.5).props("indeterminate").classes("w-full pk-progress")
        elif view.status is JobStatus.COMPLETED:
            ui.linear_progress(value=1.0).classes("w-full pk-progress")
        if view.error:
            ui.label(f"錯誤：{view.error}").classes("pk-error")  # 票 11：錯誤語意色走主題變數
        # 票 08 review：完成任務顯示「估算 vs 實際」，未完成顯示上傳時估價
        cost_label = view.usage_label or view.estimated_label
        if cost_label:
            ui.label(cost_label).classes("text-sm pk-cost")  # 票 11：成本排版變數
        with ui.row().classes("items-center"):
            if view.can_retry:
                ui.button(
                    "↻ 重試",
                    on_click=lambda: _retry_job(service, settings, view.job_id),
                ).props("outline")
            if view.can_cancel:
                ui.button(
                    "✕ 取消",
                    on_click=lambda: _cancel_job(service, view.job_id),
                ).props("outline negative")
            if view.mono_url:
                ui.button(
                    "下載 mono",
                    on_click=lambda: _download_output(view.mono_url),  # #83 守衛
                ).props("outline")
                if view.dual_url:  # 票 14：視覺路徑單一產出（mono=注記版，無 dual）
                    ui.button(
                        "下載 dual",
                        on_click=lambda: _download_output(view.dual_url),  # #83 守衛
                    ).props("outline")
                ui.button(
                    "瀏覽器內預覽",
                    on_click=lambda: _preview(preview_dialog, preview_box, view.preview_url),
                )
            if view.can_delete:  # #74：終態任務可刪除——清掉舊任務不堆積主頁
                ui.button(
                    "🗑 刪除",
                    on_click=lambda: _confirm_delete_one(service, view.job_id, delete_dialog, delete_state),
                ).props("outline color=negative")


def _preview(dialog, box, url: str) -> None:
    """#82 修復：預覽 dialog 為頁面級單例（同刪除 dialog 機制——handler 內
    重建 dialog 的 canary 會隨卡片 clear 被刪）；ui.pdf 在 NiceGUI 3.15 不存在
    （點擊時靜默 AttributeError）→ 改用 ui.html 包 iframe 渲染 PDF。
    """
    box.set_content(
        f'<iframe src="{url}" class="w-full h-full" '
        'style="border:0;min-height:70vh"></iframe>'
    )
    dialog.open()


def _refresh(
    cards,
    service: JobService,
    cost: CostService,
    settings: SettingsService,
    memo: dict,
    delete_dialog=None,
    delete_state: dict | None = None,
    preview_dialog=None,
    preview_box=None,
    quota_label=None,  # #85 切片D：免費額度資訊條（1s 輪詢同步聚合值）
) -> None:
    cards.clear()
    # #85 切片D：已用 tokens 聚合（已完成任務 in+out）→ 額度條文字
    if quota_label is not None:
        quota_label.set_text(_quota_label(_aggregate_used_tokens(service.list_jobs())))
    # spec review：引擎欄顯示 label（「DeepSeek（純文字…）」）不是 raw id
    engine_labels = _engine_label_map()
    for job in service.list_jobs():
        # memo：完成任務只算一次成本標籤（1s 輪詢下避免每輪重讀 PDF 頁數）
        if job.status is JobStatus.COMPLETED and job.job_id not in memo:
            memo[job.job_id] = cost.usage_label(job)
        # 2026-08-13：未完成任務預估標籤每輪即算——純欄位讀取無 IO（估 tokens＋美元/台幣）
        estimated_label = (
            cost.estimated_label(job) if job.status is not JobStatus.COMPLETED else None
        )
        # 2026-08-12 使用者實測 bug：卡片必須進 cards 容器——之前落在頁面 root slot，
        # 每秒輪詢 clear() 清不到、卡片＋錯誤行無限疊加。
        with cards:
            _render_card(
                build_job_card(
                    job,
                    usage_label=memo.get(job.job_id),
                    estimated_label=estimated_label,
                    engine_labels=engine_labels,
                ),
                service,
                settings,
                delete_dialog,
                delete_state,
                preview_dialog,
                preview_box,
            )


def _mask_key(key: str) -> str:
    """票 20：已存 key 回顯遮罩——前 6 字符＋其餘星號；短 key（≤6）全星號。

    短 key 全遮（前 6 明文是規格明定；短 key 全顯示＝整把 key 曝光）。
    input 顯示遮罩；儲存時值等於遮罩＝未修改（防遮罩寫回，見 _save_engine_key）。
    """
    if not key:
        return ""
    if len(key) <= 6:
        return "*" * len(key)
    return key[:6] + "*" * (len(key) - 6)


def _save_engine_choice(settings: SettingsService, engine_id: str) -> None:
    """票 20：儲存「預設引擎」選擇（key 已由各引擎卡獨立管理，不再經此寫）。"""
    try:
        settings.set_engine(engine_id)
        ui.notify("引擎設定已儲存", type="positive")
    except KeyError:
        ui.notify("未知引擎", type="negative")


def _save_engine_key(settings: SettingsService, eid: str, key_input) -> None:
    """票 20：0 參數 factory（`lambda eid=eid:` 會被 event 覆寫，票 19 教訓）。

    防遮罩寫回：input 回顯的是遮罩——值等於遮罩視為未修改，不得存成 key。
    """
    def save() -> None:
        current = settings.api_key(eid)
        value = key_input.value
        if value and value != _mask_key(current):
            settings.set_api_key(eid, value)
        ui.notify(f"已儲存 {ENGINE_SPECS[eid].label} 的 API key", type="positive")
    return save


def _clear_engine_key(settings: SettingsService, eid: str, key_input) -> None:
    """票 20：0 參數 factory——清除該引擎 key（清空後 api_key 回傳空）。

    spec review（票 20）：一併清 input 顯示值——否則殘留遮罩在「清除後再按儲存」
    會被 `_save_engine_key` 當新 key 寫回（current="" 時任何值都過防遮罩判斷）。
    """
    def clear() -> None:
        settings.set_api_key(eid, "")
        key_input.value = ""
        ui.notify(f"已清除 {ENGINE_SPECS[eid].label} 的 API key", type="warning")
    return clear


def _cache_stats_label(cache: TranslationCache) -> str:
    """「快取 N 筆 · X MB」；stats() 排除索引 DB，只算實際產物。"""
    count, total = cache.stats()
    return f"快取 {count} 筆 · {total / (1024 * 1024):.1f} MB"


def _settings_page(
    settings: SettingsService,
    cost: CostService,
    glossaries: GlossaryService,
    cache: TranslationCache | None = None,  # 票 25：快取區（None＝無頭模式不渲染）
) -> None:
    @ui.page("/settings")
    def settings_page():
        ui.page_title("Paper_Kit 設定")
        # 票 16：統一頁框——側欄（設定 active）；主題切換收進 frame
        nav = [(l, p, _nav_active(p, "/settings")) for l, p in SIDEBAR_NAV]
        app_frame("⚙️ Paper_Kit 設定", settings, nav)
        # 2026-08-12 bug 修復：bind_value_to(locals(), ...) 寫入的是 locals() dict，
        # Python 名稱解析（LOAD_GLOBAL）看不見它——函數內讀取的變數必須顯式
        # 初始化，否則首次渲染（pricing_for(engine_id)）與「不修改直接儲存」
        # 的 lambda 都會 NameError（真實 UI 500，實測 traceback app.py:326）。
        engine_id = settings.engine_id()
        target_lang = settings.target_lang()
        output_dir = settings.output_dir()
        base = cost.pricing_for(engine_id)
        in_price = str(base.input_per_1k)
        out_price = str(base.output_per_1k)
        per_page = str(base.per_page_tokens)
        rate = str(cost.usd_twd_rate())  # 2026-08-13：匯率顯示用（default 32，可改）
        # 票 16 spec review：殘留的原 header 已刪（app_frame 統一頂部標題）
        with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
            with ui.card().classes("w-full"):
                ui.label("翻譯引擎").classes("font-bold")
                ui.select(
                    _engine_label_map(),
                    value=engine_id,
                    label="預設引擎（主頁引擎卡可為單一任務另選）",
                ).classes("w-full").bind_value_to(locals(), "engine_id")
                ui.button(
                    "儲存引擎設定",
                    on_click=lambda: _save_engine_choice(settings, engine_id),
                ).props("outline")
            # 票 20：每引擎獨立 API key（BYOK——交付他人時各自用自己帳號的 key）
            with ui.card().classes("w-full"):
                ui.label("引擎 API keys").classes("font-bold")
                ui.label(
                    "各自用自己的 key（存本機 SQLite，不入 repo/log）；已存 key 僅顯示遮罩。"
                ).classes("text-xs text-grey-6")
                for eid, desc in ENGINE_CARDS:
                    spec = ENGINE_SPECS[eid]
                    with ui.card().mark(f"engine-key-{eid}").classes("w-full gap-2"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(spec.label).classes("font-semibold")
                            ui.badge("已設定" if settings.api_key(eid) else "未設定 key")
                        ui.label(desc).classes("text-xs text-grey-7")
                        key_input = ui.input(
                            "API key",
                            value=_mask_key(settings.api_key(eid)),
                            password=True,
                            password_toggle_button=True,
                        ).classes("w-full").mark(f"engine-key-input-{eid}")
                        with ui.row().classes("gap-2"):
                            ui.button(
                                "儲存 key",
                                on_click=_save_engine_key(settings, eid, key_input),
                            ).props("outline").mark(f"engine-key-save-{eid}")
                            ui.button(
                                "清除",
                                on_click=_clear_engine_key(settings, eid, key_input),
                            ).props("outline flat color=negative").mark(f"engine-key-clear-{eid}")
            with ui.card().classes("w-full"):
                ui.label("預設值").classes("font-bold")
                ui.input(
                    "目標語言（如 zh-TW）",
                    value=target_lang,
                ).classes("w-full").bind_value_to(locals(), "target_lang")
                ui.input(
                    "輸出目錄（空白 = ~/.paper_kit/outputs）",
                    value=output_dir,
                ).classes("w-full").bind_value_to(locals(), "output_dir")
                ui.button(
                    "儲存預設",
                    on_click=lambda: _save_defaults(settings, target_lang, output_dir),
                ).props("outline")
            with ui.card().classes("w-full"):
                ui.label("引擎單價（USD / 1K tokens）").classes("font-bold")
                ui.label("票 06：DeepSeek 漲價只需改這裡（單價是設定不是寫死）").classes(
                    "text-xs text-grey-6"
                )
                ui.input(
                    "input 單價",
                    value=in_price,
                ).classes("w-full").bind_value_to(locals(), "in_price")
                ui.input(
                    "output 單價",
                    value=out_price,
                ).classes("w-full").bind_value_to(locals(), "out_price")
                ui.input(
                    "每頁 token 基準",
                    value=per_page,
                ).classes("w-full").bind_value_to(locals(), "per_page")
                ui.input(
                    "匯率 USD→TWD（成本顯示換算用；default 32）",
                    value=rate,
                ).classes("w-full").bind_value_to(locals(), "rate")
                ui.button(
                    "儲存單價（目前選定的引擎）",
                    on_click=lambda: _save_pricing(cost, engine_id, in_price, out_price, per_page, rate),
                ).props("outline")
            with ui.card().classes("w-full"):
                ui.label("術語表庫").classes("font-bold")
                ui.label("票 05：多份術語表各自命名；翻譯前挑選套用哪些。CSV 標頭：source,target[,tgt_lng]").classes(
                    "text-xs text-grey-6"
                )
                glossary_select = ui.select(
                    glossaries.list_glossaries(),
                    value=settings.selected_glossary_names(glossaries.list_glossaries()),
                    multiple=True,
                    label="翻譯時套用的術語表（預設全選；勾選即生效）",
                ).classes("w-full")
                glossary_select.on_value_change(
                    lambda: settings.set_selected_glossaries(list(glossary_select.value))
                )
                ui.switch(
                    "自動術語提取（--term-siliconflow，Kimi 角色原生版）",
                    value=settings.auto_extract(),
                ).on_value_change(lambda e: settings.set_auto_extract(e.value))
                ui.upload(
                    label="匯入術語表 CSV（檔名＝術語表名）",
                    auto_upload=True,
                    on_upload=lambda e: _import_glossary(
                        glossaries, settings, glossary_select, edit_select, e
                    ),
                ).classes("w-full")
                new_name_input = ui.input("新術語表名稱").classes("w-full")
                ui.button(
                    "新增術語表",
                    on_click=lambda: _create_glossary(
                        glossaries, glossary_select, edit_select, new_name_input
                    ),
                ).props("outline")
                ui.separator()
                ui.label("編輯術語表").classes("font-bold")
                edit_select = ui.select(
                    glossaries.list_glossaries(),
                    value=None,
                    label="要編輯哪一份（顯示下面的列）",
                ).classes("w-full")
                edit_select.on_value_change(
                    lambda e: _render_entries(glossaries, entries_box, e.value)
                )
                rename_to_input = ui.input("改名為（選定後填入再按）").classes("w-full")
                with ui.row().classes("w-full items-center gap-2"):
                    ui.button(
                        "改名",
                        on_click=lambda: _rename_glossary(
                            glossaries, settings, glossary_select, edit_select,
                            edit_select.value, rename_to_input, entries_box,
                        ),
                    ).props("outline")
                    ui.button(
                        "刪除選定術語表",
                        on_click=lambda: _delete_glossary(
                            glossaries, settings, glossary_select, edit_select,
                            edit_select.value, entries_box,
                        ),
                    ).props("outline flat color=red")
                entries_box = ui.column().classes("w-full gap-1")
                with ui.row().classes("w-full items-center gap-2"):
                    src_input = ui.input("source").props("dense").classes("flex-1")
                    tgt_input = ui.input("target").props("dense").classes("flex-1")
                    ui.button(
                        "新增術語列",
                        on_click=lambda: _add_entry(
                            glossaries, edit_select.value, src_input, tgt_input, entries_box
                        ),
                    ).props("outline")
            # 票 25：翻譯快取區（開關＋統計＋清除）——cache 未注入（無頭）就不渲染
            if cache is not None:
                with ui.card().classes("w-full"):
                    ui.label("翻譯快取").classes("font-bold")
                    ui.label(
                        "票 24：同一檔案＋引擎＋設定再次翻譯＝直接回傳快取結果（省錢不花錢）"
                    ).classes("text-xs text-grey-6")
                    cache_stats_label = ui.label(_cache_stats_label(cache)).classes(
                        "text-sm text-grey-7"
                    )

                    def _refresh_cache_stats() -> None:
                        cache_stats_label.set_text(_cache_stats_label(cache))

                    def _toggle_cache(e) -> None:
                        # 開關即時生效：runtime cache.enabled＋持久化（JobService
                        # 每任務查 fingerprint 前檢查 enabled——不需重啟）
                        cache.enabled = bool(e.value)
                        settings.set_cache_enabled(bool(e.value))

                    ui.switch(
                        "啟用翻譯快取",
                        value=cache.enabled,
                    ).on_value_change(_toggle_cache)
                    ui.button(
                        "清除快取",
                        on_click=lambda: (
                            cache.clear(),
                            _refresh_cache_stats(),
                            ui.notify("快取已清除", type="positive"),
                        ),
                    ).props("outline")


def _save_defaults(settings: SettingsService, target_lang: str, output_dir: str) -> None:
    settings.set_target_lang(target_lang.strip() or "zh-TW")
    settings.set_output_dir(output_dir.strip())
    ui.notify("預設已儲存", type="positive")


# ── 票 05：術語表庫 UI ─────────────────────────────────────────


def _sync_glossary_pickers(
    glossaries: GlossaryService,
    glossary_select,
    edit_select,
    keep: list[str],
) -> None:
    """CRUD 後同步兩個選擇控件為最新術語表名（keep 之外的新名不自動選）。"""
    names = glossaries.list_glossaries()
    glossary_select.set_options(names, value=[n for n in keep if n in names])
    edit_select.set_options(names, value=edit_select.value if edit_select.value in names else None)


async def _import_glossary(
    glossaries: GlossaryService,
    settings: SettingsService,
    glossary_select,
    edit_select,
    e,
) -> None:
    """CSV 上傳：檔名＝術語表名；缺 source/target 標頭顯示明確錯誤（不崩潰）。"""
    name = Path(e.file.name).stem.strip() or "匯入"
    raw = await e.file.read()
    try:
        text = raw.decode("utf-8-sig")  # 吃 Excel 的 BOM
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp950")  # Big5 正體中文（本機環境常見）
        except UnicodeDecodeError:
            ui.notify("CSV 編碼無法識別（需 UTF-8 或 Big5）", type="negative")
            return
    try:
        count = glossaries.import_csv(name, text, target_lang=settings.target_lang())
    except (GlossaryFormatError, GlossaryNameError) as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    ui.notify(f"已匯入 {name}（{count} 條）", type="positive")
    _sync_glossary_pickers(
        glossaries, glossary_select, edit_select, list(glossary_select.value) + [name]
    )


def _create_glossary(
    glossaries: GlossaryService, glossary_select, edit_select, new_name_input
) -> None:
    name = new_name_input.value.strip()
    if not name:
        ui.notify("先填新術語表名稱", type="negative")
        return
    try:
        glossaries.create_glossary(name)
    except (GlossaryNameError, OSError) as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    ui.notify(f"已建立 {name}", type="positive")
    new_name_input.set_value("")
    _sync_glossary_pickers(
        glossaries, glossary_select, edit_select, list(glossary_select.value) + [name]
    )


def _delete_glossary(
    glossaries: GlossaryService,
    settings: SettingsService,
    glossary_select,
    edit_select,
    name,
    entries_box,
) -> None:
    if not name:
        ui.notify("先選要刪除的術語表", type="negative")
        return
    try:
        glossaries.delete_glossary(name)
    except KeyError:
        return
    ui.notify(f"已刪除 {name}", type="negative")
    keep = [n for n in glossary_select.value if n != name]
    stored = settings.selected_glossaries()  # stored 選擇同步：刪掉的名字不再引用
    if stored is not None:
        settings.set_selected_glossaries([n for n in stored if n != name])
    _sync_glossary_pickers(glossaries, glossary_select, edit_select, keep)
    _render_entries(glossaries, entries_box, None)


def _rename_glossary(
    glossaries: GlossaryService,
    settings: SettingsService,
    glossary_select,
    edit_select,
    name,
    rename_to_input,
    entries_box,
) -> None:
    if not name:
        ui.notify("先選要改名的術語表", type="negative")
        return
    new = rename_to_input.value.strip()
    try:
        glossaries.rename_glossary(name, new)
    except (GlossaryNameError, OSError) as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    except KeyError:
        ui.notify("找不到此術語表", type="negative")  # 語境由呼叫端決定（票 09 review）
        return
    ui.notify(f"已改名 {name} → {new}", type="positive")
    rename_to_input.set_value("")
    keep = [new if n == name else n for n in glossary_select.value]
    stored = settings.selected_glossaries()  # stored 選擇同步：舊名換新名
    if stored is not None:
        settings.set_selected_glossaries([new if n == name else n for n in stored])
    _sync_glossary_pickers(glossaries, glossary_select, edit_select, keep)
    _render_entries(glossaries, entries_box, new)


def _render_entries(glossaries: GlossaryService, entries_box, name) -> None:
    """編輯頁顯示術語列（每列 source → target＋刪除鈕）。"""
    entries_box.clear()
    if not name:
        return
    try:
        entries = glossaries.entries(name)
    except KeyError:
        return
    with entries_box:
        for i, (source, target) in enumerate(entries):
            with ui.row().classes("items-center w-full gap-2"):
                ui.label(f"{source} → {target}").classes("flex-1 text-sm")
                ui.button(
                    "✕",
                    on_click=lambda i=i: _delete_entry(glossaries, name, i, entries_box),
                ).props("dense flat color=red")
        if not entries:
            ui.label("（空白術語表）").classes("text-grey-6 text-sm")


def _delete_entry(
    glossaries: GlossaryService, name: str, index: int, entries_box
) -> None:
    glossaries.delete_entry(name, index)
    _render_entries(glossaries, entries_box, name)


def _add_entry(
    glossaries: GlossaryService,
    name: str,
    src_input,
    tgt_input,
    entries_box,
) -> None:
    if not name:
        ui.notify("先選要編輯的術語表", type="negative")
        return
    source = src_input.value.strip()
    target = tgt_input.value.strip()
    if not source or not target:
        ui.notify("source 與 target 都要填", type="negative")
        return
    glossaries.add_entry(name, source, target)
    src_input.set_value("")
    tgt_input.set_value("")
    _render_entries(glossaries, entries_box, name)


def _save_pricing(
    cost: CostService, engine_id: str, in_price: str, out_price: str, per_page: str, rate: str
) -> None:
    """2026-08-13：單價卡含匯率（USD→TWD 顯示換算）——一起儲存，匯率也是設定不是寫死。"""
    try:
        cost.set_pricing(engine_id, in_price, out_price, int(per_page))
        cost.set_usd_twd_rate(rate)  # 匯率單獨存（跨引擎共用）
        ui.notify(f"單價＋匯率已儲存（{engine_id}）", type="positive")
    except (ValueError, TypeError):
        ui.notify("單價/匯率格式錯誤（需為數字）", type="negative")  # 表單驗證，固定訊息


def _enter_theme(settings: SettingsService) -> ui.dark_mode:
    """票 11：三頁共用入口——注入主題 CSS＋依偏好套深色，回傳控制器。"""
    dark = apply_theme()
    if settings.dark_mode():
        dark.enable()
    return dark


def _toggle_theme(settings: SettingsService, dark: ui.dark_mode, btn) -> None:
    """票 11：切換深色偏好並即時套用（不重載頁面），按鈕圖示同步更新。"""
    on = not settings.dark_mode()
    settings.set_dark_mode(on)
    if on:
        dark.enable()
    else:
        dark.disable()
    btn.set_text("☀️" if on else "🌙")


# 票 16：統一頁框側欄導覽（label, path；active 由 _nav_active 依當前頁判定）
SIDEBAR_NAV = [
    ("翻譯", "/"),
    ("歷史", "/history"),
    ("設定", "/settings"),
]


def _nav_active(path: str, current: str) -> bool:
    """票 16：側欄項是否高亮（當前頁對應項）。"""
    return path == current


def _engine_label_map() -> dict[str, str]:
    """引擎顯示名對照（engine_id → label）。三頁共用（standards review：收攏重複對映）。"""
    return {eid: spec.label for eid, spec in ENGINE_SPECS.items()}


def app_frame(
    title: str,
    settings: SettingsService,
    nav: list[tuple[str, str, bool]],
    badge: str | None = None,
) -> None:
    """票 16：統一頁框——頂部標題＋左側導覽欄＋主題切換＋Debug 頁尾。

    各頁面建構時呼叫一次（header/drawer 為 client 層級元素，不包內容）；
    取代各頁自造的 ui.header——三頁從「三個獨立網站」變成一個工具。
    Debug 降級為側欄底部小字連結（票 16 決策）。
    """
    dark = _enter_theme(settings)
    with ui.header().classes("items-center justify-between"):
        with ui.row().classes("items-center gap-3"):
            ui.label(title).classes("text-2xl font-bold")
            if badge:
                ui.badge(badge).props("outline")
        with ui.row().classes("items-center gap-3"):
            theme_btn = ui.button(
                "🌙" if settings.dark_mode() else "☀️",
                on_click=lambda: _toggle_theme(settings, dark, theme_btn),
            ).props("flat round")
    with ui.left_drawer(value=True).classes("bg-grey-3"):
        with ui.column().classes("w-full gap-1 p-2"):
            for label, path, active in nav:
                # ui.link（真實 <a href>）：點擊即導航，不需手寫 on_click
                link = ui.link(label, path).classes("w-full px-3 py-2 rounded")
                if active:
                    link.classes("bg-primary text-white")
                else:
                    link.classes("hover:bg-grey-4")
        ui.link("Debug", "/debug").classes("text-xs text-grey-6 px-4")


def _debug_page(log_path: Path, settings: SettingsService) -> None:
    """票 09：debug 檢視頁——最近任務的 log 可查（job_id 過濾）。"""

    @ui.page("/debug")
    def debug_page():
        ui.page_title("Paper_Kit Debug")
        # 票 16：統一頁框——側欄導覽；Debug 頁也進框架
        nav = [(l, p, _nav_active(p, "/debug")) for l, p in SIDEBAR_NAV]
        app_frame("🔍 Paper_Kit Debug Log", settings, nav)
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label(f"log 檔：{log_path}").classes("text-xs text-grey-6")
            job_filter = ui.input("過濾任務 id（空白 = 全部）").classes("w-full")
            box = ui.column().classes("w-full gap-1")

            def render():
                box.clear()
                entries = recent_log_entries(
                    log_path, n=200, job_id=(job_filter.value or "").strip() or None
                )
                with box:
                    if not entries:
                        ui.label("（無 log）").classes("text-grey-6 text-sm")
                    for entry in entries:
                        ui.label(format_log_line(entry)).classes("text-xs font-mono")

            job_filter.on_value_change(lambda: render())
            ui.button("重新整理", on_click=render).props("outline")
            render()


def _history_page(
    service: JobService,
    settings: SettingsService,
    engine_labels: dict[str, str] | None = None,
) -> None:
    """票 17：任務歷史表格頁——表格化＋分頁（每頁 10）＋引擎欄＋空狀態。

    對照沉浸式翻譯「記錄頁」：欄位（文件名／創建時間／頁數／引擎／狀態／操作）。
    批量操作（勾選／刪除／zip 下載）是票 18；本頁先立表格骨架。
    ui.table 的列資料直接送前端渲染（Vue），必須 JSON-safe——
    enum 不序列化，故列資料用挑選過的 dict（非 vars(view)）。
    slot 模板的 scope 變數是 props（`props.row`）且 body-cell slot 需自包
    <q-td>（spec review：裸 row.xxx 模板在前端渲染失敗）。
    """

    @ui.page("/history")
    def history_page():
        ui.page_title("Paper_Kit 歷史")
        # 票 16：統一頁框——側欄（歷史 active）
        nav = [(l, p, _nav_active(p, "/history")) for l, p in SIDEBAR_NAV]
        app_frame("📚 翻譯歷史", settings, nav)
        with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
            jobs = service.list_jobs()
            if not jobs:
                # 票 17 AC：空歷史提示＋「翻譯新文件」快捷入口（→ 主頁）
                ui.label("尚無翻譯任務").classes("text-xl text-grey-8")
                ui.link("翻譯新文件", "/").classes("text-primary")
                return
            engine_map = engine_labels or _engine_label_map()
            columns = [
                {"name": "file_name", "label": "文件名", "field": "file_name", "align": "left"},
                {"name": "created", "label": "創建時間", "field": "created_label", "align": "left"},
                {"name": "pages", "label": "頁數", "field": "pages_label", "align": "left"},
                {"name": "engine", "label": "引擎", "field": "engine_label", "align": "left"},
                {"name": "status", "label": "狀態", "field": "status_label", "align": "left"},
                {"name": "actions", "label": "操作", "field": "actions", "align": "left"},
            ]
            rows = _history_rows(service, engine_map)
            # 票 18：selection='multiple' → Quasar 內建勾選欄＋全選；
            # row_key 指向 job_id（row dict 由 _history_row 提供）
            table = ui.table(
                columns=columns, rows=rows, row_key="job_id",
                selection="multiple", pagination={"rowsPerPage": 10},
            ).classes("w-full")
            # 狀態彩色標籤（q-badge；scope=props、需自包 <q-td>）
            table.add_slot(
                "body-cell-status",
                "<q-td><q-badge :color='props.row.status_color' :label='props.row.status_label' /></q-td>",
            )
            # 操作列：mono／dual 下載（dual 不可退化——使用者明定）；
            # download attr＝附件下載（與主頁 ui.download 行為一致）。
            # 重試／取消：Vue slot 無法綁 Python handler，票 17 review 裁決——
            # 單列重試／取消併入票 18 批量操作列（批量按鈕在表格下方，Python handler 可直綁）。
            table.add_slot(
                "body-cell-actions",
                """<q-td><div class="flex gap-1">
                <q-btn v-if="props.row.mono_url" size="sm" flat color="primary" type="a"
                       :href="props.row.mono_url" download label="下載 mono" />
                <q-btn v-if="props.row.dual_url" size="sm" flat color="teal" type="a"
                       :href="props.row.dual_url" download label="下載 dual" />
                </div></q-td>""",
            )

            # ── 票 18：批量操作工具列（勾選後操作；刪除二次確認） ──

            def _refresh_rows() -> None:
                """批量操作後重繪表格（選取清空）。"""
                table.rows = _history_rows(service, engine_map)
                table.selected = []

            def _require_selection() -> list[str] | None:
                """勾選檢查——空選回 None（已提示），否則回 job_id 清單。"""
                ids = [r["job_id"] for r in table.selected]
                if not ids:
                    ui.notify("請先勾選要操作的任務", type="warning")
                    return None
                return ids

            def _batch_delete() -> None:
                ids = _require_selection()
                if ids is None:
                    return
                # 二次確認 dialog（破壞性操作——規格書 Further Notes 必做）
                with ui.dialog() as dialog, ui.card().classes("p-4 gap-2"):
                    ui.label(f"確定刪除 {len(ids)} 筆任務（含輸出檔）？").classes("text-lg")
                    ui.label("此操作無法復原").classes("text-xs text-grey-6")
                    with ui.row().classes("gap-2"):
                        ui.button("取消", on_click=dialog.close).props("outline")
                        ui.button(
                            "確認刪除",
                            on_click=lambda: (_confirm_delete(ids), dialog.close()),
                        ).props("color=negative")
                dialog.open()

            def _confirm_delete(ids: list[str]) -> None:
                deleted, blocked = _delete_jobs(service, ids)
                if blocked:
                    ui.notify(f"{blocked} 筆執行中的任務無法刪除", type="warning")
                if deleted:
                    ui.notify(f"已刪除 {deleted} 筆任務", type="positive")
                _refresh_rows()

            def _batch_action(action: str) -> None:
                """票 18：批量重試／取消（票 17 review 裁決的承諾——Python handler 直綁）。"""
                ids = _require_selection()
                if ids is None:
                    return
                if action == "retry":
                    n = _batch_retry(service, settings, ids)
                    if n == 0:
                        ui.notify("沒有可重試的任務（僅失敗／已取消可重試）", type="warning")
                else:
                    n = _batch_cancel(service, ids)
                    if n == 0:
                        ui.notify("沒有執行中的任務可取消", type="warning")
                _refresh_rows()

            def _batch_download(kind: str) -> None:
                ids = _require_selection()
                if ids is None:
                    return
                # 跳到 /download-batch 路由：伺服端 zip 打包、附件回傳（送完刪暫存）
                ui.navigate.to(f"/download-batch?ids={','.join(ids)}&kind={kind}")

            with ui.row().classes("items-center gap-2"):
                ui.button("批量刪除", on_click=_batch_delete).props("outline color=negative")
                ui.button(
                    "↻ 批量重試", on_click=lambda: _batch_action("retry")
                ).props("outline")
                ui.button(
                    "✕ 批量取消", on_click=lambda: _batch_action("cancel")
                ).props("outline")
                ui.button(
                    "批量下載 mono", on_click=lambda: _batch_download("mono")
                ).props("outline")
                ui.button(
                    "批量下載 dual", on_click=lambda: _batch_download("dual")
                ).props("outline color=teal")
                ui.label("勾選表格列後操作；執行中任務無法刪除").classes("text-xs text-grey-6")


def register_batch_download_route(service: JobService) -> None:
    """票 18：/download-batch?ids=...&kind=mono|dual —— 批量 zip 附件下載。

    伺服端打包（build_batch_zip 純函式）、zip 暫存 tempdir、送完即刪
    （FastAPI BackgroundTask）。無可打包任務 → 404（UI 已先提示）；
    kind 只接受 mono/dual（review 修正：未知 kind 不靜默走 dual）。
    """
    @app.get("/download-batch")
    def download_batch(ids: str = "", kind: str = "mono"):
        if kind not in ("mono", "dual"):
            return JSONResponse({"error": "bad kind"}, status_code=400)
        job_ids = [i for i in ids.split(",") if i]
        jobs = [j for j in service.list_jobs() if j.job_id in job_ids]
        zip_path = build_batch_zip(jobs, kind, tempfile.gettempdir())
        if zip_path is None:
            return JSONResponse({"error": "no files"}, status_code=404)
        return FileResponse(
            zip_path,
            filename=zip_path.name,
            media_type="application/zip",
            background=BackgroundTask(zip_path.unlink, missing_ok=True),
        )


def _history_rows(service: JobService, engine_map: dict[str, str]) -> list[dict]:
    """票 18：歷史表格列資料一處建構（initial 與 _refresh_rows 共用，免重複）。"""
    return [
        _history_row(
            build_job_card(job, files_base=FILES_BASE, engine_labels=engine_map)
        )
        for job in service.list_jobs()
    ]


def _history_row(view: JobCardView) -> dict:
    """歷史表格列資料——只挑 JSON-safe 欄位（票 17；enum 不序列化）。"""
    return {
        "job_id": view.job_id,  # 票 18：row_key（勾選回傳可對映回任務）
        "file_name": view.file_name,
        "created_label": view.created_label,
        "pages_label": view.pages_label,
        "engine_label": view.engine_label or "",
        "status_label": view.status_label,
        "status_color": BADGE_COLORS[view.status],
        "mono_url": view.mono_url,
        "dual_url": view.dual_url,
    }


def main() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH = setup_logging(APP_DIR / "logs")  # 票 09：結構化 log 檔（debug 頁讀同一份）
    app.add_static_files(FILES_BASE, str(OUTPUTS_DIR))
    repo = SqliteSettingsRepository(DB_PATH)
    # 票 08：SQLite 任務歷史——重啟 app 後任務仍在（InMemory 只留給無頭執行）
    # 票 12：注入 OcrService（RapidOCR 本機引擎）——掃描件預處理用
    settings = SettingsService(repo)
    # 票 24/25：翻譯快取——main() 組裝並注入 JobService 與設定頁（enabled 依設定頁開關即時同步）
    cache = TranslationCache(APP_DIR / "cache", enabled=settings.cache_enabled())
    service = JobService(
        jobs=SqliteJobRepository(DB_PATH),
        outputs_dir=OUTPUTS_DIR,
        ocr=OcrService(RapidOcrAdapter()),
        cache=cache,
    )
    cost = CostService(repo)
    glossaries = GlossaryService(GlossaryRepository(GLOSSARIES_DIR))

    _index_page(service, settings, cost, glossaries)
    _settings_page(settings, cost, glossaries, cache)
    _history_page(service, settings)
    register_batch_download_route(service)  # 票 18：批量下載 zip 路由
    _debug_page(LOG_PATH, settings)
    ui.run(title="Paper_Kit 論文翻譯器", reload=False)

def _index_page(
    service: JobService,
    settings: SettingsService,
    cost: CostService,
    glossaries: GlossaryService,
) -> None:
    """主頁：上傳即開始翻譯（票 10 紅線提示＋票 07 頁面範圍＋票 12 OCR）。"""

    @ui.page("/")
    def index():
        ui.page_title("Paper_Kit")
        # 票 16：統一頁框——側欄（翻譯 active）＋頂部標題；主題切換收進 frame
        nav = [(l, p, _nav_active(p, "/")) for l, p in SIDEBAR_NAV]
        app_frame(
            "📄 Paper_Kit 論文翻譯器", settings, nav, badge="自建 UI · 免除線上工具綁架"
        )
        with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):
            ui.label("拖放 PDF 上傳，自動翻譯成繁體中文（mono＋dual 並排）").classes("text-grey-8")
            # #85 切片D：免費額度資訊條（BabelDOC 風格；聚合已完成任務 tokens，1s 輪詢更新）
            quota_label = ui.label(_quota_label(0)).classes("text-xs text-grey-7")
            # 票 10：上傳即提示「檔案將送雲端」＋機密確認（R18／隱私紅線）
            ui.label(
                "⚠️ 上傳即代表同意：檔案內容將送雲端 API 翻譯。"
                "機密文件（R18／隱私）請勾選 🔒——僅 DeepSeek 純文字引擎可處理"
            ).classes("text-xs text-amber-7")
            sensitive_input = ui.checkbox("🔒 這是機密文件（只准純文字引擎，不上視覺模型）")
            # 票 12：掃描件 OCR（本機 onnxruntime，不上雲——機密文件相容）
            ocr_input = ui.checkbox("🔍 掃描件（無文字層 PDF）——本機 OCR 預處理")
            memo: dict[str, str | None] = {}
            cards = ui.column().classes("w-full gap-4")
            # #82 修復：刪除／預覽 dialog 建為**頁面級單例**（重複使用、canary 掛
            # 永存容器）——舊版在 handler 內 `with ui.dialog()` 重建，canary 掛卡片
            # slot，1s 輪詢 cards.clear() 連坐 dialog.delete()（「不到 2 秒消失」）。
            # state 承接「哪一筆任務」：按確認才刪（非開啟當下快照，防競態）。
            delete_state: dict = {"job_id": None}
            with ui.dialog() as delete_dialog, ui.card().classes("p-4 gap-2"):
                ui.label("確定刪除此任務（含輸出檔）？").classes("text-lg")
                ui.label("此操作無法復原").classes("text-xs text-grey-6")
                with ui.row().classes("gap-2"):
                    ui.button("取消", on_click=delete_dialog.close).props("outline")
                    ui.button(
                        "確認刪除",
                        on_click=lambda: (
                            _do_delete_one(service, delete_state["job_id"]),
                            delete_dialog.close(),
                        ),
                    ).props("color=negative")
            with ui.dialog() as preview_dialog, ui.card().classes(
                "w-[90vw] h-[90vh] p-0"
            ):
                preview_box = ui.html("")
            # 票 19：引擎三選卡——點選即設定「本任務」引擎（不寫進設定頁 global）
            selected_engine = settings.engine_id()  # closure；預設尊重設定頁

            def _pick_engine(eid: str) -> None:
                """點選引擎卡：更新本任務引擎＋卡片高亮（同一 render 的 closure）。

                2026-08-13（使用者回報）：勾機密後點視覺卡 → 前置阻擋（不讓
                使用者選了視覺引擎按「開始翻譯」才被 _start_job 拒絕——UX 前置化）。
                """
                nonlocal selected_engine
                if sensitive_input.value and not ENGINE_SPECS[eid].sensitive_ok:
                    ui.notify(
                        "機密文件僅 DeepSeek 純文字引擎（先取消 🔒 或選 DeepSeek）",
                        type="warning",
                    )
                    return
                selected_engine = eid
                for cid, c in engine_cards.items():
                    c.classes(
                        remove="ring-2 ring-primary",
                        add=("ring-2 ring-primary" if cid == eid else ""),
                    )
                # #85 切片C：進階選項僅 babeldoc 消費 → 點到 babeldoc 卡才顯示
                advanced_box.set_visibility(eid == "babeldoc")
                ui.notify(f"本任務將使用 {ENGINE_SPECS[eid].label}", type="info")

            engine_cards: dict[str, ui.card] = {}
            with ui.row().classes("gap-2 w-full"):
                for eid, desc in ENGINE_CARDS:
                    spec = ENGINE_SPECS[eid]
                    card = ui.card().mark(f"engine-card-{eid}").classes(
                        "pk-engine-card flex-1 cursor-pointer gap-1 p-3"
                        + (" ring-2 ring-primary" if eid == selected_engine else "")
                    )
                    with card:
                        ui.label(spec.label).classes("font-semibold text-sm")
                        ui.label(desc).classes("text-xs text-grey-7 pk-engine-desc")
                    engine_cards[eid] = card
                    card.on("click", _engine_picker(_pick_engine, eid))

            # 2026-08-13（使用者回報「為何不用勾選也能開始翻譯」）：
            # 勾「🔒 機密文件」→ 引擎自動切 DeepSeek＋視覺卡禁用（灰化）。
            # 舊行為＝勾了機密仍可選視覺引擎，按「開始翻譯」才被 _start_job
            # 拒絕（被動擋）；現在連動前置，紅線不靠「按了才知道」。
            def _on_sensitive_change(e) -> None:
                # handle_event 依簽名傳參：1 參數 handler 收到**事件物件**（非值）——
                # 直接 `def f(value: bool)` 會把 True/False 都當 truthy（#85 同款陷阱）
                value = bool(e.value)
                if value:
                    _pick_engine("deepseek")
                for cid, card in engine_cards.items():
                    disabled = value and not ENGINE_SPECS[cid].sensitive_ok
                    card.classes(
                        remove=("pk-engine-card--disabled" if not disabled else ""),
                        add=("pk-engine-card--disabled" if disabled else ""),
                    )

            sensitive_input.on_value_change(_on_sensitive_change)

            # 票 19：目標語言就地下拉（預設＝設定頁值；不跳設定頁就能改本任務語言）
            # spec review：設定頁語言是自由文字——值不在內建列表時併入選項
            #（NiceGUI choice_element 對不在 options 的初始值直接 raise ValueError → 主頁 500）
            lang_options = ["zh-TW", "zh-CN", "en"]
            current_lang = settings.target_lang()
            if current_lang and current_lang not in lang_options:
                lang_options = [current_lang] + lang_options
            lang_select = ui.select(
                lang_options,
                value=current_lang,
                label="目標語言（本任務）",
            ).classes("w-full")
            # #85 切片B：術語庫選擇移入主翻譯面板（BabelDOC 風格）——與設定頁共用
            # settings 後端（任一面板勾選即生效，雙向同步）；_start_job 讀同一值
            # → 術語表帶進 job.glossary_files＋預估 tokens ×1.57 倍率（#79 已測）
            main_glossary_select = ui.select(
                glossaries.list_glossaries(),
                value=settings.selected_glossary_names(glossaries.list_glossaries()),
                multiple=True,
                label="術語表（勾選套用；預估 tokens 依倍率更新）",
            ).classes("w-full")
            main_glossary_select.on_value_change(
                lambda: settings.set_selected_glossaries(list(main_glossary_select.value))
            )
            # #85：BabelDOC 風格暫存流程（2026-08-13 定案）——選檔＝**暫存**：
            # auto_upload=True 選完即上傳伺服器暫存（不建任務、不花錢），服務端
            # pypdf 讀頁數 → 「N of M」頁面範圍下拉 → 按「開始翻譯」才消費暫存建任務。
            # 舊語意（auto_upload=False queue）無法顯示頁數——頁數要等伺服器拿到檔。
            # 暫存目錄：APP_DIR/staging/（建任務後即清；create_job 已複製源檔）。
            staged: dict[str, Path] = {}

            async def _on_file_uploaded(e) -> None:
                """選檔即暫存——讀頁數更新「N of M」下拉；不建任務、不觸發翻譯。"""
                staging_dir = APP_DIR / "staging"
                staging_dir.mkdir(parents=True, exist_ok=True)
                target = staging_dir / f"{uuid.uuid4().hex}-{e.file.name}"
                try:
                    await e.file.save(target)
                except OSError as exc:  # 票 09：暫存寫入失敗也要有 toast，不吐 traceback
                    ui.notify(to_user_message(exc), type="negative")
                    return
                try:
                    pages = len(pypdf.PdfReader(str(target)).pages)
                except Exception:
                    ui.notify(f"無法讀取頁數：{e.file.name}（不是有效 PDF？）", type="warning")
                    target.unlink(missing_ok=True)
                    return
                staged[e.file.name] = target
                # 下拉以「最新上傳檔案」頁數為基準；語義＝範圍套用全部已暫存檔
                page_select.set_options([str(i) for i in range(1, pages + 1)], value=[])
                page_select.label = f"頁面範圍（{e.file.name}：共 {pages} 頁）"
                range_counter.set_text(f"已選 0 of {pages} 頁")
                staged_label.set_text(f"已暫存：{'、'.join(staged)}")
                ui.notify(f"已暫存 {e.file.name}（{pages} 頁）——可選頁面範圍後按「開始翻譯」", type="info")

            def _start_staged() -> None:
                """「開始翻譯」＝消費暫存檔建任務（不開檔案選擇器；#85 暫存流程）。"""
                if not staged:
                    ui.notify("尚未選擇檔案——先拖放 PDF 到上方", type="warning")
                    return
                selected = page_select.value or []
                for name, path in list(staged.items()):
                    try:
                        file_pages = len(pypdf.PdfReader(str(path)).pages)
                    except Exception:
                        file_pages = 0  # 理論上不會：暫存時已驗證可讀
                    ok = _start_job(
                        service, settings, cost, glossaries, path, name,
                        pages_text=_pages_for_file(selected, file_pages) or "",
                        sensitive=sensitive_input.value,
                        ocr=ocr_input.value,
                        # 票 19：只在使用者實際點選（≠設定頁 global）才 override——
                        # 未點選走 global 路徑（settings.resolve_engine，測試 seam）
                        engine_id=(
                            selected_engine
                            if selected_engine != settings.engine_id() else None
                        ),
                        target_lang=lang_select.value,
                        only_selected_pages=only_selected_input.value,  # #85：僅選中頁面
                        # #85 切片C：babeldoc 進階選項（其他引擎忽略）
                        enhance_compatibility=enhance_compat_input.value,
                        merge_alternating_line_numbers=merge_lines_input.value,
                        remove_non_formula_lines=remove_lines_input.value,
                        font_family=font_select.value,
                    )
                    if ok:
                        staged.pop(name, None)
                        path.unlink(missing_ok=True)  # create_job 已複製源檔 → 清暫存
                if not staged:
                    page_select.set_options([], value=[])
                    page_select.label = "頁面範圍（上傳後可選）"
                    range_counter.set_text("已選 0 of 0 頁")
                    staged_label.set_text("尚未選取檔案")

            with ui.card().classes("w-full pk-card"):
                upload_el = ui.upload(
                    label="拖放 PDF 或點選選擇（可多檔）",
                    auto_upload=True,  # #85：選檔即上傳伺服器暫存（BabelDOC 風格）
                    multiple=True,
                    on_upload=_on_file_uploaded,
                ).classes("w-full")
                staged_label = ui.label("尚未選取檔案").classes("text-sm text-grey-8")
                with ui.row().classes("items-center gap-3 w-full"):
                    page_select = ui.select(
                        [], multiple=True, value=[],
                        label="頁面範圍（上傳後可選）",
                    ).classes("flex-1")
                    range_counter = ui.label("已選 0 of 0 頁").classes("text-xs text-grey-7")
                only_selected_input = ui.checkbox("☑ 僅翻譯選中頁面（未選頁原樣保留）", value=True)
                # #85 切片C：babeldoc 進階選項——僅 babeldoc 引擎消費（點卡才顯示；
                # 設定頁 global 引擎＝babeldoc 時初始即顯示）
                advanced_box = ui.column().mark("babeldoc-advanced").classes("gap-1 w-full")
                advanced_box.set_visibility(selected_engine == "babeldoc")
                with advanced_box:
                    ui.label("BabelDOC 進階選項").classes("text-sm font-semibold text-grey-8")
                    enhance_compat_input = ui.checkbox("☑ 相容模式（版式較保守、錯位較少）", value=False)
                    merge_lines_input = ui.checkbox("☑ 行號增強（合併交錯行號）", value=True)
                    remove_lines_input = ui.checkbox(
                        "☑ 移除段落中的非公式線條", value=False
                    )
                    font_select = ui.select(
                        ["serif", "sans-serif", "script"],
                        value="serif",
                        label="字體",
                    ).classes("w-48")
                # 2026-08-13（使用者回報）：輸出目錄主頁就地設定——與設定頁共用
                # SettingsService.set_output_dir 後端（空白=預設 ~/.paper_kit/outputs）
                out_dir_input = ui.input(
                    "輸出目錄（空白 = 預設 ~/.paper_kit/outputs）",
                    value=settings.output_dir(),
                ).classes("w-full")

                def _apply_output_dir() -> None:
                    settings.set_output_dir(out_dir_input.value.strip())
                    ui.notify("輸出目錄已更新", type="positive")

                with ui.row().classes("items-center gap-3 w-full"):
                    ui.button("套用輸出目錄", on_click=_apply_output_dir).props("outline")
                    ui.label("輸出目錄為產出 mono/dual PDF 的位置（設定頁同步）").classes("text-xs text-grey-7")
                with ui.row().classes("items-center gap-3 w-full"):
                    ui.button(
                        "📂 開始翻譯",
                        on_click=_start_staged,
                    ).props("color=primary unelevated").classes("text-lg")
                    ui.label("選擇檔案後按「開始翻譯」送出；拖放＝暫存不自動翻譯").classes("text-xs text-grey-7")
        ui.timer(
            1.0,
            lambda: _refresh(
                cards, service, cost, settings, memo,
                delete_dialog, delete_state, preview_dialog, preview_box,
                quota_label=quota_label,  # #85 切片D：額度條隨輪詢同步
            ),
        )


if __name__ == "__main__":
    main()
