"""SettingsRepository（SQLite）：設定與 API keys 持久化。

驗證：get/set 往返、預設值、各引擎 key 隔離、重開連線後仍在（SQLite 持久）。
key 存明文（SQLite）但**不得進 log**（redaction 在票 09 log 層處理）。
"""

import sqlite3

import pytest

from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository


def test_set_get_roundtrip(tmp_path):
    repo = SqliteSettingsRepository(tmp_path / "pk.db")
    repo.set("target_lang", "en")
    assert repo.get("target_lang") == "en"


def test_missing_key_returns_default(tmp_path):
    repo = SqliteSettingsRepository(tmp_path / "pk.db")
    assert repo.get("nope", "fallback") == "fallback"


def test_api_keys_isolated_per_engine(tmp_path):
    repo = SqliteSettingsRepository(tmp_path / "pk.db")
    repo.set_api_key("deepseek", "DS-KEY")
    repo.set_api_key("siliconflow", "SF-KEY")
    assert repo.get_api_key("deepseek") == "DS-KEY"
    assert repo.get_api_key("siliconflow") == "SF-KEY"


def test_missing_api_key_returns_empty(tmp_path):
    repo = SqliteSettingsRepository(tmp_path / "pk.db")
    assert repo.get_api_key("deepseek") == ""


def test_persists_across_reopen(tmp_path):
    db = tmp_path / "pk.db"
    repo = SqliteSettingsRepository(db)
    repo.set("engine_id", "deepseek")
    repo.set_api_key("deepseek", "DS-KEY")
    repo2 = SqliteSettingsRepository(db)  # 模擬 app 重啟
    assert repo2.get("engine_id") == "deepseek"
    assert repo2.get_api_key("deepseek") == "DS-KEY"


def test_overwrite_updates_value(tmp_path):
    repo = SqliteSettingsRepository(tmp_path / "pk.db")
    repo.set("engine_id", "deepseek")
    repo.set("engine_id", "siliconflow")
    assert repo.get("engine_id") == "siliconflow"
