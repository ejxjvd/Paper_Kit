"""SqliteSettingsRepository：設定與 API keys 持久化（SQLite，std 庫）。

key 存明文（SQLite 本機庫）；**明文 key 一律不得進 log**（redaction 在 log 層，票 09）。
"""

import sqlite3
from pathlib import Path

DEFAULT_ENGINE_ID = "siliconflow"
DEFAULT_TARGET_LANG = "zh-TW"


class SqliteSettingsRepository:
    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS api_keys (engine_id TEXT PRIMARY KEY, api_key TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS pricing ("
            "engine_id TEXT PRIMARY KEY, input_per_1k TEXT, output_per_1k TEXT, per_page_tokens INTEGER)"
        )
        self._conn.commit()

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_api_key(self, engine_id: str) -> str:
        row = self._conn.execute(
            "SELECT api_key FROM api_keys WHERE engine_id=?", (engine_id,)
        ).fetchone()
        return row[0] if row else ""

    def set_api_key(self, engine_id: str, api_key: str) -> None:
        self._conn.execute(
            "INSERT INTO api_keys (engine_id, api_key) VALUES (?, ?) "
            "ON CONFLICT(engine_id) DO UPDATE SET api_key=excluded.api_key",
            (engine_id, api_key),
        )
        self._conn.commit()

    def get_pricing(self, engine_id: str) -> tuple[str, str, int] | None:
        """票 06：引擎單價；無紀錄回 None（用預設值）。"""
        row = self._conn.execute(
            "SELECT input_per_1k, output_per_1k, per_page_tokens FROM pricing WHERE engine_id=?",
            (engine_id,),
        ).fetchone()
        return row if row else None

    def set_pricing(
        self, engine_id: str, input_per_1k: str, output_per_1k: str, per_page_tokens: int
    ) -> None:
        """票 06：漲價只需改設定（2026-08-06 DeepSeek 漲價教訓）。"""
        self._conn.execute(
            "INSERT INTO pricing (engine_id, input_per_1k, output_per_1k, per_page_tokens) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(engine_id) DO UPDATE SET "
            "input_per_1k=excluded.input_per_1k, output_per_1k=excluded.output_per_1k, "
            "per_page_tokens=excluded.per_page_tokens",
            (engine_id, input_per_1k, output_per_1k, per_page_tokens),
        )
        self._conn.commit()
