"""/settings 頁渲染回歸測試（2026-08-12 使用者實測 500：NameError: engine_id）。

bug 根因：settings_page 依賴 bind_value_to(locals(), ...) 寫回變數，
但渲染當下（單價卡 `pricing_for(engine_id)`）與儲存 lambda 讀取時，
綁定事件從未觸發 → 變數不存在。本測試用 NiceGUI 官方
user_simulation 開真實 /settings 頁——渲染拋任何例外都會 500。
"""

import pytest
from nicegui import ui
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _settings_page


@pytest.mark.asyncio
async def test_settings_page_renders_without_error(tmp_path):
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        # user_simulation 的 root 在首個 request 時才註冊路由——
        # 第一次 open 為暖身（404 骨架），第二次才是真實渲染。
        await user.open("/settings")
        client = await user.open("/settings")
        assert client is not None
        # 326 行（pricing_for(engine_id)）之後的元件必須渲染完成——
        # 若引擎卡例外中斷，術語表卡（343 行）不會出現。
        await user.should_see("術語表庫")
    # 隔離：user_simulation 退出殘留 Client.instances → 污染後續
    # sync 測試（slot stack is empty）。由 conftest.py 的
    # _nicegui_reset_between_tests（autouse）在每個測試進入前清理。


@pytest.mark.asyncio
async def test_settings_page_save_engine_without_touching_inputs(tmp_path):
    """使用者「不修改就按儲存」路徑：lambda 讀的變數必須已初始化。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")  # 暖身（見 test_settings_page_renders_without_error）
        await user.open("/settings")
        user.find("儲存引擎設定").click()
        await user.should_see("引擎設定已儲存")


# ── 票 20：每引擎獨立 API key 欄位＋遮罩＋清除 ────────────────


def _engine_key_input(user, eid: str):
    """引擎 key input（marker 定位——input 在引擎卡內，content 匹配會撈到別的 input）。"""
    return next(iter(user.find(kind=ui.input, marker=f"engine-key-input-{eid}").elements))


def _engine_key_save_button(user, eid: str):
    """引擎卡「儲存 key」按鈕（marker 定位——三張卡同名按鈕，content 撈到多個）。"""
    return user.find(kind=ui.button, marker=f"engine-key-save-{eid}")


def test_mask_key_masks_all_but_first_six_chars():
    """遮罩：前 6 字符＋其餘星號；短 key 全星號；空 key 空字串。"""
    from paper_kit.presentation.app import _mask_key

    assert _mask_key("sk-test123456") == "sk-tes*******"
    assert _mask_key("abc") == "***"
    assert _mask_key("") == ""


@pytest.mark.asyncio
async def test_settings_page_shows_three_engine_key_cards_with_masking(tmp_path):
    """AC1+AC3：三張引擎卡各有獨立 key 欄位；已存 key 回顯遮罩（前 6＋星號）。

    （字面值斷言——standards review：用 `_mask_key(...)` 算預期值是 tautology；
    遮罩格式已由 test_mask_key_masks_all_but_first_six_chars 釘死。）
    """
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    settings.set_api_key("deepseek", "sk-test123456")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        for label in ("SiliconFlow", "DeepSeek", "BabelDOC"):
            await user.should_see(label)
        deepseek_input = _engine_key_input(user, "deepseek")
        assert deepseek_input.value == "sk-tes*******", "已存 key 應遮罩回顯（前 6 字符＋星號）"
        assert _engine_key_input(user, "siliconflow").value == "", "未存引擎 input 應為空"


@pytest.mark.asyncio
async def test_engine_key_cards_use_theme_card_tokens(tmp_path):
    """2026-08-13 使用者二次回報「框框大小不一致」：設定頁三張引擎子卡
    必須套主題卡樣式（.pk-card——border/radius/shadow 與主頁卡同一 token
    來源），不留在 Quasar 默認樣式造成跨頁視覺分歧。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        for eid in ("siliconflow", "deepseek", "babeldoc"):
            card = next(iter(user.find(kind=ui.card, marker=f"engine-key-{eid}").elements))
            assert "pk-card" in card.classes, f"引擎子卡 {eid} 應套 .pk-card（主題 token）"


@pytest.mark.asyncio
async def test_save_key_stores_only_that_engine(tmp_path):
    """AC2+AC3：儲存一卡的 key 只寫該引擎；他引擎 key 不受影響。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    settings.set_api_key("siliconflow", "sf-original")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        deepseek_input = _engine_key_input(user, "deepseek")
        deepseek_input.value = "sk-new-deepseek"
        _engine_key_save_button(user, "deepseek").click()
        await user.should_see(f"已儲存 {ENGINE_SPECS['deepseek'].label} 的 API key")
        assert settings.api_key("deepseek") == "sk-new-deepseek", "handler 應已寫入 key"
        assert settings.api_key("siliconflow") == "sf-original", "儲存他卡不覆寫"


@pytest.mark.asyncio
async def test_save_with_masked_value_does_not_overwrite(tmp_path):
    """防遮罩寫回：input 回顯的是遮罩——不修改直接儲存不得把遮罩當 key 存。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    settings.set_api_key("siliconflow", "sk-original-123")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        _engine_key_save_button(user, "siliconflow").click()  # 不修改 input（遮罩原樣）
        await user.should_see(f"已儲存 {ENGINE_SPECS['siliconflow'].label} 的 API key")
        assert settings.api_key("siliconflow") == "sk-original-123", "遮罩不得寫回成 key"


