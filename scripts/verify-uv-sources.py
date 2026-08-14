#!/usr/bin/env python3
"""uv 自動安裝多源真網驗證（可重用，v0.1.9.3 起）。

情境：
  A-全鏈     — GitHub 官方 release 優先（未知使用者預設路徑）
  B-PyPI     — 只留 PyPI 官方源（GitHub 域被擋的網路）
  C-清華鏡像  — 只留 PEP 503 鏡像源（國外域全被擋的網路）

每情境實際呼叫 download_uv() 真網下載，產物 uv --version 可執行才 PASS。
驗證產物落 app_uv_path()（開發 = ~/.paper_kit/bin），跑完自動清理。

用法（repo 根）：
  .venv/bin/python scripts/verify-uv-sources.py            # 三情境全跑
  .venv/bin/python scripts/verify-uv-sources.py --only pypi
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import paper_kit.infrastructure.uv_bootstrap as ub  # noqa: E402


def run(label: str, only: str | None) -> None:
    print(f"== 情境 {label} ==")
    orig = ub._download_sources
    if only:
        ub._download_sources = lambda timeout: [
            (l, f) for l, f in orig(timeout) if l == only
        ]
    try:
        p = ub.download_uv()
    finally:
        ub._download_sources = orig
    assert p is not None, f"{label} 下載失敗（download_uv 回 None）"
    assert os.path.isfile(p), f"{label} 產物不存在"
    ver = os.popen(f"{p} --version").read().strip()
    print(f"{label} -> {p}\n  uv --version: {ver}")
    assert ver.startswith("uv "), f"{label} 產物不可執行"


def main() -> int:
    ap = argparse.ArgumentParser(description="uv 多源自動安裝真網驗證")
    ap.add_argument("--only", choices=["github", "pypi", "mirror"], default=None)
    args = ap.parse_args()
    print("落點:", ub.app_uv_path())
    if args.only:
        run(f"only-{args.only}", args.only)
    else:
        run("A-全鏈GitHub", None)
        run("B-PyPI", "pypi")
        run("C-清華鏡像", "mirror")
    print("ALL OK")
    # 清理真網驗證產物（~/.paper_kit/bin）——腳本目的是驗證，不留產物
    bin_dir = ub.app_uv_path().parent
    if bin_dir.exists():
        shutil.rmtree(bin_dir)
        print(f"已清理驗證產物：{bin_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
