"""主頁（上傳）端到端回歸：真實 upload handler 路徑（2026-08-12 使用者實測 bug）。

使用者丟 CH4.pdf 上傳（UI 顯示 100%）但翻譯沒開始、頁面也沒有任何
可點按鍵——兩件事：
1. on_upload handler 拋 AttributeError（NiceGUI 3.15 的 UploadEventArguments
   沒有 name/content，改 e.file: FileUpload）被 handle_event 吞掉 → UI 靜默無反應。
2. 主頁沒有明顯的「開始翻譯」入口（原本只有上傳區）。

本測試經 user_simulation 開真實主頁、以 handle_uploads 模擬檔案上傳，
斷言任務卡片與完成下載連結出現——handler 拋任何例外都會紅。
"""

import asyncio
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
import paper_kit.presentation.app as app_module  # 同 module 物件（見下註）
from paper_kit.presentation.app import _index_page
from paper_kit.presentation.handlers import _translated_pages  # P2：純函式已收斂至 handlers

from test_ui_flow import FileWritingFakeEngine  # noqa: E402


def _build(tmp_path) -> tuple[JobService, SettingsService, CostService, GlossaryService]:
    service = JobService(
        jobs=InMemoryJobRepository(),
        outputs_dir=tmp_path / "outputs",
    )
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    return service, settings, cost, glossaries


async def _open_twice(user) -> None:
    # user_simulation 的 root 在首個 request 才註冊路由——
    # 第一次 open 為暖身（404 骨架），第二次才是真實渲染。
    await user.open("/")
    await user.open("/")


@pytest.mark.asyncio
async def test_upload_starts_translation_and_shows_completed_card(
    tmp_path, monkeypatch, make_blank_pdf
):
    """上傳 CH4.pdf（暫存）→ 按「開始翻譯」→ 任務卡片出現 → FakeEngine 完成。

    （resolve_engine 注入 FakeEngine：真實引擎會打 API；monkeypatch 只換
    引擎解析，其餘路徑——暫存寫檔、create_job、start、計價——全真實。）
    """
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        # 真空白 PDF（conftest make_blank_pdf）——壞檔會走 PdfStreamError 防衛
        # （ocr.py），非本測試目標；真檔才通過掃描件偵測路徑
        real_pdf = make_blank_pdf(tmp_path / "CH4.pdf")
        await upload_el.handle_uploads([
            SmallFileUpload(
                name="CH4.pdf",
                content_type="application/pdf",
                _data=real_pdf.read_bytes(),
            ),
        ])
        # #85：上傳＝暫存（不自動建任務）——暫存 label 出現
        await user.should_see("已暫存：CH4.pdf", retries=20)
        user.find("📂 開始翻譯").click()
        # 任務卡片由 1s timer 刷新出現——retries 放大（2s）
        await user.should_see("CH4.pdf", retries=20)
        # FakeEngine 立即完成 → 完成卡片的下載按鈕在下一輪刷新出現（5s 保守）
        await user.should_see("下載 mono", retries=50)
        await user.should_see("完成", retries=5)


@pytest.mark.asyncio
async def test_index_page_has_start_button(tmp_path):
    """2026-08-12 使用者回饋：主頁要有明顯可點的「開始翻譯」按鍵。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        await user.should_see("開始翻譯")
        await user.should_see("拖放 PDF 或點選選擇")


@pytest.mark.asyncio
async def test_upload_stages_file_without_creating_job(tmp_path, make_blank_pdf):
    """2026-08-12 使用者核心訴求（#85 升級語意）：拖放/點選＝**暫存**，絕不自動
    開始翻譯（花錢）——auto_upload=True 選完即上傳伺服器，但任務要等
    「開始翻譯」才建立。

    auto-upload 是伺服器端契約：NiceGUI set_bool 對 truthy 值寫入 props
    （props.py），Quasar autoUpload=true → 選檔立即上傳；handler 只暫存。
    """
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        assert upload_el._props.get("auto-upload") is True, "選檔＝上傳伺服器暫存（auto-upload 契約）"
        pdf = make_blank_pdf(tmp_path / "CH4.pdf", pages=3)
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        assert service.list_jobs() == [], "暫存≠建任務——絕不自動開始翻譯（花錢）"


@pytest.mark.asyncio
async def test_start_button_consumes_staged_files_not_picker(
    tmp_path, monkeypatch, make_blank_pdf
):
    """「開始翻譯」＝消費暫存檔建任務，**不是**再開檔案選擇器（也無需 queue
    上傳——auto_upload=True 已先暫存）。舊版 on_click 開 pickFiles → 拖放後
    按鈕又彈檔案總管（2026-08-12 使用者實測 bug 的舊世代行為，本測試固化
    #85 新語意：選檔→暫存，開始→建任務）。
    """
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        # 守衛 1：開始翻譯不得開檔案選擇器——pickFiles 缺席
        start_btn = next(
            b for b in user.find(ui.button).elements if "開始翻譯" in (b.text or "")
        )
        clicked = [el for el in start_btn._event_listeners.values() if el.type == "click"]
        assert clicked, "「開始翻譯」按鈕沒有 click listener"
        # 守衛 2：無暫存時點擊 → 警告且不建任務
        for el in clicked:
            el.handler(None)
        assert service.list_jobs() == []
        # 暫存後點擊 → 消費暫存建任務（側信道：job 建立）
        pdf = make_blank_pdf(tmp_path / "CH4.pdf")
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        for el in clicked:
            el.handler(None)
        assert len(service.list_jobs()) == 1, "開始翻譯＝消費暫存建任務"


# ── 票 19：主頁就地選項（引擎卡／目標語言／任務卡顯示引擎） ─────────


def _engine_card(user, eid: str):
    """引擎卡 UserInteraction（marker 定位——Card 非 TextElement，content 查不到）。"""
    return user.find(kind=ui.card, marker=f"engine-card-{eid}")


def _collect_label_texts(el) -> list[str]:
    """遞迴收集元素內所有 TextElement 的 text（任務卡 marker 定位後斷言 meta 用）。

    TextElement.text 是 BindableProperty（props 無「text」鍵——初版用
    props.get("text") 收集到空列表，bisect 實證後修正）。
    """
    texts = []
    for child in getattr(el, "default_slot", None) and el.default_slot.children or []:
        text = getattr(child, "text", None)
        if text:
            texts.append(text)
        texts.extend(_collect_label_texts(child))
    return texts


async def _pick_and_upload(user, service, pdf: Path) -> None:
    """點選 DeepSeek 引擎卡 → 上傳（暫存）→ 點「開始翻譯」→ 等任務出現。"""
    _engine_card(user, "deepseek").click()
    upload_el = next(iter(user.find(ui.upload).elements))
    await upload_el.handle_uploads([
        SmallFileUpload(name=pdf.name, content_type="application/pdf", _data=pdf.read_bytes()),
    ])
    await user.should_see(pdf.name, retries=20)  # 暫存 label 出現（含檔名）
    user.find("📂 開始翻譯").click()  # #85：暫存 → 消費建任務
    await user.should_see("任務已建立", retries=20)


@pytest.mark.asyncio
async def test_engine_cards_select_task_engine(tmp_path, monkeypatch, make_blank_pdf):
    """AC1：主頁三張引擎卡（SiliconFlow／DeepSeek／BabelDOC），點選後本任務用該引擎
    （側信道：job.engine_id + build_engine 注入 fake，不打真 API）。"""
    from test_ui_flow import FileWritingFakeEngine

    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("deepseek", "sk-test")  # override 路徑建引擎前查 key
    monkeypatch.setattr(
        "paper_kit.presentation.app.build_engine",
        lambda spec, api_key="": FileWritingFakeEngine(),
    )

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        # 三張卡齊備
        for label in ("SiliconFlow", "DeepSeek", "BabelDOC"):
            await user.should_see(label)
        await _pick_and_upload(user, service, make_blank_pdf(tmp_path / "E1.pdf"))
        job = service.list_jobs()[-1]
        assert job.engine_id == "deepseek", f"點選引擎卡後任務應記 deepseek，實際 {job.engine_id}"


@pytest.mark.asyncio
async def test_engine_card_selection_highlights_card(tmp_path, monkeypatch):
    """點選引擎卡後該卡有選中視覺（ring-primary），提示本任務引擎。
    （2026-08-13 灰化：付費卡需 key 才能點——先填 key 模擬正常使用。）"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("deepseek", "sk-ds-test")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        deepseek_card = _engine_card(user, "deepseek")
        card_el = next(iter(deepseek_card.elements))
        assert "ring-primary" not in card_el.classes, "初始 DeepSeek 卡不應被選中（預設是 siliconflow）"
        deepseek_card.click()
        assert "ring-primary" in card_el.classes, "點選後卡片應有選中高亮"


