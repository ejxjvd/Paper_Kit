"""主頁（上傳即翻譯）：引擎卡、任務卡、進度輪詢（T-07 相位 4 自 app.py 抽出）。"""

import logging
import uuid
from pathlib import Path

import pypdf  # #85：選檔即讀頁數（BabelDOC 風格「N of M」頁面範圍下拉）
from nicegui import ui

from paper_kit.application.cost_service import CostService
from paper_kit.application.errors import to_user_message
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_intake import EngineChoice, JobIntake  # 候選 1：任務建立規則
from paper_kit.application.job_service import JobService
from paper_kit.application.ports import EngineError, TranslationEnginePort
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.cost_calculator import CostEstimate
from paper_kit.domain.translation_job import JobStatus
from paper_kit.presentation.composition import (
    ENGINE_SPECS,
    build_engine,
    can_select,
    detect_latex_dense,
    resolve_key,
    sensitive_blocked,
    spec_has_key,
)
from paper_kit.presentation.engine_cards import (
    UI_ENGINE_IDS,
    UI_FREE_ENGINE_IDS,
    UI_FREE_KEY_ENGINE_IDS,
    UI_LOCAL_GATEWAY_ENGINE_IDS,
)
from paper_kit.presentation.file_ops import _download_output, _open_folder
from paper_kit.presentation.handlers import (
    JobCardView,
    StartJobParams,  # P4：_start_job 參數收斂物件（.tex/PDF 分支各自組裝）
    _aggregate_used_tokens,
    _is_tex_path,  # 票 27：.tex 判別
    _pages_for_file,  # #85：頁面範圍套用
    _quota_label,  # #85 切片D：額度條文字
    _translated_pages,  # #27：翻譯頁數
    build_job_card,
    progress_label,  # #15：進度框文字（「完成 100% · 10/10 頁」）
)
from paper_kit.presentation.job_actions import (
    _cancel_job,
    _confirm_delete_one,
    _do_delete_one,
    _retry_job,
)
from paper_kit.presentation.runtime import APP_DIR, OUTPUTS_DIR
from paper_kit.presentation.shell import (
    BADGE_COLORS,
    SIDEBAR_NAV,
    _engine_label_map,
    _nav_active,
    app_frame,
)

logger = logging.getLogger("paper_kit.presentation.index_page")


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
    if spec.id == "latex":
        # 票 27：latex 後端＝deepseek-chat（README 唯一推薦後端）——key 未獨立
        # 填時沿用 deepseek 槽位（同後端同 key；設定頁 latex 卡可覆寫）。
        # 槽位沿用規則單點在 engine_registry.resolve_key（架構健檢 #1+2+8）——
        # 此處只取 key＋給錯誤（訊息是 UI 呼叫方責任）。
        key = resolve_key("latex", settings.api_key)
        if not key:
            raise EngineError("尚未設定 LaTeX／DeepSeek 的 API key（設定頁填入後再翻譯）")
        return spec.id, build_engine(spec, api_key=key)
    # 卡③（2026-08-14）：key 存在判定收斂 registry 單點（spec_has_key——
    # latex 槽位沿用已含；此分支 spec.id≠latex，等價裸查但規則不再內聯重算）
    if not spec_has_key(spec.id, settings.api_key):
        raise EngineError(f"尚未設定 {spec.label} 的 API key（設定頁填入後再翻譯）")
    # v0.1.3：model 覆寫（設定頁挑選）一併套用——主頁選引擎與設定頁 global 同源
    # 2026-10-16 Phase 2：雙模型三欄一併帶入（否則設定頁存了、主頁翻譯收不到——plumbing 缺口）
    return spec.id, build_engine(
        spec,
        api_key=settings.api_key(spec.id),
        model_override=settings.engine_model(spec.id) or None,
        term_api_key=settings.term_api_key(spec.id),
        term_model=settings.term_model(spec.id),
        term_base_url=settings.term_base_url(spec.id),
    )


def _engine_picker(pick, eid: str):
    """票 19：0 參數 picker factory——`lambda eid=eid:` 會被 event 參數覆寫
    （handle_event 依簽名參數數目傳 event；1 參數 lambda 收到的是事件物件）。
    迴圈內閉包捕獲也要即時綁定（否則三個 handler 全看最後一個 eid）。
    """
    def pick_engine() -> None:
        pick(eid)
    return pick_engine


def _render_single_engine_card(body: ui.column, eid: str) -> None:
    """單卡內容重建（付費／免費 LLM 兩區共用）——label／ⓘ／desc 對應目前引擎。

    架構健檢 #1：消除 _render_paid_key_card／_render_free_key_card 逐行複製
    雙胞胎（原本 28 行重複；改動後 _index_page 內只剩呼叫）。
    """
    spec = ENGINE_SPECS[eid]
    body.clear()
    with body:
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(spec.label).classes("font-semibold pk-text-sm")
            ui.icon("help_outline").props("size=16px").classes(
                "pk-muted"
            ).mark(f"info-engine-{eid}").tooltip(spec.info)
        ui.label(spec.card_desc).classes("pk-text-xs pk-muted pk-engine-desc")


