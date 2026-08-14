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


def platform_key() -> str | None:
    """平台分類 key（win32/darwin-arm64/darwin-x86_64/linux）——官方資產名
    （platform_asset_name）與 PyPI wheel 查表（uv_bootstrap）共用的分類單點。
    未知平台回 None。"""
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        arch = platform.machine().lower()
        return "darwin-arm64" if arch in ("arm64", "aarch64") else "darwin-x86_64"
    if sys.platform.startswith("linux"):
        return "linux"
    return None


def platform_asset_name() -> str | None:
    """平台 → 官方資產檔名（純函式，測試直接斷言）。未知平台回 None。"""
    return _PLATFORM_ASSETS.get(platform_key())  # noqa: dict.get(None) 回 None
