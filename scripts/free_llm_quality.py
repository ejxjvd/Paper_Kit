#!/usr/bin/env python3
"""2026-08-13 票 45/51：免費模型 vs 付費引擎品質真測（同一段技術文本對譯）。

- 免費：SiliconFlow GLM-4-9B-0414（免費模型，不扣額度）
- 付費：DeepSeek deepseek-chat（付費）
key 從 ~/.paper_kit/paper_kit.db 讀（不打印值）。譯文寫入 docs/research/ 供報告引用。
"""
import json
import sqlite3
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

DB = Path.home() / ".paper_kit" / "paper_kit.db"
SRC_PDF = Path("/mnt/c/Users/qaref/Code/Paper_Kit/tests/fixtures/paper_p34.pdf")
OUT_DIR = Path("/mnt/c/Users/qaref/Code/Paper_Kit/docs/research/free_llm_samples")
ctx = ssl.create_default_context()


def get_key(engine_id: str) -> str:
    conn = sqlite3.connect(DB)
    try:
        row = conn.execute("SELECT api_key FROM api_keys WHERE engine_id=?", (engine_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row[0]:
        sys.exit(f"DB 無 api_key_{engine_id}（{DB}）")
    return row[0]


def extract_first_page_text() -> str:
    """pypdf 提取第一頁文字（走專案 venv）。"""
    import sys as _s

    _s.path.insert(0, "/mnt/c/Users/qaref/Code/Paper_Kit/src")
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("venv 無 pypdf")
    reader = PdfReader(str(SRC_PDF))
    text = reader.pages[0].extract_text() or ""
    return " ".join(text.split())[:1200]


def chat(base_url: str, api_key: str, model: str, text: str) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "你是專業技術翻譯。把使用者給的英文論文文字翻譯成繁體中文，保持術語準確、語意完整，不要省略。"},
            {"role": "user", "content": text},
        ],
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(f"{base_url}/chat/completions", method="POST", data=payload)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code}] {e.read(300).decode('utf-8', 'replace')[:150]}"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    src = extract_first_page_text()
    (OUT_DIR / "source-text.txt").write_text(src, encoding="utf-8")

    sf_key = get_key("siliconflow")
    # GLM-4-9B-0414 已停用（Model disabled 403）→ 換現行免費模型，逐個試
    free_models = ["Qwen/Qwen3-8B", "Qwen/Qwen2.5-7B-Instruct"]
    free_out = None
    for mid in free_models:
        print(f"== SiliconFlow {mid}（免費模型）==")
        free_out = chat("https://api.siliconflow.com/v1", sf_key, mid, src)
        print(free_out[:600])
        if not free_out.startswith("[HTTP"):
            break
    if free_out is None:
        sys.exit("全部免費模型都失敗")
    print("\n== DeepSeek deepseek-chat（付費）==")
    ds_key = get_key("deepseek")
    ds_out = chat("https://api.deepseek.com/v1", ds_key, "deepseek-chat", src)
    print(ds_out[:600])

    (OUT_DIR / "GLM-4-9B-0414.txt").write_text(free_out, encoding="utf-8")
    (OUT_DIR / "deepseek-chat.txt").write_text(ds_out, encoding="utf-8")
    print(f"\n樣本已存 {OUT_DIR}")


if __name__ == "__main__":
    main()
