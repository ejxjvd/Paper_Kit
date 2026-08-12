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
from paper_kit.presentation.app import _index_page

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
    """點選引擎卡後該卡有選中視覺（ring-primary），提示本任務引擎。"""
    service, settings, cost, glossaries = _build(tmp_path)

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
    monkeypatch.setattr("paper_kit.presentation.app.build_engine", spy_build_engine)

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


# ── _pages_for_file：範圍套用單一檔案（純函式） ──


def test_pages_for_file_empty_selection_means_all():
    from paper_kit.presentation.app import _pages_for_file

    assert _pages_for_file([], 7) is None
    assert _pages_for_file(None, 7) is None


def test_pages_for_file_subset_and_full_selection():
    from paper_kit.presentation.app import _pages_for_file

    assert _pages_for_file(["1", "3"], 7) == "1,3"
    assert _pages_for_file(["3", "1", "2"], 7) == "1,2,3"  # 排序去重
    assert _pages_for_file(["1", "2", "3"], 3) is None  # 全選＝全部頁面


def test_pages_for_file_out_of_range_pages_dropped():
    from paper_kit.presentation.app import _pages_for_file

    # 檔案頁數不足 → 越界頁碼剔除；交集空 → None（全文，不把越界頁碼漏到引擎）
    assert _pages_for_file(["1", "5"], 3) == "1"
    assert _pages_for_file(["5"], 3) is None
