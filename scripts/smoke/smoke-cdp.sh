#!/bin/bash
cd /mnt/c/Users/qaref/Code/Paper_Kit || exit 1
CHROME="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
PROFILE="/mnt/c/Users/qaref/AppData/Local/Temp/chrome-pk-smoke"
PORT=9222

# start headless chrome with CDP port if not already up
if ! curl -s --max-time 2 http://127.0.0.1:$PORT/json/version > /dev/null 2>&1; then
  rm -rf "$PROFILE"
  "$CHROME" --headless=new --disable-gpu --no-sandbox --disable-extensions \
    --remote-debugging-port=$PORT --user-data-dir="$PROFILE" about:blank \
    > /tmp/chrome-pk-smoke.log 2>&1 &
  # wait for CDP
  for i in $(seq 1 30); do
    curl -s --max-time 2 http://127.0.0.1:$PORT/json/version > /dev/null 2>&1 && break
    sleep 1
  done
fi
curl -s --max-time 3 http://127.0.0.1:$PORT/json/version | head -c 120; echo

.venv/bin/python3 - <<'PY'
import os, sqlite3, time, glob
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
PDF = "/mnt/c/Users/qaref/Code/Paper_Kit/tests/fixtures/paper_p34.pdf"
DB = os.path.expanduser("~/.paper_kit/paper_kit.db")
STEM = PDF.rsplit(".", 1)[0]
results = []

def check(name, cond, extra=""):
    results.append((name, bool(cond), extra))
    print(("PASS " if cond else "FAIL ") + name + (f" | {extra}" if extra else ""))

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = ctx.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    # 1. main page
    page.goto(BASE, wait_until="networkidle", timeout=30000)
    check("主頁載入", page.locator("text=Paper_Kit").count() > 0)

    # 2. settings: auto_extract -> ON (reproduce user's failing scenario)
    page.goto(BASE + "/settings", wait_until="networkidle", timeout=30000)
    page.wait_for_selector(".q-toggle", timeout=10000)
    toggle = page.locator(".q-toggle", has_text="自動術語提取").first
    checked = toggle.locator("input").is_checked()
    print(f"auto_extract 測前狀態 = {checked}")
    if not checked:
        toggle.click()
        page.wait_for_timeout(800)
    check("設定頁開 auto_extract", toggle.locator("input").is_checked())

    # 3. main page, upload via real file input
    page.goto(BASE, wait_until="networkidle", timeout=30000)
    page.locator('input[type="file"]').first.set_input_files(PDF)
    page.wait_for_timeout(2000)

    # 4. job card in queue
    page.wait_for_selector(f"text={os.path.basename(PDF)}", timeout=10000)
    check("翻譯清單出現 job 卡", True)

    # 5. click 開始翻譯
    page.get_by_role("button", name="開始翻譯").first.click()
    print("已點「開始翻譯」")

    # 6. poll DB for COMPLETED
    deadline = time.time() + 300
    final = None
    while time.time() < deadline:
        con = sqlite3.connect(DB)
        row = con.execute(
            "SELECT status, error, output_dir, auto_extract, engine_id FROM jobs ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        con.close()
        if row:
            final = row
            if row[0] in ("COMPLETED", "FAILED"):
                break
        time.sleep(3)
    print("job 最終狀態 =", final)
    check("job COMPLETED", final and final[0] == "COMPLETED",
          f"status={final and final[0]} error={final and final[1]}")

    # 7. output PDFs exist and non-empty
    mono = glob.glob(STEM + ".zh.mono.pdf")
    dual = glob.glob(STEM + ".zh.dual.pdf")
    check("mono PDF 產出", bool(mono) and os.path.getsize(mono[0]) > 0,
          os.path.basename(mono[0]) if mono else "none")
    check("dual PDF 產出", bool(dual) and os.path.getsize(dual[0]) > 0,
          os.path.basename(dual[0]) if dual else "none")

    # 8. UI body clean of 450/401
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    check("UI 無「SiliconFlow API key is required」", "API key is required" not in body)
    check("UI 無 401", "Api key is invalid" not in body)
    check("無 pageerror", len(errors) == 0, "; ".join(errors[:3]))

    # 9. restore auto_extract
    page.goto(BASE + "/settings", wait_until="networkidle", timeout=30000)
    t2 = page.locator(".q-toggle", has_text="自動術語提取").first
    now = t2.locator("input").is_checked()
    if now != checked:
        t2.click()
        page.wait_for_timeout(600)
    check("auto_extract 還原", t2.locator("input").is_checked() == checked,
          f"原={checked}")

    ctx.close()

fails = [r for r in results if not r[1]]
print(f"\n===== 冒煙結果：{len(results) - len(fails)}/{len(results)} PASS =====")
if fails:
    print("FAILED:", [r[0] for r in fails])
    raise SystemExit(1)
PY