@pytest.mark.asyncio
async def test_target_lang_select_defaults_to_settings_value(tmp_path, monkeypatch, make_blank_pdf):
    """AC2：目標語言下拉就地可選，預設為設定頁值；改選後本任務用新值。"""
    from test_ui_flow import FileWritingFakeEngine

    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_target_lang("zh-TW")
    settings.set_api_key("deepseek", "sk-test")  # _pick_and_upload 點 DeepSeek 卡
    monkeypatch.setattr(
        "paper_kit.presentation.app.build_engine",
        lambda spec, api_key="": FileWritingFakeEngine(),
    )

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        # #85：頁面現有兩個 select（目標語言＋頁面範圍）——find 回 set，next(iter) 隨機；
        # 一律按 label 精確定位（flaky 教訓：set 迭代序不定）
        lang_select = next(
            s for s in user.find(ui.select).elements if "目標語言" in (s.label or "")
        )
        assert lang_select.value == "zh-TW", "下拉預設應為設定頁值"
        lang_select.value = "en"  # 就地改選（公開 property，同 table.selected 模式）
        await _pick_and_upload(user, service, make_blank_pdf(tmp_path / "E2.pdf"))
        job = service.list_jobs()[-1]
        assert job.target_lang == "en", f"改選語言後任務應記 en，實際 {job.target_lang}"


@pytest.mark.asyncio
async def test_lang_select_accepts_custom_setting_value(tmp_path, monkeypatch):
    """票 19 spec review：設定頁目標語言是自由文字——值不在內建列表（如「ja」）
    時主頁也要能 render（選項併入設定值；NiceGUI choice_element 對不在 options
    的初始值會 raise ValueError → 主頁 500）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_target_lang("ja")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)  # render 500 會在此炸
        lang_select = next(
            s for s in user.find(ui.select).elements if "目標語言" in (s.label or "")
        )
        assert lang_select.value == "ja", "設定值應被併入選項並保持為下拉值"


@pytest.mark.asyncio
async def test_upload_with_missing_key_is_blocked(tmp_path, monkeypatch, make_blank_pdf):
    """AC5（票 20）：點選無 key 的引擎上傳 → 就地錯誤提示且引擎未被呼叫。

    側信道：monkeypatch build_engine 計數——被呼叫即失敗；任務也不該建立。
    （override 路徑 `_resolve_task_engine` 建引擎前查 key——票 19 設計。）
    #85：暫存不觸發 key 檢查——按「開始翻譯」消費暫存時才攔。
    """
    calls = []

    def spy_build_engine(spec, api_key=""):
        calls.append(spec.id)
        raise AssertionError("無 key 引擎不應被建")

    from paper_kit.infrastructure.engine_registry import ENGINE_SPECS

    service, settings, cost, glossaries = _build(tmp_path)
    # 物件式 patch：分裂免疫（conftest unload 後 dotted-path 會 patch 到別 module）
    monkeypatch.setattr(app_module, "build_engine", spy_build_engine)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _engine_card(user, "deepseek").click()  # 未設 deepseek key
        upload_el = next(iter(user.find(ui.upload).elements))
        await upload_el.handle_uploads([
            SmallFileUpload(
                name="N1.pdf",
                content_type="application/pdf",
                _data=make_blank_pdf(tmp_path / "N1.pdf").read_bytes(),
            ),
        ])
        await user.should_see("已暫存：N1.pdf", retries=20)
        assert calls == [], "暫存不應觸發引擎建置"
        user.find("📂 開始翻譯").click()  # 消費暫存 → 建引擎前查 key
        msg = f"尚未設定 {ENGINE_SPECS['deepseek'].label} 的 API key（設定頁填入後再翻譯）"
        await user.should_see(msg, retries=20)
        assert calls == [], f"引擎不應被呼叫，實際呼叫：{calls}"
        assert service.list_jobs() == [], "無 key 不應建立任務"


@pytest.mark.asyncio
async def test_job_card_shows_engine_label_not_raw_id(tmp_path, monkeypatch, make_blank_pdf):
    """AC3：任務卡顯示引擎名稱（非 raw id）——完成卡片 meta 含 label。

    （未點引擎卡 → 走 global 路徑 → settings.resolve_engine seam，同既有測試。）
    票 19 spec review：純 content 匹配是假陽性（引擎卡自身也有 spec.label）——
    必須以 job-card marker 限定任務卡，再斷言其內文字含引擎 label。
    """
    from test_ui_flow import FileWritingFakeEngine

    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_engine("siliconflow")
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        real_pdf = make_blank_pdf(tmp_path / "E3.pdf")
        await upload_el.handle_uploads([
            SmallFileUpload(name="E3.pdf", content_type="application/pdf", _data=real_pdf.read_bytes()),
        ])
        await user.should_see("已暫存：E3.pdf", retries=20)
        user.find("📂 開始翻譯").click()  # #85：暫存 → 消費建任務
        await user.should_see("任務已建立", retries=20)
        # 等 timer 刷新把完成卡片 meta（含引擎 label）渲染出來——
        # bisect 實證：sleep 一段再 find（重複 find 會撞 timer 重畫空窗）
        engine_label = "SiliconFlow gemma-4-31B-it"
        cards = []
        for _ in range(5):
            await asyncio.sleep(1.0)
            cards = user.find(kind=ui.card, marker="job-card").elements
            if cards:
                break
        assert cards, "上傳後應有任務卡（job-card marker）"
        texts = _collect_label_texts(next(iter(cards)))
        # meta 是整行「任務 xxx · 時間 · label」——substring 檢查（in texts 是成員等於，會漏）
        assert any(engine_label in t for t in texts), f"任務卡 meta 應含引擎 label，實際文字：{texts}"
        job = service.list_jobs()[-1]
        assert job.engine_id == "siliconflow", "對照組：raw id 是 siliconflow，與 label 不同"


# ── 2026-08-12 使用者實測 bug 回歸 ────────────────────────────


@pytest.mark.asyncio
async def test_refresh_replaces_cards_not_duplicates(
    tmp_path, monkeypatch, make_blank_pdf
):
    """使用者實測：任務卡＋錯誤行每秒疊加到最下面。

    根因：_refresh 每秒 cards.clear() 但 _render_card 的 ui.card() 落在頁面
    root slot（沒進 cards 容器）——clear 清不到、每輪重畫疊加。
    修復後：多輪輪詢後 job-card 仍只有一張。
    """
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        real_pdf = make_blank_pdf(tmp_path / "CH4.pdf")
        await upload_el.handle_uploads([
            SmallFileUpload(
                name="CH4.pdf", content_type="application/pdf",
                _data=real_pdf.read_bytes(),
            ),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        user.find("📂 開始翻譯").click()  # #85：暫存 → 消費建任務
        await user.should_see("任務已建立", retries=20)
        await user.should_see("下載 mono", retries=50)  # 完成卡片
        await asyncio.sleep(2.2)  # 再等 ≥2 輪 1s 輪詢（疊加 bug 的觸發窗口）
        cards = user.find(kind=ui.card, marker="job-card").elements
        assert len(cards) == 1, f"輪詢重畫必須替換不疊加（實際 {len(cards)} 張）"


@pytest.mark.asyncio
async def test_start_button_uses_selected_files_not_picker(tmp_path):
    """使用者實測：拖放檔案後按「開始翻譯」又彈出檔案總管（舊世代 bug 回歸）。

    #85 新語意守衛：auto_upload=True（選檔＝上傳伺服器暫存，但**不建任務**）＋
    「開始翻譯」＝消費暫存——改回 pickFiles（開檔案總管）或 auto_upload=False
    （回 queue 舊流程）都會紅。
    """
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        assert upload_el._props.get("auto-upload") is True, "選檔＝上傳伺服器暫存（#85 契約）"
        # 按鈕存在且可點（無頭環境不真執行 JS）
        user.find("📂 開始翻譯").click()
        await user.should_see("選擇檔案後按「開始翻譯」送出")


# ── #85：BabelDOC 風格頁面範圍下拉（N of M）＋僅選中頁面 toggle ──


@pytest.mark.asyncio
async def test_upload_shows_page_range_dropdown_with_page_count(
    tmp_path, make_blank_pdf
):
    """#85：上傳後伺服器讀頁數 → 頁面範圍下拉選項＝頁碼（BabelDOC「N of M」）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        pdf = make_blank_pdf(tmp_path / "CH4.pdf", pages=3)
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        # 下拉選項＝頁碼（最近上傳檔案的頁數）＋計數 label
        page_select = next(
            s for s in user.find(ui.select).elements if "頁面範圍" in (s.label or "")
        )
        assert page_select.options == ["1", "2", "3"], f"下拉應列出頁碼，實際 {page_select.options}"
        await user.should_see("已選 0 of 3 頁", retries=5)
        await user.should_see("僅翻譯選中頁面", retries=5)


