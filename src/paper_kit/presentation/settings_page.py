"""設定頁：引擎 key、預設值、術語庫、計價、快取（T-07 相位 4 自 app.py 抽出）。"""

import asyncio
import logging
from pathlib import Path

from nicegui import ui

from paper_kit.application.cost_service import CostService
from paper_kit.application.errors import to_user_message
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.settings_service import SettingsService
from paper_kit.application.translation_cache import TranslationCache
from paper_kit.domain.glossary import GlossaryFormatError
from paper_kit.presentation.composition import (
    ENGINE_SPECS,
    GlossaryNameError,
    diagnose,
    list_models,
    probe_key,
    probe_model,
)
from paper_kit.presentation.engine_cards import UI_ENGINE_IDS, UI_FREE_KEY_ENGINE_IDS
from paper_kit.presentation.handlers import _mask_key  # 票 20：key 遮罩
from paper_kit.presentation.index_page import _save_engine_choice
from paper_kit.presentation.shell import (
    SIDEBAR_NAV,
    _engine_label_map,
    _nav_active,
    app_frame,
)

logger = logging.getLogger("paper_kit.presentation.settings_page")


def _key_handlers(
    settings: SettingsService,
    eid: str,
    key_input,
    *,
    getter,
    setter,
    save_msg: str,
    clear_msg: str,
) -> tuple:
    """票 20/#84：0 參數 factory（`lambda eid=eid:` 會被 event 覆寫，票 19 教訓）。

    引擎 key 與術語提取 key（#84）共用同一份包裝——差異只有 getter/setter 與
    通知文案（2026-08-13 架構重構 P1：原四胞胎收斂）。防遮罩寫回：input 回顯的
    是遮罩——值等於遮罩視為未修改，不得存成 key；spec review（票 20）：清除後
    一併清 input 顯示值——否則殘留遮罩在「清除後再按儲存」會被當新 key 寫回
    （current="" 時任何值都過防遮罩判斷）。回傳 (save, clear) 0 參數 closures。
    """
    def save() -> None:
        current = getter(eid)
        value = key_input.value
        if value and value != _mask_key(current):
            setter(eid, value)
        ui.notify(save_msg, type="positive")

    def clear() -> None:
        setter(eid, "")
        key_input.value = ""
        ui.notify(clear_msg, type="warning")

    return save, clear


