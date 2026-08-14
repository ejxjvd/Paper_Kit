"""uv 官方二進制資產查表（win32/darwin/linux——工具層資產命名知識）。

uv 自動安裝（infrastructure/uv_bootstrap.py）的官方 release 資產名——跨
平台查表（非單平台行為，故不進 macos/ 或 windows/）。平台分支收斂於此。
"""

import platform
import sys

_PLATFORM_ASSETS = {
    "win32": "uv-x86_64-pc-windows-msvc.zip",
    "darwin-arm64": "uv-aarch64-apple-darwin.tar.gz",
    "darwin-x86_64": "uv-x86_64-apple-darwin.tar.gz",
    "linux": "uv-x86_64-unknown-linux-gnu.tar.gz",
}


def uv_executable_name() -> str:
    """平台執行檔名（Windows 帶 .exe）。"""
    return "uv.exe" if sys.platform == "win32" else "uv"


def platform_asset_name() -> str | None:
    """平台 → 官方資產檔名（純函式，測試直接斷言）。未知平台回 None。"""
    if sys.platform == "win32":
        return _PLATFORM_ASSETS["win32"]
    if sys.platform == "darwin":
        arch = (
            "arm64"
            if platform.machine().lower() in ("arm64", "aarch64")
            else "x86_64"
        )
        return _PLATFORM_ASSETS[f"darwin-{arch}"]
    if sys.platform.startswith("linux"):
        return _PLATFORM_ASSETS["linux"]
    return None