@pytest.mark.asyncio
async def test_selected_pages_flow_into_job_pages(
    tmp_path, monkeypatch, make_blank_pdf
):
    """#85：下拉選頁 → 開始翻譯 → job.pages 為選中頁碼（"1,3" 式範圍）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        pdf = make_blank_pdf(tmp_path / "CH4.pdf", pages=3)
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        page_select = next(
            s for s in user.find(ui.select).elements if "頁面範圍" in (s.label or "")
        )
        page_select.value = ["1", "3"]  # 選第 1、3 頁
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        job = service.list_jobs()[-1]
        assert job.pages == "1,3", f"選中頁碼應記入 job.pages，實際 {job.pages!r}"
        assert job.only_selected_pages is True, "toggle 預設 ON"


@pytest.mark.asyncio
async def test_only_selected_pages_toggle_off_flows_into_job(
    tmp_path, monkeypatch, make_blank_pdf
):
    """#85：「僅翻譯選中頁面」toggle OFF → job.only_selected_pages False（引擎
    輸出全部頁面、未選頁原樣保留——不送 --only-include-translated-page）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        pdf = make_blank_pdf(tmp_path / "CH4.pdf", pages=2)
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        toggle = next(
            c for c in user.find(ui.checkbox).elements if "僅翻譯選中頁面" in (c.text or "")
        )
        toggle.value = False
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        job = service.list_jobs()[-1]
        assert job.only_selected_pages is False, "toggle OFF 應記入 job"


# ── #85 切片B：術語庫選擇移入主翻譯面板 ──


def _seed_glossary(tmp_path, name: str) -> None:
    """造一份術語表（repo 直寫——主面板下拉選項來源）。"""
    from paper_kit.domain.glossary import Glossary
    from paper_kit.infrastructure.glossary_repo import GlossaryRepository

    repo = GlossaryRepository(tmp_path / "glossaries")
    repo.create(name)
    repo.write(name, Glossary.parse("source,target\nterm,譯\n", target_lang="zh"))


@pytest.mark.asyncio
async def test_main_panel_glossary_selection_flows_into_job(
    tmp_path, monkeypatch, make_blank_pdf
):
    """#85 切片B：主面板術語表多選——勾選後翻譯的 job 帶該術語表（側信道
    job.glossary_files）；預設值＝設定頁選擇（雙向同步同一 settings 後端）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    _seed_glossary(tmp_path, "dl")
    _seed_glossary(tmp_path, "img")
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        g_select = next(
            s for s in user.find(ui.select).elements if "術語表" in (s.label or "")
        )
        assert set(g_select.value) == {"dl", "img"}, "預設全選（與設定頁一致）"
        g_select.value = ["dl"]  # 只留 dl
        assert settings.selected_glossary_names(glossaries.list_glossaries()) == ["dl"], \
            "主面板勾選即寫入 settings（雙向同步）"
        upload_el = next(iter(user.find(ui.upload).elements))
        pdf = make_blank_pdf(tmp_path / "CH4.pdf", pages=2)
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        job = service.list_jobs()[-1]
        names = [Path(p).stem for p in job.glossary_files]
        assert names == ["dl"], f"job 應帶勾選的術語表，實際 {names}"


# ── #85 切片D：免費額度資訊條（0/500,000 Tokens） ──


def _completed_job(job_id: str, *, in_t: int, out_t: int):
    """造一筆已完成任務（領域狀態機＋result）——聚合額度的唯一來源。"""
    from paper_kit.domain.job_result import JobResult
    from paper_kit.domain.translation_job import JobStatus, TranslationJob

    job = TranslationJob(job_id=job_id, source_path="/out/x.pdf")
    job.transition(JobStatus.TRANSLATING)
    job.transition(JobStatus.COMPLETED)
    job.result = JobResult(
        mono_path="/out/x.zh-TW.mono.pdf", dual_path="/out/x.zh-TW.dual.pdf",
        input_tokens=in_t, output_tokens=out_t,
    )
    return job


def test_aggregate_used_tokens_counts_only_completed():
    """#85 切片D：已用 tokens＝已完成任務 in+out 加總；失敗/排隊/翻譯中不計。"""
    from paper_kit.domain.job_result import JobResult
    from paper_kit.domain.translation_job import JobStatus, TranslationJob
    from paper_kit.presentation.handlers import _aggregate_used_tokens, _quota_label

    done = _completed_job("a", in_t=3000, out_t=7000)
    failed = TranslationJob(job_id="b", source_path="/out/x.pdf")
    failed.transition(JobStatus.TRANSLATING)
    failed.transition(JobStatus.FAILED)  # 失敗 → 不計入（就算有 result 也不計）
    failed.result = JobResult(
        mono_path="/out/x.mono.pdf", dual_path="/out/x.dual.pdf",
        input_tokens=9999, output_tokens=9999,
    )
    jobs = [done, failed, TranslationJob(job_id="c", source_path="/out/y.pdf")]
    assert _aggregate_used_tokens(jobs) == 10_000
    assert _aggregate_used_tokens([]) == 0
    assert _quota_label(10_000) == "免費額度 10,000/500,000 Tokens"
    assert _quota_label(0) == "免費額度 0/500,000 Tokens"