def _render_engine_key_card(settings: SettingsService, eid: str) -> None:
    """設定頁單一引擎的 key 子卡（2026-08-13：付費／免費兩區共用同一渲染——
    迴圈主體不複製兩份；marker 各引擎唯一：engine-key-{eid} 等）。

    含：狀態 badge、遮罩 input、儲存/清除/測試 API（GET /models 零成本驗證）、
    siliconflow 專屬術語提取 key 欄（#84）。
    """
    spec = ENGINE_SPECS[eid]
    # 2026-08-13（使用者二次回報「框框大小不一致」）：子卡套 .pk-card
    # 主題 token——與主頁引擎卡同一 border/radius/shadow 來源，不留在
    # Quasar 默認樣式造成跨頁視覺分歧
    with ui.card().mark(f"engine-key-{eid}").classes("pk-card w-full gap-2"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(spec.label).classes("font-semibold")
            ui.badge("已設定" if settings.api_key(eid) else "未設定 key")
        ui.label(spec.card_desc).classes("pk-text-xs pk-muted")
        key_input = ui.input(
            "API key",
            value=_mask_key(settings.api_key(eid)),
            password=True,
            password_toggle_button=True,
        ).classes("w-full").mark(f"engine-key-input-{eid}")
        save_key, clear_key = _key_handlers(
            settings, eid, key_input,
            getter=settings.api_key,
            setter=settings.set_api_key,
            save_msg=f"已儲存 {ENGINE_SPECS[eid].label} 的 API key",
            clear_msg=f"已清除 {ENGINE_SPECS[eid].label} 的 API key",
        )
        with ui.row().classes("gap-2"):
            ui.button(
                "儲存 key",
                on_click=save_key,
            ).props("outline").mark(f"engine-key-save-{eid}")
            ui.button(
                "清除",
                on_click=clear_key,
            ).props("outline flat color=negative").mark(f"engine-key-clear-{eid}")
            # 2026-08-13（使用者要求）：測試 API 按鈕——填入 key 後確認
            # 是否成功啟用。GET /models（零成本）驗 key ＋ POST /chat/completions
            # （max_tokens=1）驗模型可生成（#78：gemini-3-pro-latest 在清單但
            # generateContent 404 的盲區）。
            async def _test_api(eid=eid, spec=spec, settings=settings) -> None:
                key = settings.api_key(eid)
                if not key:
                    ui.notify(f"{spec.label}：尚未設定 key", type="warning")
                    return
                # 卡①：探測收斂 llm_probe.probe_model（單點——UA/診斷文案與
                # preflight 同源；v0.1.7 Groq 403 誤擋修復全端生效）
                code, body = await asyncio.to_thread(
                    probe_model, spec.base_url, key, spec.model
                )
                if code == 200:
                    ui.notify(
                        f"✅ {spec.label} 連線成功（HTTP 200）",
                        type="positive",
                    )
                elif code in (401, 403):
                    ui.notify(f"⚠️ {spec.label}：{diagnose(code, body)}", type="warning")
                elif code == 404:
                    ui.notify(f"❌ {spec.label}：{diagnose(code, body)}", type="negative")
                elif code == 429:
                    ui.notify(f"⚠️ {spec.label}：{diagnose(code, body)}", type="warning")
                else:
                    ui.notify(f"❌ {spec.label}：{diagnose(code, body)}", type="negative")

            ui.button(
                "測試 API",
                on_click=_test_api,
            ).props("outline").mark(f"engine-key-test-{eid}")
        if eid == "siliconflow":
            # #84：術語提取 key 獨立化——term 引擎＝SiliconFlow 專屬
            # （term 旗標僅 siliconflow provider 發送，#83）；獨立 key
            # 避免共用主 key（可各自輪替、權限分離）。
            ui.label("術語提取 API key（自動術語提取專用；空白 = 沿用主 key）").classes(
                "pk-text-xs pk-muted"
            )
            term_input = ui.input(
                "術語提取 API key",
                value=_mask_key(settings.term_api_key(eid)),
                password=True,
                password_toggle_button=True,
            ).classes("w-full").mark(f"term-key-input-{eid}")
            save_term, clear_term = _key_handlers(
                settings, eid, term_input,
                getter=settings.term_api_key,
                setter=settings.set_term_api_key,
                save_msg="已儲存術語提取 key",
                clear_msg="已清除術語提取 key",
            )
            with ui.row().classes("gap-2"):
                ui.button(
                    "儲存術語 key",
                    on_click=save_term,
                ).props("outline").mark(f"term-key-save-{eid}")
                ui.button(
                    "清除",
                    on_click=clear_term,
                ).props("outline flat color=negative").mark(f"term-key-clear-{eid}")
        if spec.provider == "babeldoc":
            # 雙模型（2026-10-16 Phase 2，仿沉浸式翻譯「Kimi 抽術語 + DeepSeek 翻正文」）：
            # BabelDOC 原生支援 --openai-term-extraction-*——術語抽取可以走另一個
            # 模型／端點／key。**三欄各自獨立留空＝沿用主模型**（向後相容、opt-in）。
            # 未開啟自動術語提取時這些設定不會被使用（UI 不隱藏，避免使用者困惑
            # 「為什麼找不到」——N/A 由 tooltip 說明）。
            ui.label(
                "雙模型（術語抽取獨立；空白 = 沿用主模型與端點）"
            ).classes("pk-text-xs pk-muted").mark(f"term-model-label-{eid}")
            term_model_input = ui.input(
                "術語模型",
                value=settings.term_model(eid),
            ).classes("w-full").mark(f"term-model-input-{eid}")
            save_tm, clear_tm = _key_handlers(
                settings, eid, term_model_input,
                getter=settings.term_model,
                setter=settings.set_term_model,
                save_msg="已儲存術語模型",
                clear_msg="已清除術語模型（沿用主模型）",
            )
            term_base_url_input = ui.input(
                "術語端點",
                value=settings.term_base_url(eid),
            ).classes("w-full").mark(f"term-base-url-input-{eid}")
            save_tb, clear_tb = _key_handlers(
                settings, eid, term_base_url_input,
                getter=settings.term_base_url,
                setter=settings.set_term_base_url,
                save_msg="已儲存術語端點",
                clear_msg="已清除術語端點（沿用主端點）",
            )
            with ui.row().classes("gap-2"):
                ui.button("儲存術語模型", on_click=save_tm).props(
                    "outline"
                ).mark(f"term-model-save-{eid}")
                ui.button("清除術語模型", on_click=clear_tm).props(
                    "outline flat color=negative"
                ).mark(f"term-model-clear-{eid}")
                ui.button("儲存術語端點", on_click=save_tb).props(
                    "outline"
                ).mark(f"term-base-url-save-{eid}")
                ui.button("清除術語端點", on_click=clear_tb).props(
                    "outline flat color=negative"
                ).mark(f"term-base-url-clear-{eid}")
        if spec.provider == "openai":
            # v0.1.3：模型挑選（NVIDIA EOL 410 教訓——2026-08-14 使用者實測
            # deepseek-v4-flash 於 08-07 下線：registry 寫死的 model 會過期）——
            # 下拉（載入 API 最新清單）＋自訂輸入（with_input）雙軌，永遠不撞 EOL。
            ui.label("模型（下拉挑選或自行輸入；空白 = 官方預設）").classes(
                "pk-text-xs pk-muted"
            )
            saved_model = settings.engine_model(eid)
            default_model = spec.model
            model_select = ui.select(
                [default_model] + (
                    [saved_model] if saved_model and saved_model != default_model else []
                ),
                value=saved_model or default_model,
                label="模型",
                with_input=True,  # 可自訂輸入（不從清單挑時直接打字）
            ).classes("w-full").mark(f"engine-model-select-{eid}")

            async def _load_models(
                eid=eid, spec=spec, settings=settings, model_select=model_select,
            ) -> None:
                """拉取 API 最新模型清單填入下拉（用已儲存 key；零成本 GET /models）。"""
                key = settings.api_key(eid)
                if not key:
                    ui.notify(
                        f"{spec.label}：請先「儲存 key」再載入模型清單",
                        type="warning",
                    )
                    return
                code, body = await asyncio.to_thread(probe_key, spec.base_url, key)
                if code != 200:
                    ui.notify(
                        f"{spec.label}：載入模型失敗（HTTP {code} {body[:40]}）"
                        "——key 可能無效",
                        type="negative",
                    )
                    return
                models = await asyncio.to_thread(list_models, spec.base_url, key)
                if not models:
                    ui.notify(f"{spec.label}：模型清單為空", type="warning")
                    return
                current = model_select.value
                model_select.options = models
                if current not in models:
                    model_select.options = [current] + models  # 保留既有值
                model_select.update()
                ui.notify(
                    f"已載入 {len(models)} 個模型——可在下拉挑選或直接輸入",
                    type="positive",
                )

            def _save_model() -> None:
                """儲存挑選的模型（空白 = 清除覆寫、用官方預設）。"""
                value = (model_select.value or "").strip()
                settings.set_engine_model(eid, value)
                ui.notify(
                    f"已儲存 {spec.label} 的模型：{value or spec.model + '（官方預設）'}",
                    type="positive",
                )

            with ui.row().classes("gap-2"):
                ui.button(
                    "🔄 載入模型清單",
                    on_click=_load_models,
                ).props("outline").mark(f"engine-model-load-{eid}")
                ui.button(
                    "儲存模型",
                    on_click=_save_model,
                ).props("outline").mark(f"engine-model-save-{eid}")


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
                ).classes("pk-text-xs pk-muted")
                # 2026-08-13（使用者要求「付費、免費不要混雜」）：分兩區——付費引擎
                # 與免費 LLM（自備免費 key）各自成區、各有區標題；卡集合同 registry
                # 單點（UI_ENGINE_IDS 付費／UI_FREE_KEY_ENGINE_IDS 免費）。
                ui.label("🔑 付費引擎（自備 key）").classes(
                    "pk-text-sm font-semibold pk-muted mt-3"
                ).mark("paid-keys-section")
                for eid in UI_ENGINE_IDS:
                    _render_engine_key_card(settings, eid)
                ui.label("🎁 免費 LLM（自備免費 key）").classes(
                    "pk-text-sm font-semibold pk-muted mt-3"
                ).mark("free-keys-section")
                for eid in UI_FREE_KEY_ENGINE_IDS:
                    _render_engine_key_card(settings, eid)
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
                    "pk-text-xs pk-muted"
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
                    "pk-text-xs pk-muted"
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
                ui.button(
                    "匯入內建詞表（paper-kit-basic，265 條自研）",
                    on_click=lambda: _seed_builtin(glossaries, glossary_select, edit_select),
                ).props("outline")
                ui.button(
                    "匯入樂詞網詞表（naer-core，樂詞網學術名詞 2.9 萬條）",
                    on_click=lambda: _seed_naer(glossaries, glossary_select, edit_select),
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
                    ).classes("pk-text-xs pk-muted")
                    cache_stats_label = ui.label(_cache_stats_label(cache)).classes(
                        "pk-text-sm pk-muted"
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
    if count == 0:
        # 2026-08-14 真機診斷：三欄 CSV 的 tgt_lng（如 zh-TW）與任務目標語言
        # （如 zh）不符 → 領域層整表跳過。舊行為綠字「已匯入（0 條）」誤導
        # 使用者以為成功、任務卻無詞表可用 → 負面警示＋提示原因。
        ui.notify(
            f"匯入 {name}：0 條——CSV 無資料，或 tgt_lng 語言 "
            f"（若有）與目標語言 {settings.target_lang()} 不符",
            type="negative",
        )
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


def _seed_builtin(glossaries: GlossaryService, glossary_select, edit_select) -> None:
    """#84 方案 A：匯入內建基礎詞表（自研 265 條；冪等——已存在不覆寫）。

    授權紅線：immersive-terms 無 LICENSE 不得嵌入，本詞表全自研彙編
    （見 builtin_glossary 模組 docstring／docs/research/…-immersive-terms術語庫-查證.md）。
    """
    try:
        created = glossaries.seed_builtin()
    except OSError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    if created:
        ui.notify("已匯入內建詞表 paper-kit-basic（265 條）", type="positive")
    else:
        ui.notify("內建詞表已存在，未覆寫（可從下方編輯）", type="warning")
    _sync_glossary_pickers(glossaries, glossary_select, edit_select, list(glossary_select.value))


def _seed_naer(glossaries: GlossaryService, glossary_select, edit_select) -> None:
    """術語庫擴充（2026-08-14）：匯入樂詞網詞表 naer-core（2.9 萬條單詞層）。

    來源國家教育研究院樂詞網（政府資料開放授權條款-第1版，顯名聲明見
    builtin_glossary docstring／scripts/naer_build.py 檔頭）；冪等——已存在不覆寫。
    """
    try:
        created = glossaries.seed_naer()
    except OSError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    if created:
        ui.notify("已匯入樂詞網詞表 naer-core（2.9 萬條）", type="positive")
    else:
        ui.notify("樂詞網詞表已存在，未覆寫（可從下方編輯）", type="warning")
    _sync_glossary_pickers(glossaries, glossary_select, edit_select, list(glossary_select.value))


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
    """編輯頁顯示術語列（每列 source → target＋刪除鈕）。

    大詞表截斷（術語庫擴充 2026-08-14）：naer-core 2.9 萬條全量渲染會卡死
    UI——超過上限只顯示前段（刪除索引仍是原始序，編輯仍正確）。
    """
    _DISPLAY_LIMIT = 500  # 大詞表（naer-core 等）只顯示前段
    entries_box.clear()
    if not name:
        return
    try:
        entries = glossaries.entries(name)
    except KeyError:
        return
    with entries_box:
        shown = entries[:_DISPLAY_LIMIT]
        for i, (source, target) in enumerate(shown):
            with ui.row().classes("items-center w-full gap-2"):
                ui.label(f"{source} → {target}").classes("flex-1 pk-text-sm")
                ui.button(
                    "✕",
                    on_click=lambda i=i: _delete_entry(glossaries, name, i, entries_box),
                ).props("dense flat color=red")
        if len(entries) > _DISPLAY_LIMIT:
            ui.label(
                f"（詞表共 {len(entries)} 條，僅顯示前 {_DISPLAY_LIMIT} 條——"
                "大詞表供翻譯使用，編輯請用小詞表或直接改 CSV 檔）"
            ).classes("pk-muted pk-text-sm")
        if not entries:
            ui.label("（空白術語表）").classes("pk-muted pk-text-sm")


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