def _swap_single_engine_card(
    engine_cards: dict, card: ui.card, body: ui.column,
    old_eid: str, new_eid: str, disabled: bool,
) -> None:
    """單卡切換顯示引擎：dict key 替換＋內容重建＋灰化重算（付費／免費 LLM 兩區共用）。

    呼叫方（_index_page closure）已通過 _pick_engine 守衛並負責下拉顯示同步
    （set_value 不觸發 handler 無遞迴）；disabled＝新引擎的灰化判定
    （can_select）——換引擎後卡不該停留舊引擎的灰態（舊無 key、新有 key 時）。
    架構健檢 #1：_set_paid_card／_on_free_key_select 後半段逐行複製收斂於此。
    """
    engine_cards.pop(old_eid, None)
    engine_cards[new_eid] = card
    _render_single_engine_card(body, new_eid)
    card.classes(
        remove="ring-2 ring-primary"
        + ("" if disabled else " pk-engine-card--disabled"),
        add="ring-2 ring-primary"
        + (" pk-engine-card--disabled" if disabled else ""),
    )


def _start_job(
    service: JobService,
    settings: SettingsService,
    cost: CostService,
    glossaries: GlossaryService,
    params: StartJobParams,
) -> bool:
    """送暫存檔建立翻譯任務。成功（含引擎已啟動）回 True——呼叫方清理暫存。

    候選 1（2026-08-19 架構深化）：十條應用層規則已搬進 application/job_intake。
    這裡只剩兩件事——解析引擎（registry-bound，錯誤訊息要引擎 label），
    以及把回傳的結果畫成 toast。規則不再與 ui.notify 交錯，因此可以不開 UI 就測。
    """
    try:
        engine_id, engine = _resolve_task_engine(settings, params.engine_id)
    except EngineError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return False
    # 引擎能力以資料交給 application（票 10 慣例：application 不查 ENGINE_SPECS）。
    # 卡③ fail-closed：未知引擎視為不允許機密——這條判定現在只算一次。
    choice = EngineChoice(
        engine_id=engine_id,
        engine=engine,
        allows_sensitive=not sensitive_blocked(engine_id, True, unknown_sensitive_ok=False),
        tex_only=engine_id == "latex",
    )
    result = JobIntake(service, settings, cost, glossaries).submit(params, choice)
    if not result.accepted:
        ui.notify(result.rejection, type="negative")
        return False
    for warning in result.warnings:
        ui.notify(warning, type="warning")
    _notify_estimate(cost, engine_id, result.estimate)
    ui.notify(f"任務已建立：{params.file_name}", type="positive")
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
                    ui.label(view.file_name).classes("pk-text-lg font-semibold")
                    if view.sensitive:  # 票 10：機密標記顯示
                        ui.badge("🔒 機密").props("outline color=orange")
                    if view.ocr:  # 票 12：掃描件標記顯示
                        ui.badge("🔍 掃描件").props("outline color=teal")
                    if view.from_cache:  # 票 26：快取命中標記（引擎未呼叫）
                        ui.badge("⚡ 快取").props("outline color=cyan")
                    if view.latex_warning:  # v0.1.9.5：LaTeX 密集標注（行重疊風險提示）
                        ui.badge("⚠️ 疑似 LaTeX 密集").props(
                            "outline color=orange"
                        ).tooltip(
                            "偵測到此 PDF 含 LaTeX 數學字體（Computer Modern/Latin Modern/"
                            "unicode-math 系）——翻譯後中文行距可能被引擎壓縮而產生重疊"
                            "（BabelDOC 限制，公式參數與 mono 實測無效）；建議以下載的 "
                            "dual 左半原文對照閱讀。判定為字體名啟發式：XeLaTeX/CTeX 中文"
                            "論文若完全不用 CM/LM 數學字體可能漏標（僅少一次提醒，無損傷）。"
                        )
                # 票 08：歷史卡片顯示建立時間＋引擎
                meta = f"任務 {view.job_id[:8]} · {view.created_label}"
                if view.engine_label:
                    meta += f" · {view.engine_label}"
                ui.label(meta).classes("pk-text-xs pk-meta")  # 票 11：muted 變數
            ui.badge(view.status_label).props(f"color={BADGE_COLORS[view.status]}")
        # #72：排隊中＝還沒開始（不顯示進度條，與翻譯中明確區分——使用者要求
        # 「排隊中跟翻譯中完全不同」）；翻譯中＝有引擎進度顯示確定值、無則
        # indeterminate（動畫＝正在跑）；完成＝100%。
        # #15：一律 show_value=False（默認 True 會在 bar 中央顯示內嵌「1」——
        # 完成只看到「1」的根因）＋progress_label 組字（「完成 100% · 10/10 頁」）。
        if view.status is JobStatus.QUEUED:
            pass
        elif view.status is JobStatus.TRANSLATING:
            if view.progress is not None:
                # 票 11：進度條納入主題變數（深色下保持對比）
                ui.linear_progress(value=view.progress, show_value=False).classes("w-full pk-progress")
            else:
                ui.linear_progress(
                    value=0.5, show_value=False
                ).props("indeterminate").classes("w-full pk-progress")
            ui.label(progress_label(view)).classes("pk-text-xs pk-meta")
        elif view.status is JobStatus.COMPLETED:
            ui.linear_progress(value=1.0, show_value=False).classes("w-full pk-progress")
            ui.label(progress_label(view)).classes("pk-text-xs pk-meta")
        if view.error:
            ui.label(f"錯誤：{view.error}").classes("pk-error")  # 票 11：錯誤語意色走主題變數
        # 票 08 review：完成任務顯示「估算 vs 實際」，未完成顯示上傳時估價
        cost_label = view.usage_label or view.estimated_label
        if cost_label:
            ui.label(cost_label).classes("pk-text-sm pk-cost")  # 票 11：成本排版變數
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
    latex_memo: dict[str, bool] | None = None,  # v0.1.9.5：LaTeX 密集偵測（完成任務只偵測一次）
) -> None:
    cards.clear()
    # #85 切片D：已用 tokens 聚合（已完成任務 in+out）→ 額度條文字
    if quota_label is not None:
        quota_label.set_text(_quota_label(_aggregate_used_tokens(service.list_jobs())))
    # spec review：引擎欄顯示 label（「DeepSeek（純文字…）」）不是 raw id
    engine_labels = _engine_label_map()
    if latex_memo is None:
        latex_memo = {}
    for job in service.list_jobs():
        # memo：完成任務只算一次成本標籤（1s 輪詢下避免每輪重讀 PDF 頁數）
        if job.status is JobStatus.COMPLETED and job.job_id not in memo:
            memo[job.job_id] = cost.usage_label(job)
        # v0.1.9.5：完成任務只偵測一次 LaTeX 密集（讀 PDF 字體清單有 IO，memo 避免每輪重掃）
        if job.status is JobStatus.COMPLETED and job.job_id not in latex_memo:
            latex_memo[job.job_id] = _is_latex_dense_source(job)
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
                    latex_warning=bool(latex_memo.get(job.job_id)),
                ),
                service,
                settings,
                delete_dialog,
                delete_state,
                preview_dialog,
                preview_box,
            )


