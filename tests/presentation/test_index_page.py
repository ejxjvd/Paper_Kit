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
    """上傳 CH4.pdf → 任務卡片出現 → FakeEngine 完成 → 下載連結出現。

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
    """點選 DeepSeek 引擎卡 → 上傳 pdf → 等任務出現。"""
    _engine_card(user, "deepseek").click()
    upload_el = next(iter(user.find(ui.upload).elements))
    await upload_el.handle_uploads([
        SmallFileUpload(name=pdf.name, content_type="application/pdf", _data=pdf.read_bytes()),
    ])
    await user.should_see(pdf.name, retries=20)


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
        lang_select = next(iter(user.find(ui.select).elements))
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
        lang_select = next(iter(user.find(ui.select).elements))
        assert lang_select.value == "ja", "設定值應被併入選項並保持為下拉值"


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
        await user.should_see("E3.pdf", retries=20)
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
