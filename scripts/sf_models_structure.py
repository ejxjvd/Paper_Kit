#!/usr/bin/env python3
"""看 SiliconFlow /models 回傳結構（前 3 個模型欄位，不打印 key）。"""
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

print("total:", data.get("data") and len(data["data"]))
for m in (data.get("data") or [])[:3]:
    print(json.dumps(m, ensure_ascii=False, indent=1)[:500])