def _is_latex_dense_source(job) -> bool:
    """v0.1.9.5：來源 PDF 是否 LaTeX 數學密集（只對 PDF 判定；讀取失敗→False）。

    LaTeX 論文翻譯後行重疊是 BabelDOC 引擎限制（行距壓縮 < 中文字形高）——
    偵測到時卡片標注 ⚠️ 提示使用者。非 PDF 來源（.tex 走 LaTeX 引擎）不判定。
    """
    src = job.source_path
    if not src:
        return False
    try:
        result = detect_latex_dense(str(src))
    except Exception as exc:  # 偵測失敗不中斷既有流程
        logger.debug("LaTeX 偵測失敗", extra={"path": str(src), "error": str(exc)})
        return False
    return bool(result and result.is_dense)


def _save_engine_choice(settings: SettingsService, engine_id: str) -> None:
    """票 20：儲存「預設引擎」選擇（key 已由各引擎卡獨立管理，不再經此寫）。"""
    try:
        settings.set_engine(engine_id)
        ui.notify("引擎設定已儲存", type="positive")
    except KeyError:
        ui.notify("未知引擎", type="negative")


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
            ui.label("拖放 PDF 上傳，自動翻譯成繁體中文（mono＋dual 並排）").classes("pk-text")
            # #85 切片D：免費額度資訊條（BabelDOC 風格；聚合已完成任務 tokens，1s 輪詢更新）
            quota_label = ui.label(_quota_label(0)).classes("pk-text-xs pk-muted")
            # 票 10：上傳即提示「檔案將送雲端」＋機密確認（R18／隱私紅線）
            ui.label(
                "⚠️ 上傳即代表同意：檔案內容將送雲端 API 翻譯。"
                "機密文件（R18／隱私）請勾選 🔒——僅 DeepSeek 純文字引擎可處理"
            ).classes("pk-text-xs pk-warning")
            with ui.row().classes("items-center gap-2"):
                sensitive_input = ui.checkbox("🔒 這是機密文件（只准純文字引擎，不上視覺模型）")
                # 2026-08-13（使用者要求）：ⓘ 說明——hover 顯示機密紅線細節
                ui.icon("help_outline").props("size=18px").classes(
                    "pk-muted cursor-pointer"
                ).mark("info-sensitive").tooltip(
                    "機密文件（R18／隱私）只能走 DeepSeek 純文字引擎，視覺模型不上雲。"
                    "勾選後引擎自動切 DeepSeek，視覺卡灰化禁用"
                )
            # 票 12：掃描件 OCR（本機 onnxruntime，不上雲——機密文件相容）
            with ui.row().classes("items-center gap-2"):
                ocr_input = ui.checkbox("🔍 掃描件（無文字層 PDF）——本機 OCR 預處理")
                ui.icon("help_outline").props("size=18px").classes(
                    "pk-muted cursor-pointer"
                ).mark("info-ocr").tooltip(
                    "無文字層的掃描 PDF：先本機 OCR（RapidOCR，不上雲）抽出文字層再翻譯，"
                    "機密相容"
                )
            # 2026-08-13（使用者認為「都不勾也能翻譯」是 bug）：勾選項是「特殊處理」
            # 開關——都不是＝一般 PDF 直接翻譯（勾了掃描件反而多跑 OCR 預處理）
            ui.label("（都不勾選＝一般 PDF，直接翻譯）").classes("pk-text-xs pk-muted")
            # 2026-08-13（使用者回報）：引擎三卡移到機密／掃描件勾選之下、任務清單之上
            # ——任務一多不再把引擎卡往下推（cards 容器最後建立，見頁尾）
            selected_engine = settings.engine_id()  # closure；預設尊重設定頁

            def _pick_engine(eid: str, force: bool = False) -> bool:
                """點選引擎卡：更新本任務引擎＋卡片高亮（同一 render 的 closure）。

                2026-08-13（使用者回報）：勾機密後點視覺卡 → 前置阻擋（不讓
                使用者選了視覺引擎按「開始翻譯」才被 _start_job 拒絕——UX 前置化）。
                2026-08-13（使用者要求）：無 API key 的付費卡灰化不可點——點擊
                前置阻擋＋警告（與機密阻擋同 UX 模式）。
                force＝程式自動切換（機密紅線優先於 key 檢查——機密模式自動切
                DeepSeek 即使未填 key 也要切，讓翻譯時報缺 key 而非 UI 卡住）。
                回傳 True＝已切換；False＝被守衛擋下（下拉選單復原用）。
                """
                nonlocal selected_engine
                # 規則收斂 registry（架構健檢 #1+2+8）：sensitive_blocked／spec_has_key
                # 純函式單點——與 _card_disabled（can_select 組合）同源；訊息留此呼叫方
                if sensitive_blocked(eid, sensitive_input.value):
                    ui.notify(
                        "機密文件僅 DeepSeek／OpenAI／Gemini 付費等不訓練引擎可用"
                        "（先取消 🔒 或選其一）",
                        type="warning",
                    )
                    return False
                spec = ENGINE_SPECS[eid]
                if not force and not spec_has_key(eid, settings.api_key):
                    ui.notify(
                        f"尚未設定 {spec.label} 的 API key（設定頁填入後再翻譯）",
                        type="warning",
                    )
                    return False
                selected_engine = eid
                for cid, c in engine_cards.items():
                    c.classes(
                        remove="ring-2 ring-primary",
                        add=("ring-2 ring-primary" if cid == eid else ""),
                    )
                # #85 切片C：進階選項僅 babeldoc 消費 → 點到 babeldoc 卡才顯示
                advanced_box.set_visibility(eid == "babeldoc")
                ui.notify(f"本任務將使用 {ENGINE_SPECS[eid].label}", type="info")
                return True

            engine_cards: dict[str, ui.card] = {}

            def _card_disabled(eid: str) -> bool:
                """2026-08-13（使用者要求）：無 API key 的付費卡灰化不可點。

                統一判定（機密＋key 兩層紅線合併）——規則收斂 registry
                （架構健檢 #1+2+8）：can_select＝sensitive_blocked（票 10 紅線）
                ＋spec_has_key（needs_key／latex 槽位沿用）。_on_sensitive_change
                與初始渲染共用同一判定——取消機密不會誤解灰化。
                """
                return not can_select(eid, sensitive_input.value, settings.api_key)

            # 付費引擎區（2026-08-13 使用者要求「卡片欄位太多」）：6 卡收斂為
            # 單卡顯示目前所選引擎＋下拉選單挑選——與免費 LLM 區同款機制（單卡
            # 仍進 engine_cards dict，key＝目前顯示引擎——ring 清除／機密禁用
            # 迴圈自動涵蓋）；下拉換引擎＝換 dict key＋重建卡內容（_pick_engine
            # 同款守衛，被擋復原下拉值）。
            ui.label("付費引擎（自備 key）").classes(
                "pk-text-sm font-semibold pk-muted mt-2"
            ).mark("paid-key-engine-section")
            ui.label(
                "品質最佳（DeepSeek／OpenAI／Gemini 等）——在設定頁填入各自的 API key；"
                "機密文件請選 DeepSeek 等不訓練引擎"
            ).classes("pk-text-xs pk-muted").mark("paid-key-engine-hint")
            paid_key_eid = (
                selected_engine if selected_engine in UI_ENGINE_IDS
                else UI_ENGINE_IDS[0]
            )
            with ui.row().classes("gap-2 w-full items-stretch"):
                paid_key_select = ui.select(
                    {eid: ENGINE_SPECS[eid].label for eid in UI_ENGINE_IDS},
                    value=paid_key_eid,
                    label="付費引擎",
                ).classes("w-64").mark("paid-key-engine-select")
                with ui.card().mark("paid-key-engine-card").classes(
                    "pk-engine-card flex-1 cursor-pointer gap-1 p-3"
                    + (" ring-2 ring-primary" if selected_engine == paid_key_eid else "")
                    + (" pk-engine-card--disabled" if _card_disabled(paid_key_eid) else "")
                ) as paid_key_card:
                    paid_key_body = ui.column().classes("gap-1 w-full")

                _render_single_engine_card(paid_key_body, paid_key_eid)
                engine_cards[paid_key_eid] = paid_key_card
                paid_key_card.on("click", lambda: _pick_engine(paid_key_eid))

                def _set_paid_card(eid: str) -> None:
                    """付費單卡切換顯示引擎（薄 closure）：同 eid 早退＋下拉同步＋
                    共用 _swap_single_engine_card（dict key／內容重建／灰化重算——
                    架構健檢 #1 收斂與免費 LLM 區的重複）。

                    呼叫方已通過 _pick_engine 守衛（下拉 handler／.tex 自動鎖定／
                    機密自動切 DeepSeek）。_pick_engine 的 ring 迴圈跑在換 key 前
                    （eid 不在 dict 不會加 ring）——單卡高亮在此手動補（_swap）。
                    順序關鍵（2026-08-13 實證）：paid_key_eid 必須先更新再 set_value
                    ——set_value 會觸發 on_value_change handler（重入），handler
                    見同 eid 早退才無害；反之 handler 走完整守衛（無 key 的
                    deepseek 被 key 守衛擋）→ 復原下拉值覆寫同步（真實 bug：
                    機密勾選後下拉與卡片不一致）。"""
                    nonlocal paid_key_eid
                    if eid == paid_key_eid:
                        return
                    old_eid = paid_key_eid
                    paid_key_eid = eid  # 先更新：set_value 重入的 handler 見同 eid 早退
                    paid_key_select.set_value(eid)  # 同步下拉顯示（機密/.tex 自動切換）
                    _swap_single_engine_card(
                        engine_cards, paid_key_card, paid_key_body,
                        old_eid, eid, disabled=_card_disabled(eid),
                    )

                def _on_paid_key_select(e) -> None:
                    """下拉換引擎＝挑選引擎（同點卡語意）。被機密／key 守衛擋下時
                    復原下拉值（widget 不回滾，手動復原）。"""
                    eid = e.value
                    if eid == paid_key_eid:
                        return
                    if not _pick_engine(eid):  # 守衛擋下（機密/key）→ 復原
                        paid_key_select.set_value(paid_key_eid)
                        return
                    _set_paid_card(eid)

                paid_key_select.on_value_change(_on_paid_key_select)

            # 免費翻譯入口（2026-08-13，使用者要求「拿到工具的人不填 key 就能
            # 免費翻譯、絕不動個人 API」）：免 key 引擎卡區。與付費卡共用同一
            # engine_cards dict → ring 清除／_on_sensitive_change 禁用迴圈／
            # _pick_engine 機密阻擋全部自動涵蓋，無需特例分支。
            ui.label("免費翻譯（不需 API key）").classes(
                "pk-text-sm font-semibold pk-muted mt-2"
            ).mark("free-engine-section")
            ui.label("零成本翻譯（上游代理轉發）——品質低於付費引擎；機密文件請選 DeepSeek").classes(
                "pk-text-xs pk-muted"
            ).mark("free-engine-hint")
            # items-stretch（2026-10-16 D4）：另兩區（付費／免費 LLM）早有此 class，
            # 唯獨本區漏了——這正是「三卡不等高」最早的來源之一。補上後與其他兩列一致，
            # 卡片高度改由 flex stretch 決定，不再靠 CSS 硬鎖＋截斷。
            with ui.row().classes("gap-2 w-full items-stretch"):
                for eid in UI_FREE_ENGINE_IDS:
                    spec = ENGINE_SPECS[eid]
                    card = ui.card().mark(f"engine-card-{eid}").classes(
                        "pk-engine-card flex-1 cursor-pointer gap-1 p-3"
                        + (" ring-2 ring-primary" if eid == selected_engine else "")
                    )
                    with card:
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(spec.label).classes("font-semibold pk-text-sm")
                            ui.icon("help_outline").props("size=16px").classes(
                                "pk-muted"
                            ).mark(f"info-engine-{eid}").tooltip(spec.info)
                        ui.label(spec.card_desc).classes("pk-text-xs pk-muted pk-engine-desc")
                    engine_cards[eid] = card
                    card.on("click", _engine_picker(_pick_engine, eid))

            # 免費 LLM 入口（2026-08-13，Free-LLM-Collection 查證後加入）：BYOK 免費 key
            # 引擎第二層——品質優於上方零 key 區（NVIDIA/ModelScope 等旗艦免費），
            # 但需各自申請免費 key。2026-08-13（使用者要求「7 張卡太多」）：7 卡收斂
            # 為單卡顯示目前所選引擎＋下拉選單挑選。單卡仍進 engine_cards dict（key＝
            # 目前顯示引擎——ring 清除／機密禁用迴圈自動涵蓋）；下拉換引擎＝換 dict
            # key＋重建卡內容（_pick_engine 同款守衛，被擋復原下拉值）。
            ui.label("免費 LLM（自備免費 key）").classes(
                "pk-text-sm font-semibold pk-muted mt-2"
            ).mark("free-key-engine-section")
            ui.label(
                "免費大模型（NVIDIA/ModelScope 等，品質接近付費）——在設定頁填入各自的"
                "免費 API key；機密文件請選 DeepSeek"
            ).classes("pk-text-xs pk-muted").mark("free-key-engine-hint")
            # 下拉預設＝目前所選引擎（若為免費 LLM）或優先序首支；選項＝registry 單點
            free_key_eid = (
                selected_engine if selected_engine in UI_FREE_KEY_ENGINE_IDS
                else UI_FREE_KEY_ENGINE_IDS[0]
            )
            with ui.row().classes("gap-2 w-full items-stretch"):
                free_key_select = ui.select(
                    {eid: ENGINE_SPECS[eid].label for eid in UI_FREE_KEY_ENGINE_IDS},
                    value=free_key_eid,
                    label="免費 LLM 引擎",
                ).classes("w-64").mark("free-key-engine-select")
                with ui.card().mark("free-key-engine-card").classes(
                    "pk-engine-card flex-1 cursor-pointer gap-1 p-3"
                    + (" ring-2 ring-primary" if selected_engine == free_key_eid else "")
                    + (" pk-engine-card--disabled" if _card_disabled(free_key_eid) else "")
                ) as free_key_card:
                    free_key_body = ui.column().classes("gap-1 w-full")

                _render_single_engine_card(free_key_body, free_key_eid)
                engine_cards[free_key_eid] = free_key_card
                free_key_card.on("click", lambda: _pick_engine(free_key_eid))

                def _on_free_key_select(e) -> None:
                    """下拉換引擎＝挑選引擎（同點卡語意）。被機密／key 守衛擋下時
                    復原下拉值（widget 不回滾，手動復原）。切換共用
                    _swap_single_engine_card（付費區同款——架構健檢 #1 收斂）。"""
                    nonlocal free_key_eid
                    eid = e.value
                    if eid == free_key_eid:
                        return
                    if not _pick_engine(eid):  # 守衛擋下（機密/key）→ 復原
                        free_key_select.set_value(free_key_eid)
                        return
                    _swap_single_engine_card(
                        engine_cards, free_key_card, free_key_body,
                        free_key_eid, eid, disabled=_card_disabled(eid),
                    )
                    free_key_eid = eid

                free_key_select.on_value_change(_on_free_key_select)

            # 本機代理區（2026-10-16 D2 裁決：A 案＋本機閘道另立第四區）。
            # 與免費 LLM 區分開的原因：loopback 端點（http://127.0.0.1）不符合
            # 免費 LLM 區的 https 不變式；語意也不同——這裡是「本機轉發閘道」。
            # ⚠️ 卡面文案必須寫明「不是本機推論」：流量仍上行至上游（命名誠實）。
            if UI_LOCAL_GATEWAY_ENGINE_IDS:
                ui.label("本機代理（需自行啟動閘道）").classes(
                    "pk-text-sm font-semibold pk-muted mt-2"
                ).mark("local-gateway-section")
                ui.label(
                    "本機轉發閘道——⚠️ 不是本機推論，內容仍會上行至上游；"
                    "使用前請先啟動閘道，機密文件不可用"
                ).classes("pk-text-xs pk-muted").mark("local-gateway-hint")
                with ui.row().classes("gap-2 w-full items-stretch"):
                    for eid in UI_LOCAL_GATEWAY_ENGINE_IDS:
                        spec = ENGINE_SPECS[eid]
                        card = ui.card().mark(f"engine-card-{eid}").classes(
                            "pk-engine-card flex-1 cursor-pointer gap-1 p-3"
                            + (" ring-2 ring-primary" if eid == selected_engine else "")
                        )
                        with card:
                            with ui.row().classes("items-center justify-between w-full"):
                                ui.label(spec.label).classes("font-semibold pk-text-sm")
                                ui.icon("help_outline").props("size=16px").classes(
                                    "pk-muted"
                                ).mark(f"info-engine-{eid}").tooltip(spec.info)
                            ui.label(spec.card_desc).classes("pk-text-xs pk-muted pk-engine-desc")
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
                    _pick_engine("deepseek", force=True)
                    _set_paid_card("deepseek")  # 單卡化後：付費單卡同步顯示可用引擎
                for cid, card in engine_cards.items():
                    # 2026-08-13（使用者要求）：統一判定（機密＋key）——取消機密
                    # 只解除機密層；無 key 的付費卡仍灰。規則收斂 registry
                    # （架構健檢 #1+2+8）：can_select＝sensitive_blocked＋spec_has_key
                    # ——與 _card_disabled／_pick_engine 同源（取消機密不解錯灰化）。
                    disabled = not can_select(cid, value, settings.api_key)
                    card.classes(
                        remove=("pk-engine-card--disabled" if not disabled else ""),
                        add=("pk-engine-card--disabled" if disabled else ""),
                    )

            sensitive_input.on_value_change(_on_sensitive_change)
            # #82 修復：刪除／預覽 dialog 建為**頁面級單例**（重複使用、canary 掛
            # 永存容器）——舊版在 handler 內 `with ui.dialog()` 重建，canary 掛卡片
            # slot，1s 輪詢 cards.clear() 連坐 dialog.delete()（「不到 2 秒消失」）。
            # state 承接「哪一筆任務」：按確認才刪（非開啟當下快照，防競態）。
            delete_state: dict = {"job_id": None}
            with ui.dialog() as delete_dialog, ui.card().classes("p-4 gap-2"):
                ui.label("確定刪除此任務（含輸出檔）？").classes("pk-text-lg")
                ui.label("此操作無法復原").classes("pk-text-xs pk-muted")
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
                if _is_tex_path(e.file.name):
                    # 票 27：LaTeX 源碼——無「頁數」概念（xelatex 編譯後才有）；
                    # 不讀 pypdf；自動鎖 LaTeX 引擎（.tex 預設走 LaTeX 路線）
                    staged[e.file.name] = target
                    page_select.set_options([], value=[])
                    page_select.label = "LaTeX 源碼：整份編譯（無頁面範圍）"
                    range_counter.set_text("—")
                    staged_label.set_text(f"已暫存：{'、'.join(staged)}")
                    if selected_engine != "latex":
                        if _pick_engine("latex"):  # 自動鎖定（含卡片高亮＋notify）
                            _set_paid_card("latex")  # 單卡化後：付費單卡同步顯示
                    else:
                        ui.notify(f"已暫存 {e.file.name}（LaTeX 源碼——LaTeX 引擎）", type="info")
                    return
                try:
                    pages = len(pypdf.PdfReader(str(target)).pages)
                except Exception as exc:
                    # 帶真實原因（2026-08-14 實測：AES-256 加密 PDF 在缺
                    # cryptography 時訊息誤導為「不是有效 PDF？」）
                    ui.notify(
                        f"無法讀取頁數：{e.file.name}（{type(exc).__name__}: {exc}）",
                        type="warning",
                    )
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
                    if _is_tex_path(name):
                        # 票 27：.tex 無頁數語意——總頁數 None（進度框不顯示頁數）、
                        # 整份編譯；engine override 已由暫存時自動鎖定 latex
                        ok = _start_job(
                            service, settings, cost, glossaries,
                            # P4：.tex 分支——pages_text/total_pages/ocr 無語意（走 StartJobParams 預設）
                            StartJobParams(
                                file_path=path,
                                file_name=name,
                                sensitive=sensitive_input.value,
                                engine_id=(
                                    selected_engine
                                    if selected_engine != settings.engine_id() else None
                                ),
                                target_lang=lang_select.value,
                            ),
                        )
                        if ok:
                            staged.pop(name, None)
                            path.unlink(missing_ok=True)  # create_job 已複製源檔 → 清暫存
                        continue
                    try:
                        file_pages = len(pypdf.PdfReader(str(path)).pages)
                    except Exception:
                        file_pages = 0  # 理論上不會：暫存時已驗證可讀
                    pages_text = _pages_for_file(selected, file_pages)
                    ok = _start_job(
                        service, settings, cost, glossaries,
                        StartJobParams(
                            file_path=path,
                            file_name=name,
                            pages_text=pages_text or "",
                            # #27：翻譯頁數（選取頁碼數）與 PDF 總頁數分開——
                            # 挑 2 頁翻譯 → 「完成 100% · 2/2 頁」＋歷史「2/58 頁」（先前錯顯示 58/58）
                            total_pages=_translated_pages(pages_text, file_pages),
                            pdf_pages=file_pages or None,
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
                        ),
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
                staged_label = ui.label("尚未選取檔案").classes("pk-text-sm pk-text")
                with ui.row().classes("items-center gap-3 w-full"):
                    page_select = ui.select(
                        [], multiple=True, value=[],
                        label="頁面範圍（上傳後可選）",
                    ).classes("flex-1")
                    range_counter = ui.label("已選 0 of 0 頁").classes("pk-text-xs pk-muted")
                only_selected_input = ui.checkbox("僅翻譯選中頁面（未選頁原樣保留）", value=True)
                # #85 切片C：babeldoc 進階選項——僅 babeldoc 引擎消費（點卡才顯示；
                # 設定頁 global 引擎＝babeldoc 時初始即顯示）
                advanced_box = ui.column().mark("babeldoc-advanced").classes("gap-1 w-full")
                advanced_box.set_visibility(selected_engine == "babeldoc")
                with advanced_box:
                    ui.label("BabelDOC 進階選項").classes("pk-text-sm font-semibold pk-text")
                    # 2026-08-13（使用者要求「開啟 babeldoc 多了一堆選項，差別在哪」）：
                    # 每個選項旁 ⓘ 說明——hover 即看用途，不用猜
                    with ui.row().classes("items-center gap-1"):
                        enhance_compat_input = ui.checkbox("☑ 相容模式（版式較保守、錯位較少）", value=False)
                        ui.icon("help_outline").props("size=16px").classes(
                            "pk-muted cursor-pointer"
                        ).mark("info-compat").tooltip(
                            "版面重排較保守：保留更多原始版式、減少文字錯位，"
                            "但段落重排效果較弱。適合數學／表格密集的 PDF。"
                        )
                    with ui.row().classes("items-center gap-1"):
                        merge_lines_input = ui.checkbox("☑ 行號增強（合併交錯行號）", value=True)
                        ui.icon("help_outline").props("size=16px").classes(
                            "pk-muted cursor-pointer"
                        ).mark("info-merge-lines").tooltip(
                            "把因欄位排版被拆成多行的「行號」合併回原行——"
                            "期刊／論文雙欄版面的行號不再散落成孤兒行。"
                        )
                    with ui.row().classes("items-center gap-1"):
                        remove_lines_input = ui.checkbox(
                            "☑ 移除段落中的非公式線條", value=False
                        )
                        ui.icon("help_outline").props("size=16px").classes(
                            "pk-muted cursor-pointer"
                        ).mark("info-remove-lines").tooltip(
                            "刪除圖表框線、分隔線等不屬於公式的直線物件——"
                            "版面雜訊較多的掃描文件建議開啟。"
                        )
                    with ui.row().classes("items-center gap-1"):
                        font_select = ui.select(
                            ["serif", "sans-serif", "script"],
                            value="serif",
                            label="字體",
                        ).classes("w-48")
                        ui.icon("help_outline").props("size=16px").classes(
                            "pk-muted cursor-pointer"
                        ).mark("info-font").tooltip(
                            "輸出的字型風格：serif（襯線，正式文件）／"
                            "sans-serif（無襯線，簡潔現代）／script（手寫風，裝飾用）。"
                        )
                # 2026-08-13（使用者回報）：輸出目錄主頁就地設定——與設定頁共用
                # SettingsService.set_output_dir 後端（空白=預設 ~/.paper_kit/outputs）
                out_dir_input = ui.input(
                    "輸出目錄（空白 = 預設 ~/.paper_kit/outputs）",
                    value=settings.output_dir(),
                ).classes("w-full")

                def _apply_output_dir() -> None:
                    settings.set_output_dir(out_dir_input.value.strip())
                    ui.notify("輸出目錄已更新", type="positive")

                # 2026-08-13（使用者回報）：輸出目錄旁「瀏覽資料夾」——填完路徑
                # 直接開 Explorer 看產出（_open_folder 見檔頭，wslpath 轉 Windows 路徑）。
                # 注意：settings.output_dir() 未設定時回傳 ""——Path("")＝當前目錄，
                # 會開錯資料夾；fallback 到 OUTPUTS_DIR（真實預設，main() 傳給 JobService）
                def _browse_output_dir() -> None:
                    target = out_dir_input.value.strip()
                    _open_folder(Path(target) if target else OUTPUTS_DIR)

                with ui.row().classes("items-center gap-3 w-full"):
                    ui.button("套用輸出目錄", on_click=_apply_output_dir).props("outline")
                    ui.button(
                        "📂 瀏覽資料夾",
                        on_click=_browse_output_dir,
                    ).props("outline").mark("browse-output-dir")
                    ui.label("輸出目錄為產出 mono/dual PDF 的位置（設定頁同步）").classes("pk-text-xs pk-muted")
                with ui.row().classes("items-center gap-3 w-full"):
                    ui.button(
                        "📂 開始翻譯",
                        on_click=_start_staged,
                    ).props("color=primary unelevated").classes("pk-text-lg")
                    ui.label("選擇檔案後按「開始翻譯」送出；拖放＝暫存不自動翻譯").classes("pk-text-xs pk-muted")
            # 2026-08-13（使用者回報「3 個引擎按鈕在任務歷史下方」）：任務清單容器
            # 最後建立——引擎卡固定在上方（勾選下方），任務一多不再把引擎卡往下推
            # #22（2026-08-13 修復）：容器必須留在 max-w-4xl 欄位內（本欄位的 with
            # 區塊）——先前縮排掉出欄位、落在 root slot，任務卡橫跨全頁寬
            # （使用者回報「任務歷史一整排填滿、與上方寬度不一、割裂」；
            # CDP 實測 L=316 R=1889 vs 欄位 L=655 R=1551 定案）。
            memo: dict[str, str | None] = {}
            latex_memo: dict[str, bool] = {}  # v0.1.9.5：LaTeX 密集偵測 memo（完成任務只算一次）
            cards = ui.column().classes("w-full gap-4")
            ui.timer(
                1.0,
                lambda: _refresh(
                    cards, service, cost, settings, memo,
                    delete_dialog, delete_state, preview_dialog, preview_box,
                    quota_label=quota_label,  # #85 切片D：額度條隨輪詢同步
                    latex_memo=latex_memo,
                ),
            )