@pytest.mark.asyncio
async def test_free_quota_bar_shows_aggregated_tokens(tmp_path, make_blank_pdf):
    """#85 切片D：主面板頂部額度條——無任務顯示 0/500,000；已有完成任務
    的 tokens 聚合顯示（timer 1s 輪詢刷新，側信道文字）。"""
    from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
    from paper_kit.presentation.app import _index_page

    repo = InMemoryJobRepository()
    done = _completed_job("q1", in_t=3000, out_t=7000)
    repo.add(done)
    service = JobService(jobs=repo, outputs_dir=tmp_path / "outputs")
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        await user.should_see("免費額度 10,000/500,000 Tokens", retries=5)


# ── _pages_for_file：範圍套用單一檔案（純函式） ──


def test_pages_for_file_empty_selection_means_all():
    from paper_kit.presentation.handlers import _pages_for_file

    assert _pages_for_file([], 7) is None
    assert _pages_for_file(None, 7) is None


def test_pages_for_file_subset_and_full_selection():
    from paper_kit.presentation.handlers import _pages_for_file

    assert _pages_for_file(["1", "3"], 7) == "1,3"
    assert _pages_for_file(["3", "1", "2"], 7) == "1,2,3"  # 排序去重
    assert _pages_for_file(["1", "2", "3"], 3) is None  # 全選＝全部頁面


def test_pages_for_file_out_of_range_pages_dropped():
    from paper_kit.presentation.handlers import _pages_for_file

    # 檔案頁數不足 → 越界頁碼剔除；交集空 → None（全文，不把越界頁碼漏到引擎）
    assert _pages_for_file(["1", "5"], 3) == "1"
    assert _pages_for_file(["5"], 3) is None


# ── #27：翻譯頁數計算（total_pages 語意修正——挑 2 頁不可顯示 58 頁） ──


def test_translated_pages_selection_counts_selected():
    """挑 2 頁（29,30）→ 翻譯頁數 2（不是 PDF 總頁數 58——使用者實測 bug）。"""
    assert _translated_pages("29,30", 58) == 2
    assert _translated_pages("1,2,3", 58) == 3


def test_translated_pages_no_selection_uses_file_pages():
    """全文（無選取）→ 翻譯頁數＝PDF 總頁數。"""
    assert _translated_pages(None, 58) == 58
    assert _translated_pages("", 58) == 58


def test_translated_pages_no_info_returns_none():
    """檔案頁數讀不到（理論上不會）→ None（舊任務相容）。"""
    assert _translated_pages(None, None) is None
    assert _translated_pages("", 0) is None


# ── #20：瀏覽資料夾路徑語意正規化（純函式——使用者實測「點按無回應」） ──


def test_explorer_target_windows_path_passthrough():
    """Windows 路徑（使用者常見輸入）→ 原樣（explorer 直接可開，實測 C:\\ 開窗）。"""
    assert app_module._explorer_target(r"C:\Users\qaref\out") == r"C:\Users\qaref\out"


def test_explorer_target_unc_passthrough():
    assert (
        app_module._explorer_target(r"\\wsl.localhost\Ubuntu\home")
        == r"\\wsl.localhost\Ubuntu\home"
    )


def test_explorer_target_mnt_converts_to_drive():
    """WSL /mnt/c/... → C:\\...（手轉，免 subprocess——最可靠路徑）。"""
    assert app_module._explorer_target("/mnt/c/Users/qaref/out") == r"C:\Users\qaref\out"


def test_explorer_target_home_uses_wslpath():
    """WSL 家目錄（~/.paper_kit/outputs）→ wslpath -w 轉 \\\\wsl.localhost UNC。"""
    target = app_module._explorer_target("/home/qaref/.paper_kit/outputs")
    assert target.startswith(r"\\wsl.localhost")


def test_win_to_wsl_converts_drive_path():
    """Windows 路徑 → WSL 對應（mkdir 用：C:\\ → /mnt/c/）。"""
    assert app_module._win_to_wsl(r"C:\Users\qaref\out") == "/mnt/c/Users/qaref/out"
    assert app_module._win_to_wsl(r"D:\x\y") == "/mnt/d/x/y"


# ── #85 切片C：babeldoc 進階選項（僅 babeldoc 引擎顯示） ──


def _babeldoc_advanced_box(user):
    """BabelDOC 進階選項容器（marker 定位；預設隱藏、點 babeldoc 卡才顯示）。"""
    return next(iter(user.find(kind=ui.column, marker="babeldoc-advanced").elements))


@pytest.mark.asyncio
async def test_babeldoc_advanced_panel_hidden_by_default(tmp_path):
    """#85 切片C：進階選項（相容模式／行號增強／非公式線條／字體）預設隱藏——
    預設引擎（siliconflow）不消費 babeldoc 旗標，不該看到這些開關。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        # find 只回傳可見元素（only_visible=True）→ 預設隱藏＝find 不到 advanced_box。
        # 不能用 content="BabelDOC 進階選項" 子字串——#17 ⓘ 說明 tooltip
        # （ENGINE_INFO["babeldoc"]，在引擎卡上、預設可見）文案含同字樣會誤撈；
        # 改以 marker 精確定位（ancestors 檢查含 advanced_box 自身→隱藏時整樹不可見）。
        with pytest.raises(AssertionError):
            user.find(kind=ui.column, marker="babeldoc-advanced")


@pytest.mark.asyncio
async def test_babeldoc_advanced_panel_shows_when_babeldoc_selected(tmp_path):
    """#85 切片C：點選 BabelDOC 卡 → 進階選項區顯示（引擎＝babeldoc 才消費這些旗標）。
    （2026-08-13 灰化：付費卡需 key 才能點——先填 key。）"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("babeldoc", "bk-test")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _engine_card(user, "babeldoc").click()
        assert _babeldoc_advanced_box(user).visible is True, \
            "點選 babeldoc 卡後進階選項區應顯示"


