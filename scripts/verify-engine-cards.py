#!/usr/bin/env python3
"""引擎卡視覺驗證（Playwright headless）——量測**真實渲染**，而非斷言 CSS 字串。

為什麼需要這支（#214）：`test_theme.py` 掃原始碼、`test_index_page.py` 檢查元素樹，
兩者都能在「class 寫了但瀏覽器算出來不是那樣」時維持綠燈。D4 的引擎卡等高／
不截斷是**版面行為**，只有量測實際幾何才算驗證過。

檢查項：
  (a) 每個引擎列的 row 都帶 items-stretch（渲染後 DOM 上驗證）
  (b) 同列卡片高度一致（flex stretch 生效）
  (c) 沒有 .pk-engine-desc 被裁切（scrollHeight > clientHeight 即截斷）

用法：
    # 1) 先起 app（另一個終端）
    .venv/bin/python -m paper_kit.presentation.app
    # 2) 跑驗證
    .venv/bin/python scripts/verify-engine-cards.py
    .venv/bin/python scripts/verify-engine-cards.py --url http://localhost:8080

依賴：playwright（本專案未列入執行期依賴，需自備）
    uv pip install playwright && playwright install chromium

⚠️ 這是**手動**驗證工具，不在 pytest 套件內（Playwright 未納入 CI）。
若日後要納入，需先在 CI 安裝瀏覽器二進位。

Linux 無頭環境若缺共用函式庫（libnspr4／libnss3／libasound2），可下載 deb 解開後
以 LD_LIBRARY_PATH 注入，不需 root：
    apt-get download libnspr4 libnss3 libasound2t64
    for d in *.deb; do dpkg-deb -x "$d" /tmp/deps; done
    LD_LIBRARY_PATH=/tmp/deps/usr/lib/x86_64-linux-gnu python scripts/verify-engine-cards.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

VIEWPORTS = [(1400, 1200, "wide"), (900, 1400, "mid"), (420, 1400, "narrow")]


def find_chromium() -> str | None:
    """找 Playwright 已安裝的 chromium；找不到回 None（交給 Playwright 自己解析）。"""
    root = os.path.expanduser("~/.cache/ms-playwright")
    if not os.path.isdir(root):
        return None
    for name in sorted(os.listdir(root), reverse=True):
        if not name.startswith("chromium-"):
            continue
        for sub in ("chrome-linux64/chrome", "chrome-linux/chrome"):
            cand = os.path.join(root, name, sub)
            if os.path.isfile(cand):
                return cand
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="引擎卡視覺驗證（真實渲染量測）")
    ap.add_argument("--url", default="http://localhost:8080", help="app 位址")
    ap.add_argument("--wait", type=int, default=2500, help="載入後等待毫秒")
    ap.add_argument("--screenshot-dir", default="", help="若給，於各寬度截圖至此目錄")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: 需要 playwright —— uv pip install playwright && playwright install chromium")
        return 2

    # 讓瀏覽器找得到共用函式庫（無頭 Linux 常缺；有設就不覆寫）
    env = dict(os.environ)
    deps = "/tmp/deps/usr/lib/x86_64-linux-gnu"
    if os.path.isdir(deps):
        env["LD_LIBRARY_PATH"] = deps + os.pathsep + env.get("LD_LIBRARY_PATH", "")

    chrome = find_chromium()
    failures: list[str] = []
    launch_kw = {"headless": True, "env": env}
    if chrome:
        launch_kw["executable_path"] = chrome

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kw)
        for w, h, tag in VIEWPORTS:
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(args.url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(args.wait)
            if args.screenshot_dir:
                os.makedirs(args.screenshot_dir, exist_ok=True)
                page.screenshot(path=os.path.join(args.screenshot_dir, f"engine-cards-{tag}.png"),
                                full_page=True)

            print(f"\n===== viewport {w}x{h} ({tag}) =====")

            # (a)(b) 依最近的 .row 祖先把卡片分組
            rows = page.evaluate("""() => {
                const cards = [...document.querySelectorAll('.pk-engine-card')];
                const allRows = [...document.querySelectorAll('.row')];
                const groups = new Map();
                for (const c of cards) {
                    let p = c.parentElement;
                    while (p && !p.classList.contains('row')) p = p.parentElement;
                    const key = p ? allRows.indexOf(p) : -1;
                    if (!groups.has(key)) groups.set(key, {el: p, cards: []});
                    groups.get(key).cards.push(c);
                }
                return [...groups.entries()].map(([k, v]) => ({
                    rowIndex: k,
                    classes: v.el ? v.el.className : null,
                    heights: v.cards.map(c => {
                        const r = c.getBoundingClientRect();
                        return {label: (c.innerText || '').split('\\n')[0].slice(0, 24),
                                h: Math.round(r.height * 10) / 10};
                    }),
                }));
            }""")

            for g in rows:
                cls = g["classes"] or ""
                if "items-stretch" not in cls:
                    failures.append(f"[{tag}] row#{g['rowIndex']} 缺 items-stretch: {cls}")
                print(f"  row#{g['rowIndex']:<3} items-stretch={'items-stretch' in cls}"
                      f"  卡片數={len(g['heights'])}")
                hs = [c["h"] for c in g["heights"]]
                if len(hs) > 1 and (max(hs) - min(hs)) > 0.5:
                    failures.append(
                        f"[{tag}] row#{g['rowIndex']} 同列不等高 {min(hs)}~{max(hs)}: "
                        + ", ".join(f"{c['label']}={c['h']}" for c in g["heights"]))
                    print(f"    ✗ 不等高 {min(hs)}~{max(hs)}")
                elif len(hs) > 1:
                    print(f"    ✓ 等高 {hs[0]}px ×{len(hs)}")

            # (c) desc 截斷
            clipped = page.evaluate("""() => {
                const out = [];
                for (const e of document.querySelectorAll('.pk-engine-desc')) {
                    if (e.scrollHeight > e.clientHeight + 1) {
                        out.push({text: (e.innerText || '').slice(0, 50),
                                  sh: e.scrollHeight, ch: e.clientHeight});
                    }
                }
                return out;
            }""")
            if clipped:
                for c in clipped:
                    failures.append(f"[{tag}] desc 被截斷 {c['sh']}>{c['ch']}: {c['text']}")
                print(f"  ✗ 被裁切 desc：{len(clipped)}")
            else:
                print("  ✓ 無 desc 被裁切")

            if tag == "wide":
                print(f"  引擎卡總數：{page.locator('.pk-engine-card').count()}")
            page.close()
        browser.close()

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: FAIL（{len(failures)} 項）")
        for f in failures:
            print("  -", f)
        return 1
    print("RESULT: PASS（items-stretch 齊備／同列等高／無文字截斷，"
          f"{len(VIEWPORTS)} 種視窗寬度）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
