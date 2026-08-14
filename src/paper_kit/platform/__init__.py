"""平台分離（2026-08-14 使用者要求：macOS／Windows 各自乾淨專案，避免汙染）。

工程事實（2026-08-14 統計）：單一源碼 7,618 行中平台分支僅 18 處——99.8%
是平台無關共用核心（application／domain／infrastructure 其餘部分）。使用者
拍板「repo 內平台資料夾分離」：平台知識全部收斂於本套件——

- platform/macos/     macOS 版專屬（Finder 開啟、POSIX 程序樹殺）
- platform/windows/   Windows 版專屬（explorer 開啟＋WSL 路徑正規化、
                      taskkill 樹殺）
- platform/uv_assets.py  uv 官方二進制資產查表（win32/darwin/linux）

分離守則（tests/platform/test_platform.py 強制）：macos/ 與 windows/ 互不
import；共用核心零平台分支（一律經本層 dispatch）。Linux 僅開發兜底
（POSIX 通則與 macOS 共用，不另設資料夾）。
"""

import subprocess
import sys
from pathlib import Path

from paper_kit.platform import macos, windows

# dispatch 的屬性查找（windows.processes/explorer、macos.processes/finder）
# 依賴子模組被 import 過（「import package」不會掛載子模組屬性）——測試
# 環境曾被測試檔頭部 import 副作用遮蔽（v0.1.9.1 全綠假象），frozen exe
# 乾淨環境每翻譯必炸（2026-08-15 使用者真機抓到 AttributeError: no
# attribute 'processes'，任務建立→開始→同秒失敗）；PyInstaller 分析器
# 亦以本層 import 為準收包。此處為 dispatch 父層職責，不違反
# macos/ 與 windows/ 互不 import 的分離守則。
import paper_kit.platform.macos.finder  # noqa: F401 掛載屬性
import paper_kit.platform.macos.processes  # noqa: F401 掛載屬性
import paper_kit.platform.windows.explorer  # noqa: F401 掛載屬性
import paper_kit.platform.windows.processes  # noqa: F401 掛載屬性

PLATFORM_LABELS = {"win32": "Windows", "darwin": "macOS", "linux": "Linux"}


def platform_label() -> str:
    """App 內版本標註（「Paper_Kit 論文翻譯器（Windows 版）」）。"""
    return PLATFORM_LABELS.get(sys.platform, sys.platform)


def folder_opener(platform_name: str | None = None) -> str | None:
    """平台 → 檔案管理員命令（純函式）。win32 回 None（走 explorer 正規化路徑）。"""
    plat = platform_name or sys.platform
    if plat == "darwin":
        return "open"
    if plat.startswith("linux"):
        return "xdg-open"
    return None


def open_folder(path: Path) -> str:
    """開啟系統檔案管理員到資料夾（平台分派單點）。回傳顯示 target。

    win32 → windows/explorer.open_folder（explorer.exe＋WSL 路徑正規化）；
    其餘 → macOS Finder（Linux 開發兜底 xdg-open）——POSIX 通則共用。
    """
    if sys.platform == "win32":
        return windows.explorer.open_folder(path)
    return macos.finder.open_folder(path)


def kill_tree(proc) -> None:
    """程序樹殺（平台分派單點）。已退場（poll 非 None）不動作。

    win32 → taskkill /T /F 遞迴殺整棵樹；macOS／Linux → killpg 殺進程組。
    """
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        windows.processes.kill_tree(proc)
    else:
        macos.processes.kill_tree(proc)


def spawn_kwargs() -> dict:
    """Popen spawn 參數（平台分派單點）。POSIX 需要進程組長（樹殺前提）。"""
    if sys.platform == "win32":
        return windows.processes.spawn_kwargs()
    return macos.processes.spawn_kwargs()
