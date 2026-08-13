#!/usr/bin/env python3
"""列 SiliconFlow 免費模型（api_keys 表讀 key，不打印值）。"""
import json
import ssl
import sqlite3
import urllib.request
from pathlib import Path

ctx = ssl.create_default_context()
conn = sqlite3.connect(Path.home() / ".paper_kit" / "paper_kit.db")
key = conn.execute("SELECT api_key FROM api_keys WHERE engine_id='siliconflow'").fetchone()[0]
conn.close()

req = urllib.request.Request("https://api.siliconflow.com/v1/models", method="GET")
req.add_header("Authorization", f"Bearer {key}")
with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
    data = json.loads(resp.read().decode("utf-8"))

free = []
for m in data.get("data", []):
    p = m.get("pricing", {})
    is_free = m.get("free") or (p.get("input") == "0" and p.get("output") == "0")
    if is_free:
        free.append(m["id"])
print(f"免費模型（{len(free)}）：")
for mid in sorted(free):
    print(" ", mid)
