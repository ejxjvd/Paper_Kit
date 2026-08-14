#!/usr/bin/env python3
"""真翻譯驗證（可重用，v0.1.9.3 起）。

驗證紀律：任何引擎／uv／翻譯管線修復都必須走 app 真實執行路徑
（build_engine→adapter.translate→_default_runner→resolve_uv）實際
翻譯產出 mono/dual 檔案才算完成。本腳本把該流程參數化，取代每次
臨時手寫 /tmp 腳本（2026-08-15 使用者要求：流程加快＋腳本存專案）。

用法（repo 根）：
  .venv/bin/python scripts/verify-translate.py                      # 預設 google／paper_p34 第 1 頁
  .venv/bin/python scripts/verify-translate.py --engine bing --pages 2
  .venv/bin/python scripts/verify-translate.py --prepend-bin        # PATH 前置 ~/.paper_kit/bin
                                                                    #（驗證 resolve_uv 命中自動安裝產物）

輸出：elapsed＋mono/dual 路徑與大小；產出檔存在才 exit 0。
產出落點：pdf2zh 引擎在 runner cwd（= source_path.parent）產出、不搬移——
腳本斷言 fixture 同目錄的 {stem}.{lang}.mono/dual.pdf，跑完自動清理。
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description="真翻譯驗證（產出 mono/dual 才算過）")
    ap.add_argument("--engine", default="google", help="ENGINE_SPECS 鍵名（預設 google＝免費引擎）")
    ap.add_argument("--fixture", default=str(REPO_ROOT / "tests/fixtures/paper_p34.pdf"))
    ap.add_argument("--pages", default="1")
    ap.add_argument("--target-lang", default="zh-TW")
    ap.add_argument(
        "--prepend-bin", action="store_true",
        help="PATH 前置 ~/.paper_kit/bin（驗證 resolve_uv 命中自動安裝產物）",
    )
    args = ap.parse_args()

    if args.prepend_bin:
        prod_bin = Path.home() / ".paper_kit" / "bin"
        if prod_bin.is_dir():
            os.environ["PATH"] = str(prod_bin) + ":" + os.environ.get("PATH", "")
            print("PATH 前置產物 bin：", prod_bin)
        else:
            print("警告：產物 bin 不存在，resolve_uv 走其他偵測層")

    from paper_kit.domain.translation_job import TranslationJob
    from paper_kit.infrastructure import uv_bootstrap as ub
    from paper_kit.infrastructure.engine_registry import ENGINE_SPECS, build_engine

    uv = ub.resolve_uv()
    print("resolve_uv ->", uv)
    assert uv and Path(uv).is_file(), "resolve_uv 必須命中 uv"

    fixture = Path(args.fixture)
    assert fixture.is_file(), f"fixture 不存在：{fixture}"
    assert args.engine in ENGINE_SPECS, f"未知引擎 {args.engine}，可用：{list(ENGINE_SPECS)}"

    job = TranslationJob(
        job_id="verify-translate",
        source_path=str(fixture),
        target_lang=args.target_lang,
        pages=args.pages,
        glossary_files=[],
    )
    adapter = build_engine(ENGINE_SPECS[args.engine])
    t0 = time.monotonic()
    result = adapter.translate(job)
    elapsed = time.monotonic() - t0
    print("elapsed:", round(elapsed, 1), "s")
    print("result:", result)

    # 產出落 runner cwd（= fixture 同目錄，pdf2zh 不搬移——實測 2026-08-15）
    pattern = f"{fixture.stem}.{args.target_lang}.*.pdf"
    outputs = sorted(fixture.parent.glob(pattern))
    print("產出檔:", [(p.name, p.stat().st_size) for p in outputs])
    assert outputs, f"產出檔不存在（{fixture.parent}/{pattern}）"
    names = {p.name for p in outputs}
    assert any("mono" in n for n in names) and any("dual" in n for n in names), \
        "必須同時產出 mono＋dual"
    for p in outputs:
        p.unlink()  # 跑完清產出，fixture 目錄保持乾淨
    print(f"VERIFY OK（{round(elapsed, 1)}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