@pytest.mark.asyncio
async def test_clear_key_button_empties_key(tmp_path):
    """AC4：清除按鈕清空後 api_key 回傳空。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    settings.set_api_key("babeldoc", "bk-original")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        babeldoc_input = _engine_key_input(user, "babeldoc")
        user.find(kind=ui.button, marker="engine-key-clear-babeldoc").click()
        await user.should_see(f"已清除 {ENGINE_SPECS['babeldoc'].label} 的 API key")
        assert settings.api_key("babeldoc") == ""
        # spec review（票 20）：清除後 input 顯示值也必須清空——否則殘留遮罩
        # 在「清除後再按儲存」時會被 `_save_engine_key` 當新 key 寫回（current=""
        # 時任何值都過防遮罩判斷），key 損毀且不可復原
        assert babeldoc_input.value == "", "清除後 input 顯示值應為空"



# ── 票 25：設定頁翻譯快取區（開關＋統計＋清除） ───────────────


def _term_key_input(user, eid: str):
    """術語提取 key input（marker 定位——siliconflow 卡內獨立欄）。"""
    return next(iter(user.find(kind=ui.input, marker=f"term-key-input-{eid}").elements))


def _term_key_save_button(user, eid: str):
    return user.find(kind=ui.button, marker=f"term-key-save-{eid}")


# ── #84：術語提取 key 獨立化（設定頁入口） ─────────────────


@pytest.mark.asyncio
async def test_settings_page_term_key_field_renders(tmp_path):
    """#84：siliconflow 卡有「術語提取 API key」欄（term 引擎＝SiliconFlow 專屬）。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        _term_key_input(user, "siliconflow")  # 不存在會 raise
        await user.should_see("術語提取 API key")


@pytest.mark.asyncio
async def test_save_term_key_stores_independently(tmp_path):
    """#84：儲存術語提取 key → 寫入 term_api_key；主引擎 key 不受影響。"""
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    settings.set_api_key("siliconflow", "sf-main-original")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        term_input = _term_key_input(user, "siliconflow")
        term_input.value = "sf-term-new"
        _term_key_save_button(user, "siliconflow").click()
        await user.should_see("已儲存術語提取 key")
        assert settings.term_api_key("siliconflow") == "sf-term-new"
        assert settings.api_key("siliconflow") == "sf-main-original", "術語 key 不得覆寫主 key"


def _cache_toggle(user) -> ui.switch:
    """「啟用翻譯快取」開關（label 過濾——設定頁有多個 switch）。"""
    return next(
        iter(s for s in user.find(ui.switch).elements if "啟用翻譯快取" in (s.text or ""))
    )


def _build_settings(tmp_path):
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    return settings, cost, glossaries


@pytest.mark.asyncio
async def test_settings_page_cache_section_renders(tmp_path):
    """票 25：設定頁有「翻譯快取」卡（啟用開關＋統計＋清除按鈕）。"""
    from paper_kit.application.translation_cache import TranslationCache

    settings, cost, glossaries = _build_settings(tmp_path)
    cache = TranslationCache(tmp_path / "cache")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries, cache)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        await user.should_see("翻譯快取")
        await user.should_see("啟用翻譯快取")
        await user.should_see("清除快取")


@pytest.mark.asyncio
async def test_cache_toggle_updates_setting_and_runtime(tmp_path):
    """票 25：切「啟用翻譯快取」開關 → settings.cache_enabled 更新＋cache.enabled 即時生效。"""
    from paper_kit.application.translation_cache import TranslationCache

    settings, cost, glossaries = _build_settings(tmp_path)
    cache = TranslationCache(tmp_path / "cache")

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries, cache)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        _cache_toggle(user).set_value(False)
        assert settings.cache_enabled() is False, "開關應寫回設定（持久化）"
        assert cache.enabled is False, "開關應即時同步 runtime cache（不需重啟）"
        _cache_toggle(user).set_value(True)
        assert settings.cache_enabled() is True
        assert cache.enabled is True


@pytest.mark.asyncio
async def test_cache_stats_shown(tmp_path):
    """票 25：統計顯示「快取 N 筆 · X MB」（檔案掃描實算）。"""
    from paper_kit.application.translation_cache import TranslationCache

    settings, cost, glossaries = _build_settings(tmp_path)
    cache = TranslationCache(tmp_path / "cache")
    # 兩筆快取：mono 檔各 10KB（放得進 stats 的檔案掃描）
    for i in range(2):
        f = tmp_path / f"m{i}.pdf"
        f.write_bytes(b"x" * 10240)
        cache.put(f"fp{i}", str(f), None)

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries, cache)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        await user.should_see("快取 2 筆", retries=20)


@pytest.mark.asyncio
async def test_clear_cache_button_clears(tmp_path):
    """票 25：「清除快取」→ 快取檔刪除、統計歸零。"""
    from paper_kit.application.translation_cache import TranslationCache

    settings, cost, glossaries = _build_settings(tmp_path)
    cache = TranslationCache(tmp_path / "cache")
    f = tmp_path / "m.pdf"
    f.write_bytes(b"x" * 1024)
    cache.put("fp", str(f), None)
    assert cache.stats()[0] == 1

    async with user_simulation(
        root=lambda: _settings_page(settings, cost, glossaries, cache)
    ) as user:
        await user.open("/settings")
        await user.open("/settings")
        user.find("清除快取").click()
        await user.should_see("快取已清除", retries=20)
        assert cache.stats() == (0, 0), "清除後快取應歸零"