@pytest.mark.asyncio
async def test_babeldoc_advanced_options_flow_into_job(
    tmp_path, monkeypatch, make_blank_pdf
):
    """#85 切片C：勾選進階選項＋選字體 → job 帶全部值（側信道）→ adapter 轉旗標。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("babeldoc", "sk-test")  # override 路徑建引擎前查 key
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _engine_card(user, "babeldoc").click()
        # 勾選：相容模式 ON、行號增強 OFF（預設 ON）、移除非公式線條 ON
        for label, value in (
            ("相容模式", True),
            ("行號增強", False),
            ("非公式線條", True),
        ):
            cb = next(
                c for c in user.find(ui.checkbox).elements if label in (c.text or "")
            )
            cb.value = value
        font_select = next(
            s for s in user.find(ui.select).elements if "字體" in (s.label or "")
        )
        font_select.value = "script"
        upload_el = next(iter(user.find(ui.upload).elements))
        pdf = make_blank_pdf(tmp_path / "CH4.pdf", pages=2)
        await upload_el.handle_uploads([
            SmallFileUpload(name="CH4.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：CH4.pdf", retries=20)
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        job = service.list_jobs()[-1]
        assert job.enhance_compatibility is True
        assert job.merge_alternating_line_numbers is False
        assert job.remove_non_formula_lines is True
        assert job.font_family == "script"


# ── 2026-08-13 批次 A：引擎卡移位／ⓘ 說明／一般文件說明／瀏覽資料夾 ──


def _dom_markers(root) -> list[tuple[str, str]]:
    """DFS 收集 (type, marker) 的 DOM 插入序。

    user.find 回傳 set（無序）——DOM 順序測試需自行走
    default_slot.children（插入序；2026-08-12 實證）。
    """
    out = []
    if getattr(root, "_markers", None):
        out.extend((type(root).__name__, m) for m in root._markers)
    for child in getattr(root, "default_slot", None) and root.default_slot.children or []:
        out.extend(_dom_markers(child))
    return out


@pytest.mark.asyncio
async def test_engine_cards_after_checks_before_output_area(tmp_path):
    """#16：引擎三卡在機密/掃描勾選**下方**、輸出區**上方**（DOM 插入序）——
    任務一多引擎卡不再被往下推（cards 容器最後建立）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        order = [m for _, m in _dom_markers(user.client.content)]
        assert order.index("info-sensitive") < order.index("engine-card-siliconflow"), (
            "引擎卡必須在「機密文件」勾選下方"
        )
        assert order.index("engine-card-siliconflow") < order.index("engine-card-deepseek")
        assert order.index("engine-card-deepseek") < order.index("engine-card-babeldoc")
        assert order.index("engine-card-babeldoc") < order.index("browse-output-dir"), (
            "引擎卡必須在輸出目錄/任務區上方"
        )


def _find_cards_container(el):
    """DFS 找「任務卡容器」——ui.column、classes 恰為 w-full gap-4（app.py 1751）。

    #22：卡片容器掉出 max-w-4xl 欄位時，此 DFS 在 root slot 直屬處也找得到——
    測的是「容器的 parent 是誰」，不是「存不存在」。
    """
    if isinstance(el, ui.column) and "gap-4" in el._classes and "max-w-4xl" not in el._classes:
        return el
    for child in getattr(el, "default_slot", None) and el.default_slot.children or []:
        found = _find_cards_container(child)
        if found is not None:
            return found
    return None


@pytest.mark.asyncio
async def test_job_cards_container_inside_maxw_column(tmp_path):
    """#22：任務卡容器必須是 max-w-4xl 欄位的**後代**（2026-08-13 使用者回報
    「任務歷史一整排填滿、與上方寬度不一、割裂」——cards 容器縮排掉出欄位、
    落在 root slot 時任務卡橫跨全頁寬；CDP 實測卡 L=316 R=1889 vs 欄位
    L=655 R=1551 定案；修復＝容器移回欄位內）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        cards = _find_cards_container(user.client.content)
        assert cards is not None, "找不到任務卡容器"
        # 父層存取：default_slot.parent 對 root 層級元素回傳自身——
        # 用 element._parent_slot()（weakref→Slot）→ .parent（Slot 所屬元素）
        parent_ref = cards._parent_slot
        parent = parent_ref().parent if parent_ref else None
        assert parent is not None and isinstance(parent, ui.column), (
            "任務卡容器必須在 ui.column 內（不可是 root slot 直屬）"
        )
        assert "max-w-4xl" in parent._classes, (
            "任務卡容器的父層必須是 max-w-4xl 欄位（卡片與上方內容同寬）"
        )


@pytest.mark.asyncio
async def test_engine_card_info_icons_exist(tmp_path):
    """#17：三張引擎卡各帶 ⓘ（hover 說明引擎差異）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        for eid in ("siliconflow", "deepseek", "babeldoc"):
            icons = user.find(kind=ui.icon, marker=f"info-engine-{eid}").elements
            assert len(icons) == 1, f"引擎卡 {eid} 應有且僅有一個 ⓘ"
            assert icons.pop().tooltip is not None, f"引擎卡 {eid} ⓘ 應有 tooltip"


@pytest.mark.asyncio
async def test_babeldoc_advanced_option_info_icons_exist(tmp_path):
    """#17：babeldoc 進階選項 4 個 ⓘ（相容模式/行號增強/非公式線條/字體）——
    先點 babeldoc 卡顯示進階區（find 預設 only_visible=True）。
    （2026-08-13 灰化：付費卡需 key 才能點——先填 key。）"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("babeldoc", "bk-test")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _engine_card(user, "babeldoc").click()
        for marker in ("info-compat", "info-merge-lines", "info-remove-lines", "info-font"):
            icons = user.find(kind=ui.icon, marker=marker).elements
            assert len(icons) == 1, f"{marker} ⓘ 應存在"
            assert icons.pop().tooltip is not None, f"{marker} ⓘ 應有 tooltip"


@pytest.mark.asyncio
async def test_normal_pdf_hint_label(tmp_path):
    """#18：機密/掃描都不勾的說明（一般 PDF 直接翻譯）——消除
    「為何不勾選也能開始翻譯」的誤解。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        await user.should_see("（都不勾選＝一般 PDF，直接翻譯）")


@pytest.mark.asyncio
async def test_browse_output_dir_button_calls_open_folder(tmp_path, monkeypatch):
    """#14：輸出目錄旁「📂 瀏覽資料夾」→ _open_folder（帶目前輸入路徑）。

    注意：app_module 必須在**檔案頂部** import（collection 時載入）——nicegui
    reset_globals 的 finally 會把非 tests. 前綴的 page-route module（app.py）
    從 sys.modules pop 掉；若在此函式內才 `from ... import app`，前一個測試
    跑完後會**重新載入**一份新 module——monkeypatch 打到新 module，但
    _index_page closure 查的是舊 module 的 _open_folder（未 patch）→ 靜默失效。
    """
    called: list = []
    monkeypatch.setattr(app_module, "_open_folder", lambda p: called.append(p))
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        user.find(kind=ui.button, marker="browse-output-dir").click()
        assert len(called) == 1, "按「瀏覽資料夾」應呼叫 _open_folder"
        assert "outputs" in str(called[0]), "應帶輸出目錄路徑（預設 ~/.paper_kit/outputs）"


