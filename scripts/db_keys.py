#!/usr/bin/env python3
"""列出 settings DB 的表格與含 api/key 的欄位名稱（不打印值）。"""
import sqlite3
from pathlib import Path

db = Path.home() / ".paper_kit" / "paper_kit.db"
conn = sqlite3.connect(db)
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print("tables:", tables)
for t in tables:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})")]
    print(f"{t} cols: {cols}")
for t in tables:
    if "settings" in t.lower():
        keys = [r[0] for r in conn.execute(f"SELECT key FROM {t}")]
        print(f"{t} keys: {keys}")
conn.close()
