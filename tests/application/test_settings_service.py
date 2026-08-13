"""SettingsService（application）：設定 ↔ repo 的 typed 存取＋引擎解析。

驗證：預設引擎/語言、set 後解析出對應引擎、缺 key 給友善錯誤、
換引擎＝下一次翻譯走新引擎（FakeEngine 證明 UI 零改動由 01 測試守住）。
"""

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.babeldoc_adapter import BabelDocAdapter
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS
from paper_kit.infrastructure.ppt_vision_adapter import PptVisionAdapter
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository


def make_service(tmp_path) -> SettingsService:
    return SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))


def test_defaults_are_siliconflow_and_traditional_chinese(tmp_path):
    svc = make_service(tmp_path)
    assert svc.engine_id() == "siliconflow"
    assert svc.target_lang() == "zh-TW"


def test_set_engine_and_resolve_returns_new_engine(tmp_path):
    svc = make_service(tmp_path)
    svc.set_api_key("deepseek", "DS-KEY")
    svc.set_engine("deepseek")
    engine = svc.resolve_engine()
    assert engine._config.provider == "deepseek"  # 換引擎＝下一次翻譯走新引擎
    assert svc.engine_id() == "deepseek"


def test_set_unknown_engine_rejected(tmp_path):
    svc = make_service(tmp_path)
    with pytest.raises(KeyError):
        svc.set_engine("no-such-engine")


def test_babeldoc_engine_resolves_through_registry(tmp_path):
    """票 13：換插頭不破壞——babeldoc 走同一 resolve 路徑（needs_key 守證）。"""
    svc = make_service(tmp_path)
    with pytest.raises(EngineError, match="API key"):
        svc.resolve_engine()  # 預設 siliconflow 也缺 key——先設 babeldoc
    svc.set_engine("babeldoc")
    with pytest.raises(EngineError, match="API key"):
        svc.resolve_engine()  # babeldoc needs_key：缺 key 友善錯誤
    svc.set_api_key("babeldoc", "BK")
    engine = svc.resolve_engine()
    assert isinstance(engine, BabelDocAdapter)
    assert engine._config.api_key == "BK"


def test_resolve_engine_missing_key_gives_friendly_error(tmp_path):
    svc = make_service(tmp_path)
    with pytest.raises(EngineError, match="API key"):
        svc.resolve_engine()


def test_ppt_vision_engine_resolves_through_registry(tmp_path):
    """票 14：PPT 視覺走同一 resolve 路徑（needs_key 守證，UI 引擎下拉自動出現）。"""
    svc = make_service(tmp_path)
    svc.set_engine("ppt-vision")
    with pytest.raises(EngineError, match="API key"):
        svc.resolve_engine()  # needs_key：缺 key 友善錯誤
    svc.set_api_key("ppt-vision", "SF-KEY")
    engine = svc.resolve_engine()
    assert isinstance(engine, PptVisionAdapter)
    assert engine._config.api_key == "SF-KEY"


def test_api_key_roundtrip(tmp_path):
    svc = make_service(tmp_path)
    svc.set_api_key("deepseek", "DS-KEY")
    assert svc.api_key("deepseek") == "DS-KEY"


def test_target_lang_roundtrip(tmp_path):
    svc = make_service(tmp_path)
    svc.set_target_lang("en")
    assert svc.target_lang() == "en"


def test_output_dir_roundtrip(tmp_path):
    svc = make_service(tmp_path)
    svc.set_output_dir("/tmp/out")
    assert svc.output_dir() == "/tmp/out"


def test_engine_spec_matches_registry(tmp_path):
    svc = make_service(tmp_path)
    assert svc.engine_spec() is ENGINE_SPECS["siliconflow"]


# ── 票 05：術語表挑選＋自動提取開關 ──────────────────────────


def test_selected_glossaries_default_none_means_all(tmp_path):
    """未存過選擇 → None（呼叫端用「全選」）；存過（含空）→ 原樣回傳。"""
    svc = make_service(tmp_path)
    assert svc.selected_glossaries() is None
    svc.set_selected_glossaries(["dl", "img"])
    assert svc.selected_glossaries() == ["dl", "img"]
    svc.set_selected_glossaries([])
    assert svc.selected_glossaries() == []  # 明確取消全選要可區分


def test_selected_glossary_names_resolves_fallback(tmp_path):
    """「未存過 → 全選」慣例收進 service（UI 兩個呼叫點不再各自寫）。"""
    svc = make_service(tmp_path)
    assert svc.selected_glossary_names(["dl", "img"]) == ["dl", "img"]
    svc.set_selected_glossaries(["dl"])
    assert svc.selected_glossary_names(["dl", "img"]) == ["dl"]
    svc.set_selected_glossaries([])
    assert svc.selected_glossary_names(["dl", "img"]) == []  # 明確取消就真的是空


def test_auto_extract_toggle_roundtrip(tmp_path):
    svc = make_service(tmp_path)
    assert svc.auto_extract() is False  # 預設關
    svc.set_auto_extract(True)
    assert svc.auto_extract() is True
    svc.set_auto_extract(False)
    assert svc.auto_extract() is False


def test_term_api_key_defaults_blank_and_roundtrip(tmp_path):
    """#84：術語提取 key 獨立化——預設空（build_command 沿用主 key）、可獨立設定。"""
    svc = make_service(tmp_path)
    assert svc.term_api_key("siliconflow") == ""
    svc.set_term_api_key("siliconflow", "sf-term-key-123")
    assert svc.term_api_key("siliconflow") == "sf-term-key-123"
    # 獨立 key 與主 key 各自存放（不同 repo key）
    svc.set_api_key("siliconflow", "sf-main-key-456")
    assert svc.term_api_key("siliconflow") == "sf-term-key-123"
    assert svc.api_key("siliconflow") == "sf-main-key-456"


# ── 票 11：深色模式偏好 ───────────────────────────────────


def test_dark_mode_defaults_to_dark(tmp_path):
    svc = make_service(tmp_path)
    assert svc.dark_mode() is True  # 論文翻譯工具夜間使用為主


def test_dark_mode_roundtrip_and_survives_restart(tmp_path):
    svc = make_service(tmp_path)
    svc.set_dark_mode(False)
    assert svc.dark_mode() is False

    restarted = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))  # 重啟
    assert restarted.dark_mode() is False


# ── 票 25：翻譯快取開關 ────────────────────────────────────


def test_cache_enabled_defaults_true(tmp_path):
    """票 25：快取開關預設開（優化不預設關閉）。"""
    svc = make_service(tmp_path)
    assert svc.cache_enabled() is True


def test_cache_enabled_toggle_roundtrip(tmp_path):
    svc = make_service(tmp_path)
    svc.set_cache_enabled(False)
    assert svc.cache_enabled() is False

    restarted = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))  # 重啟
    assert restarted.cache_enabled() is False