@pytest.mark.asyncio
async def test_dialogs_closed_on_load(tmp_path):
    """#13 防護：頁面載入後所有 dialog 初始關閉——使用者回報「中央深灰色
    遮罩」經查證為 NiceGUI 斷線重連 overlay（非 dialog 自動開啟），
    此測試鎖定 dialog 不得初始開啟，防未來回歸。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        dialogs = user.find(ui.dialog).elements
        assert dialogs, "主頁應有刪除/預覽 dialog（頁面級單例，#82）"
        for d in dialogs:
            assert d.value is False, f"dialog 初始不得開啟（{d}）"


@pytest.mark.asyncio
async def test_completed_card_shows_pages_and_percent(tmp_path, monkeypatch, make_blank_pdf):
    """#15：完成卡進度框＝「完成 100% · N/N 頁」——不再只顯示「1」
    （NiceGUI LinearProgress show_value 默認 True 的內嵌 label）；
    bar show_value=False（size=4px，無內嵌值 label）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    monkeypatch.setattr(settings, "resolve_engine", lambda: FileWritingFakeEngine())

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        pdf = make_blank_pdf(tmp_path / "pages3.pdf", pages=3)
        upload_el = next(iter(user.find(ui.upload).elements))
        await upload_el.handle_uploads([
            SmallFileUpload(name="pages3.pdf", content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("已暫存：pages3.pdf", retries=20)
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        await user.should_see("完成", retries=50)
        card = next(iter(user.find(kind=ui.card, marker="job-card").elements))
        texts = _collect_label_texts(card)
        assert "完成 100% · 3/3 頁" in texts, f"完成卡應顯示「完成 100% · 3/3 頁」（got {texts}）"
        bar = next(iter(user.find(ui.linear_progress).elements))
        assert bar._props.get("size") == "4px", "show_value=False（無內嵌「1」label）"

# ── 票 27：LaTeX 源碼路線整合主 UI（.tex 自動鎖定、第 4 引擎卡、PDF 守衛）──


@pytest.mark.asyncio
async def test_engine_cards_include_latex_card(tmp_path):
    """票 27 切片B：主頁引擎卡含第 4 卡 LaTeX（engine-card-latex marker）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        card = _engine_card(user, "latex")
        assert len(card.elements) == 1, "主頁應有 LaTeX 引擎卡（第 4 卡）"


@pytest.mark.asyncio
async def test_tex_upload_auto_selects_latex_engine(tmp_path, monkeypatch):
    """票 27 切片A/C：上傳 .tex → 自動鎖 LaTeX 引擎（不點卡）→ 任務記 latex。

    build_engine 注入 FakeEngine（不打真 API）——key fallback 語意
    （latex 沿用 deepseek 槽位）由純函式測試 test_resolve_latex_engine_falls_back_to_deepseek_key
    單獨驗證（user_simulation 順序污染敏感，spy 不進 UI 測試）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("deepseek", "sk-ds-test")  # latex 共用 deepseek key
    monkeypatch.setattr(
        "paper_kit.presentation.app.build_engine",
        lambda spec, api_key="", **kw: FileWritingFakeEngine(),
    )

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        upload_el = next(iter(user.find(ui.upload).elements))
        await upload_el.handle_uploads([
            SmallFileUpload(
                name="paper.tex",
                content_type="application/x-tex",
                _data=(
                    rb"\documentclass{article}\n\begin{document}\n"
                    rb"Hello world\n\end{document}"
                ),
            ),
        ])
        await user.should_see("已暫存：paper.tex", retries=20)
        # 自動鎖定：LaTeX 卡高亮（ring-primary class——與點選引擎卡同款視覺）
        latex_card = _engine_card(user, "latex")
        card_el = next(iter(latex_card.elements))
        assert "ring-primary" in card_el.classes, \
            "上傳 .tex 後 LaTeX 卡應自動高亮（預設走 LaTeX）"
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        jobs = service.list_jobs()
        assert jobs and jobs[0].engine_id == "latex", \
            f".tex 任務應記 latex 引擎，實際 {jobs[0].engine_id if jobs else None}"


@pytest.mark.asyncio
async def test_latex_engine_rejects_pdf_upload(tmp_path, monkeypatch, make_blank_pdf):
    """票 27 切片B AC4：選 LaTeX 卡＋上傳 PDF → 前置擋下（notify）＋不建任務。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("deepseek", "sk-ds-test")
    monkeypatch.setattr(
        "paper_kit.presentation.app.build_engine",
        lambda spec, api_key="", **kw: FileWritingFakeEngine(),
    )

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _engine_card(user, "latex").click()
        pdf = make_blank_pdf(tmp_path / "P.pdf")
        upload_el = next(iter(user.find(ui.upload).elements))
        await upload_el.handle_uploads([
            SmallFileUpload(
                name="P.pdf", content_type="application/pdf", _data=pdf.read_bytes()
            ),
        ])
        await user.should_see("已暫存：P.pdf", retries=20)
        user.find("📂 開始翻譯").click()
        await user.should_see("僅適用 .tex", retries=20)
        assert service.list_jobs() == [], "LaTeX 引擎＋PDF 不得建立任務"

def test_resolve_latex_engine_falls_back_to_deepseek_key(tmp_path, monkeypatch):
    """票 27 切片A：latex 未獨立填 key → 沿用 deepseek 槽位（同後端
    deepseek-chat，README 唯一推薦後端）；build_engine 收到 deepseek key。
    純函式（不經 user_simulation——UI 測試順序污染敏感）。"""
    from paper_kit.infrastructure.engine_registry import ENGINE_SPECS

    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("deepseek", "sk-ds-test")
    seen: dict = {}

    def spy(spec, api_key="", **kw):
        seen["eid"] = spec.id
        seen["key"] = api_key
        return FileWritingFakeEngine()

    monkeypatch.setattr(app_module, "build_engine", spy)
    # 分裂免疫：unload 後函式內 from-import 會拿新 module（patch 舊 module 無效）——
    # 直接經 app_module 物件取屬性（同一 globals 字典）
    _resolve_task_engine = app_module._resolve_task_engine
    eid, engine = _resolve_task_engine(settings, "latex")
    assert eid == "latex"
    assert seen.get("eid") == "latex"
    assert seen.get("key") == "sk-ds-test", "latex 未填 key 時應 fallback deepseek key"
    assert ENGINE_SPECS["latex"].id == "latex"


def test_resolve_latex_engine_raises_without_any_key(tmp_path, monkeypatch):
    """票 27：latex 與 deepseek 都無 key → 友善錯誤（不 build_engine）。"""
    from paper_kit.presentation.app import _resolve_task_engine
    from paper_kit.application.ports import EngineError

    service, settings, cost, glossaries = _build(tmp_path)
    with pytest.raises(EngineError, match="LaTeX"):
        _resolve_task_engine(settings, "latex")


# ── 免費翻譯入口（2026-08-13：交付他人免費翻譯、不動個人 API） ──────────


@pytest.mark.asyncio
async def test_free_engine_cards_render(tmp_path):
    """免費翻譯區渲染：header＋品質提示＋三張免費卡（marker 定位，與付費卡同機制）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        await user.should_see("免費翻譯（不需 API key）")
        user.find(marker="free-engine-hint")  # 品質提示存在
        for eid in ("siliconflowfree", "google", "bing"):
            card = _engine_card(user, eid)
            assert next(iter(card.elements)), f"{eid} 免費卡應渲染"
            user.find(kind=ui.icon, marker=f"info-engine-{eid}")  # ⓘ tooltip 存在


@pytest.mark.asyncio
async def test_free_engine_selection_creates_job_without_key(tmp_path, monkeypatch, make_blank_pdf):
    """免費翻譯入口主流程：點免費卡不需任何 key → 任務建立且引擎被呼叫
    （側信道 job.engine_id＋build_engine spy——與 test_upload_with_missing_key_is_blocked
    的 calls==[] 相反語意：免費引擎應被呼叫且 api_key 為空）。"""
    from test_ui_flow import FileWritingFakeEngine

    calls = []

    def spy_build_engine(spec, api_key=""):
        calls.append((spec.id, api_key))
        return FileWritingFakeEngine()

    # 物件式 patch（分裂免疫）：conftest 的 nicegui_reset_globals 會在測試間
    # unload paper_kit.* module——dotted-path monkeypatch 會 re-import 出第二個
    # module，而本檔頂部 import 的 app_module／_index_page 仍引用舊 globals，
    # spy 永遠不被呼叫（2026-08-13 免費卡測試踩中：真 adapter 建出 → 缺 key 失敗）。
    monkeypatch.setattr(app_module, "build_engine", spy_build_engine)
    service, settings, cost, glossaries = _build(tmp_path)  # 全程不設任何 key

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        free_card = _engine_card(user, "siliconflowfree")
        card_el = next(iter(free_card.elements))
        assert "ring-primary" not in card_el.classes, "初始免費卡不應被選中（預設付費 siliconflow）"
        free_card.click()
        assert "ring-primary" in card_el.classes, "點選免費卡後應有選中高亮"
        pdf = make_blank_pdf(tmp_path / "FREE1.pdf")
        upload_el = next(iter(user.find(ui.upload).elements))
        await upload_el.handle_uploads([
            SmallFileUpload(name=pdf.name, content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("FREE1.pdf", retries=20)  # 暫存 label 出現
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        job = service.list_jobs()[-1]
        assert job.engine_id == "siliconflowfree", (
            f"點免費卡後任務應記 siliconflowfree，實際 {job.engine_id}"
        )
        # build_engine 在 background 翻譯執行時才呼叫（同既有測試模式）——
        # 等 FakeEngine 立即完成（背景執行寫檔）後 spy 必已收到呼叫；
        # 逾時失敗訊息帶 job.error 以利診斷
        from paper_kit.domain.translation_job import JobStatus
        import asyncio

        for _ in range(50):
            if service.list_jobs()[-1].status is JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.1)
        job = service.list_jobs()[-1]
        assert job.status is JobStatus.COMPLETED, f"翻譯未在時限內完成：{job.error}"
        assert calls == [("siliconflowfree", "")], (
            f"免費引擎應被呼叫且零 key（不動個人 API），實際 {calls}"
        )


def test_resolve_free_engine_requires_no_key(tmp_path, monkeypatch):
    """免費引擎解析不需 key：_resolve_task_engine 回 ("siliconflowfree", engine)
    且 build_engine 收到空 api_key（純函式——user_simulation 順序污染敏感，spy 拆出）。"""
    from test_ui_flow import FileWritingFakeEngine

    service, settings, cost, glossaries = _build(tmp_path)  # 不設任何 key
    seen: dict = {}

    def spy(spec, api_key="", **kw):
        seen["eid"] = spec.id
        seen["key"] = api_key
        return FileWritingFakeEngine()

    monkeypatch.setattr(app_module, "build_engine", spy)
    # 分裂免疫：unload 後函式內 from-import 會拿新 module（patch 舊 module 無效）——
    # 直接經 app_module 物件取屬性（同一 globals 字典）
    _resolve_task_engine = app_module._resolve_task_engine
    eid, engine = _resolve_task_engine(settings, "siliconflowfree")
    assert eid == "siliconflowfree"
    assert seen.get("eid") == "siliconflowfree"
    assert seen.get("key") == "", "免費引擎應收到空 key（不需 key、不動個人 API）"


# ── 切片 4-5：機密阻擋免費卡＋免費區 DOM 順序（2026-08-13） ──────────


def _sensitive_checkbox(user) -> ui.checkbox:
    """機密文件勾選框（同 test_sensitive_output_ui 的 helper）。"""
    return next(
        iter(
            c for c in user.find(ui.checkbox).elements
            if "機密" in (c.text or "")
        )
    )


@pytest.mark.asyncio
async def test_sensitive_blocks_free_engine_cards(tmp_path):
    """機密模式（票 10 紅線）：免費卡全禁用（sensitive_ok=False，同付費視覺卡）——
    勾機密 → 三卡灰化、點擊不切換（引擎仍 DeepSeek）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        for eid in ("siliconflowfree", "google", "bing"):
            card = next(iter(_engine_card(user, eid).elements))
            assert "pk-engine-card--disabled" in card.classes, f"{eid} 免費卡應禁用（機密紅線）"
        # 點免費卡不切換（仍 DeepSeek）
        _engine_card(user, "siliconflowfree").click()
        classes = next(iter(_engine_card(user, "deepseek").elements)).classes
        assert "ring-primary" in classes, "機密下點免費卡不得切換引擎"


@pytest.mark.asyncio
async def test_unchecking_sensitive_restores_free_engine_cards(tmp_path):
    """取消機密 → 免費卡解禁（與付費視覺卡同機制）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        _sensitive_checkbox(user).set_value(False)
        card = next(iter(_engine_card(user, "siliconflowfree").elements))
        assert "pk-engine-card--disabled" not in card.classes, "取消機密後免費卡應解禁"


@pytest.mark.asyncio
async def test_free_engine_section_dom_order(tmp_path):
    """免費翻譯區 DOM 位置：付費卡之後、目標語言/輸出區之前；區內
    header → hint → 三卡（siliconflowfree 首）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        order = [m for _, m in _dom_markers(user.client.content)]
        assert order.index("engine-card-babeldoc") < order.index("free-engine-section"), (
            "免費區必須在付費卡（babeldoc 末卡）之後"
        )
        assert order.index("free-engine-section") < order.index("free-engine-hint")
        assert order.index("free-engine-hint") < order.index("engine-card-siliconflowfree")
        assert order.index("engine-card-siliconflowfree") < order.index("engine-card-google")
        assert order.index("engine-card-google") < order.index("engine-card-bing")
        assert order.index("engine-card-bing") < order.index("browse-output-dir"), (
            "免費卡必須在輸出目錄/任務區上方"
        )


# ── 免費 LLM key 引擎（2026-08-13：Free-LLM-Collection 查證後加入，BYOK 免費 key）──


@pytest.mark.asyncio
async def test_free_key_engine_cards_render(tmp_path):
    """免費 LLM 區渲染：header＋品質提示＋6 張卡（依優先序）＋ⓘ tooltip。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        await user.should_see("免費 LLM（自備免費 key）")
        user.find(marker="free-key-engine-hint")  # 品質提示存在
        for eid in ("nvidia", "modelscope", "groq", "openrouter", "bigmodel", "gemini"):
            card = _engine_card(user, eid)
            assert next(iter(card.elements)), f"{eid} 免費 LLM 卡應渲染"
            user.find(kind=ui.icon, marker=f"info-engine-{eid}")  # ⓘ tooltip 存在


@pytest.mark.asyncio
async def test_free_key_engine_selection_passes_key(tmp_path, monkeypatch, make_blank_pdf):
    """免費 LLM 選卡→翻譯：BYOK 模式——填 key 後點卡，build_engine 收到該 key
    （與零 key 區的 api_key=="" 相反語意；「不能動用個人 API」紅線的另一面：
    免費 key 是使用者/他人自己申請的免費額度）。"""
    from test_ui_flow import FileWritingFakeEngine

    calls = []

    def spy_build_engine(spec, api_key="", **kw):
        calls.append((spec.id, api_key))
        return FileWritingFakeEngine()

    monkeypatch.setattr(app_module, "build_engine", spy_build_engine)
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("nvidia", "nvapi-test-free-key")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        nvidia_card = _engine_card(user, "nvidia")
        card_el = next(iter(nvidia_card.elements))
        assert "ring-primary" not in card_el.classes, "初始免費 LLM 卡不應被選中"
        nvidia_card.click()
        assert "ring-primary" in card_el.classes, "點選免費 LLM 卡後應有選中高亮"
        pdf = make_blank_pdf(tmp_path / "NIM1.pdf")
        upload_el = next(iter(user.find(ui.upload).elements))
        await upload_el.handle_uploads([
            SmallFileUpload(name=pdf.name, content_type="application/pdf", _data=pdf.read_bytes()),
        ])
        await user.should_see("NIM1.pdf", retries=20)
        user.find("📂 開始翻譯").click()
        await user.should_see("任務已建立", retries=20)
        from paper_kit.domain.translation_job import JobStatus

        for _ in range(50):
            if service.list_jobs()[-1].status is JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.1)
        job = service.list_jobs()[-1]
        assert job.status is JobStatus.COMPLETED, f"翻譯未在時限內完成：{job.error}"
        assert job.engine_id == "nvidia", f"任務應記 nvidia，實際 {job.engine_id}"
        assert calls == [("nvidia", "nvapi-test-free-key")], (
            f"免費 LLM 引擎應收到使用者自備的免費 key，實際 {calls}"
        )


def test_resolve_free_key_engine_requires_key(tmp_path, monkeypatch):
    """免費 LLM 解析需 key（BYOK）：未填 key 選卡翻譯被擋（友善訊息），
    填 key 後 build_engine 收到該 key（純函式）。"""
    from test_ui_flow import FileWritingFakeEngine

    service, settings, cost, glossaries = _build(tmp_path)
    seen: dict = {}

    def spy(spec, api_key="", **kw):
        seen["eid"] = spec.id
        seen["key"] = api_key
        return FileWritingFakeEngine()

    monkeypatch.setattr(app_module, "build_engine", spy)
    from paper_kit.application.ports import EngineError

    _resolve_task_engine = app_module._resolve_task_engine
    with pytest.raises(EngineError, match="尚未設定.*key"):
        _resolve_task_engine(settings, "groq")  # 未填 key → 擋
    settings.set_api_key("groq", "gsk-free-key")
    eid, engine = _resolve_task_engine(settings, "groq")
    assert eid == "groq"
    assert seen.get("key") == "gsk-free-key", "填 key 後應傳給引擎"


@pytest.mark.asyncio
async def test_sensitive_blocks_free_key_engine_cards(tmp_path):
    """機密模式（票 10 紅線）：免費 LLM 卡全禁用（免費層無 SLA／第三方雲端）——
    勾機密 → 6 卡灰化、點擊不切換（引擎仍 DeepSeek）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        _sensitive_checkbox(user).set_value(True)
        await user.should_see("本任務將使用 DeepSeek", retries=20)
        for eid in ("nvidia", "modelscope", "groq", "openrouter", "bigmodel", "gemini"):
            card = next(iter(_engine_card(user, eid).elements))
            assert "pk-engine-card--disabled" in card.classes, f"{eid} 免費 LLM 卡應禁用（機密紅線）"
        _engine_card(user, "nvidia").click()
        classes = next(iter(_engine_card(user, "deepseek").elements)).classes
        assert "ring-primary" in classes, "機密下點免費 LLM 卡不得切換引擎"


@pytest.mark.asyncio
async def test_free_key_engine_section_dom_order(tmp_path):
    """免費 LLM 區 DOM 位置：零 key 免費區之後（bing 末卡 → 新區 header → hint →
    6 卡依優先序 nvidia 首）；輸出目錄/任務區之前。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        order = [m for _, m in _dom_markers(user.client.content)]
        assert order.index("engine-card-bing") < order.index("free-key-engine-section"), (
            "免費 LLM 區必須在零 key 免費區（bing 末卡）之後"
        )
        assert order.index("free-key-engine-section") < order.index("free-key-engine-hint")
        assert order.index("free-key-engine-hint") < order.index("engine-card-nvidia")
        assert order.index("engine-card-nvidia") < order.index("engine-card-modelscope")
        assert order.index("engine-card-modelscope") < order.index("engine-card-groq")
        assert order.index("engine-card-groq") < order.index("engine-card-openrouter")
        assert order.index("engine-card-openrouter") < order.index("engine-card-bigmodel")
        assert order.index("engine-card-bigmodel") < order.index("engine-card-gemini")
        assert order.index("engine-card-gemini") < order.index("browse-output-dir"), (
            "免費 LLM 卡必須在輸出目錄/任務區上方"
        )


# ── 付費卡灰化（2026-08-13 使用者要求：無 API key 時 4 付費卡灰色不可點）──


@pytest.mark.asyncio
async def test_paid_cards_greyed_out_without_key(tmp_path):
    """無任何 API key：4 張付費卡（siliconflow/deepseek/babeldoc/latex）灰化
    （pk-engine-card--disabled）且點擊不切換（notify 阻擋）。"""
    service, settings, cost, glossaries = _build(tmp_path)  # 不設任何 key

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        for eid in ("siliconflow", "deepseek", "babeldoc", "latex"):
            card = next(iter(_engine_card(user, eid).elements))
            assert "pk-engine-card--disabled" in card.classes, (
                f"{eid} 付費卡無 key 應灰化"
            )
        # 點擊付費卡（deepseek，非預設）→ 阻擋：不切換＋警告通知
        deepseek = next(iter(_engine_card(user, "deepseek").elements))
        _engine_card(user, "deepseek").click()
        assert "ring-primary" not in deepseek.classes, "無 key 時點付費卡不得切換"
        await user.should_see("尚未設定", retries=20)  # 警告通知出現


@pytest.mark.asyncio
async def test_free_key_cards_greyed_out_without_key(tmp_path):
    """免費 LLM 卡（BYOK）無 key 也灰化——沒 key 不能翻譯，提示去設定頁填。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        for eid in ("nvidia", "modelscope", "groq", "openrouter", "bigmodel", "gemini"):
            card = next(iter(_engine_card(user, eid).elements))
            assert "pk-engine-card--disabled" in card.classes, f"{eid} 免費 LLM 卡無 key 應灰化"


@pytest.mark.asyncio
async def test_paid_card_unlocks_after_key_set(tmp_path):
    """設定 key 後（重開頁）付費卡解禁——灰化以「是否有 key」為準，不是永久灰。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("deepseek", "sk-ds-key")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        card = next(iter(_engine_card(user, "deepseek").elements))
        assert "pk-engine-card--disabled" not in card.classes, "填 key 後付費卡應解禁"
        # 其餘無 key 付費卡仍灰（latex 例外——沿用 deepseek 槽位語意，同 _resolve）
        for eid in ("siliconflow", "babeldoc"):
            c = next(iter(_engine_card(user, eid).elements))
            assert "pk-engine-card--disabled" in c.classes, f"{eid} 未填 key 仍應灰化"


@pytest.mark.asyncio
async def test_free_key_card_unlocks_after_key_set(tmp_path):
    """免費 LLM 卡填 key 後解禁（BYOK 流程完整）。"""
    service, settings, cost, glossaries = _build(tmp_path)
    settings.set_api_key("nvidia", "nvapi-test")

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_twice(user)
        card = next(iter(_engine_card(user, "nvidia").elements))
        assert "pk-engine-card--disabled" not in card.classes, "免費 LLM 填 key 後應解禁"
