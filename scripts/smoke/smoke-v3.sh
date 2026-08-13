#!/bin/bash
cd /mnt/c/Users/qaref/Code/Paper_Kit || exit 1
.venv/bin/python3 - <<'PY'
import os, sqlite3, time, sys, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
PDF = "/mnt/c/Users/qaref/Code/Paper_Kit/tests/fixtures/paper_p34.pdf"
DB = os.path.expanduser("~/.paper_kit/paper_kit.db")
LIBS = "/tmp/deps/usr/lib/x86_64-linux-gnu:/tmp/deps/lib/x86_64-linux-gnu"
results = []

def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" | {extra}" if extra else ""))

def db_setting(key):
    con = sqlite3.connect(DB)
    r = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return r[0] if r else None

def db_latest_job():
    con = sqlite3.connect(DB)
    r = con.execute("SELECT job_id, status, error, result, auto_extract, engine_id FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
    con.close()
    return r

def job_terminal():
    con = sqlite3.connect(DB)
    r = con.execute("SELECT status FROM jobs ORDER BY created_at DESC LIMIT 1").fetchone()
    con.close()
    return r and r[0] in ("COMPLETED", "FAILED")

ae_before = db_setting("auto_extract")
print(f"DB auto_extract 測前 = {ae_before}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, env={"LD_LIBRARY_PATH": LIBS})
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # 1. main page
    page.goto(BASE, wait_until="networkidle", timeout=30000)
    check("主頁載入", page.locator("text=Paper_Kit").count() > 0)

    # 2. settings page: ensure ON (click only if currently OFF)
    page.goto(BASE + "/settings", wait_until="networkidle", timeout=30000)
    page.wait_for_selector(".q-toggle", timeout=10000)
    toggle = page.locator(".q-toggle", has_text="自動術語提取").first
    ui_checked = toggle.locator("input").is_checked()
    print(f"UI switch 顯示 = {ui_checked} | DB = {db_setting('auto_extract')}")
    check("UI switch 與 DB 一致", str(int(ui_checked)) == db_setting("auto_extract"),
          f"UI={ui_checked} DB={db_setting('auto_extract')}")
    if db_setting("auto_extract") != "1":
        toggle.click()
        page.wait_for_timeout(800)
    check("auto_extract=1（重現 Bug 1 場景）", db_setting("auto_extract") == "1")

    # 3. main page upload via real file input
    page.goto(BASE, wait_until="networkidle", timeout=30000)
    page.locator('input[type="file"]').first.set_input_files(PDF)
    page.wait_for_timeout(2000)
    page.wait_for_selector(f"text={os.path.basename(PDF)}", timeout=10000)
    check("翻譯清單出現 job 卡", True)

    # 4. click 開始翻譯
    page.get_by_role("button", name="開始翻譯").first.click()
    print("已點「開始翻譯」")

    # 5. poll DB until terminal
    deadline = time.time() + 300
    while time.time() < deadline and not job_terminal():
        time.sleep(3)
    jid, status, err, result, ae, engine = db_latest_job()
    print(f"job {jid[:12]} status={status} auto_extract={ae} engine={engine}")
    check("job COMPLETED", status == "COMPLETED", f"error={err}")
    check("job auto_extract=1（Bug 1 場景）", ae == "1")

    # 6. outputs from result JSON
    res = json.loads(result) if result else {}
    mono, dual = res.get("mono_path", ""), res.get("dual_path", "")
    check("mono PDF 產出", bool(mono) and os.path.getsize(mono) > 0, os.path.basename(mono) if mono else "none")
    check("dual PDF 產出", bool(dual) and os.path.getsize(dual) > 0, os.path.basename(dual) if dual else "none")
    gl_dir = os.path.dirname(mono) if mono else ""
    gloss = [f for f in os.listdir(gl_dir) if f.endswith(".glossary.csv")] if gl_dir and os.path.isdir(gl_dir) else []
    check("術語提取 glossary.csv 產出", bool(gloss), gloss[0] if gloss else "none")
    check("Token 用量有值", res.get("input_tokens", 0) + res.get("output_tokens", 0) > 0,
          f"in={res.get('input_tokens')} out={res.get('output_tokens')}")

    # 7. UI clean
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    check("UI 無「SiliconFlow API key is required」", "API key is required" not in body)
    check("UI 無 401", "Api key is invalid" not in body)
    check("無 pageerror", len(errors) == 0, "; ".join(errors[:3]))

    # 8. restore auto_extract
    if db_setting("auto_extract") != ae_before:
        page.goto(BASE + "/settings", wait_until="networkidle", timeout=30000)
        page.wait_for_selector(".q-toggle", timeout=10000)
        page.locator(".q-toggle", has_text="自動術語提取").first.click()
        page.wait_for_timeout(800)
    check("auto_extract 還原", db_setting("auto_extract") == ae_before,
          f"原={ae_before} 現={db_setting('auto_extract')}")

    browser.close()

fails = [r for r in results if not r[1]]
print(f"\n===== 冒煙結果：{len(results) - len(fails)}/{len(results)} PASS =====")
if fails:
    print("FAILED:", [r[0] for r in fails])
    sys.exit(1)
PY
