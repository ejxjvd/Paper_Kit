"""SettingsService（application）：設定 ↔ repo 的 typed 存取＋引擎解析。

驗證：預設引擎/語言、set 後解析出對應引擎、缺 key 給友善錯誤、
換引擎＝下一次翻譯走新引擎（FakeEngine 證明 UI 零改動由 01 測試守住）。
"""

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS
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


def test_resolve_engine_missing_key_gives_friendly_error(tmp_path):
    svc = make_service(tmp_path)
    with pytest.raises(EngineError, match="API key"):
        svc.resolve_engine()


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
