"""uv 工具自動安裝（v0.1.1）：引擎中介（pdf2zh_next/babeldoc）不打包是 AGPL
散佈紅線的既定決策——改由應用程式自動偵測＋安裝 uv，開箱即用、無需使用者
手動裝任何東西（2026-08-14 使用者要求：「偵測並自動執行安裝，而不是讓使用者
自行安裝」）。

偵測鏈：系統 PATH → ~/.local/bin（uv 官方 install script 落點）→
~/.paper_kit/bin（app 專屬，自動安裝落點）。自動安裝直接下載 uv 官方
二進制 release（平台分支）解壓到 app 專屬目錄——不改使用者環境（不寫
PATH）、不需 shell（Windows 無 sh）。全鏈失敗才回 None，呼叫方給可操作錯誤。
"""

import logging
import platform
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_APP_DIR_NAME = ".paper_kit"  # 與 presentation/app.py:76 共用語意（infra 不 import presentation）

_UV_DOWNLOAD_BASE = "https://github.com/astral-sh/uv/releases/latest/download"
# 平台 → 官方 release 資產名（latest 浮動可接受——工具層，測試 mock 不觸網）
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


def download_url() -> str | None:
    """平台 → 完整下載 URL（純函式）。"""
    asset = platform_asset_name()
    return f"{_UV_DOWNLOAD_BASE}/{asset}" if asset else None


def app_uv_path() -> Path:
    """app 專屬 uv 落點（~/.paper_kit/bin/uv[.exe]）。

    動態組 Path.home()——測試會 monkeypatch Path.home 隔離家目錄。
    """
    return Path.home() / _APP_DIR_NAME / "bin" / uv_executable_name()


def installed_uv() -> Path | None:
    """偵測鏈：PATH → ~/.local/bin（官方 install script 落點）→ app 專屬。"""
    on_path = shutil.which("uv")
    if on_path:
        return Path(on_path)
    home_bin = Path.home() / ".local" / "bin" / uv_executable_name()
    if home_bin.is_file():
        return home_bin
    local = app_uv_path()
    return local if local.is_file() else None


def _extract_uv(archive: Path, dest_dir: Path) -> Path:
    """解壓並把 uv 執行檔搬到穩定落點（dest_dir/uv[.exe]）回傳。

    官方 zip/tar 內含平台前綴目錄（uv-x86_64-pc-windows-msvc/uv.exe）——
    不搬的話每次 installed_uv() 檢查穩定路徑都會撲空、重複下載。
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest_dir)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(dest_dir)
    found = next(dest_dir.rglob(uv_executable_name()), None)
    if found is None:
        raise ValueError(f"解壓後找不到 uv 執行檔（{dest_dir}）")
    stable = dest_dir / uv_executable_name()
    if found != stable:
        shutil.move(str(found), stable)
    return stable


def download_uv(timeout: int = 60) -> Path | None:
    """下載官方二進制到 app 專屬目錄。回傳可執行路徑；失敗回 None（log 原因）。"""
    url = download_url()
    if url is None:
        logger.error("uv 自動安裝：不支援的平台 %s", sys.platform)
        return None
    bin_dir = app_uv_path().parent
    bin_dir.mkdir(parents=True, exist_ok=True)
    archive = bin_dir / url.rsplit("/", 1)[-1]
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            archive.write_bytes(resp.read())
        return _extract_uv(archive, bin_dir)
    except Exception as exc:  # noqa: BLE001——下載失敗原因多元（離線/憑證/被擋）
        logger.error("uv 自動安裝失敗（%s）：%s", url, exc)
        return None


def ensure_uv(timeout: int = 60) -> Path | None:
    """偵測→缺則自動安裝。回傳 uv 路徑或 None（呼叫方給可操作錯誤）。"""
    existing = installed_uv()
    if existing is not None:
        return existing
    return download_uv(timeout=timeout)


def resolve_uv(timeout: int = 60) -> str | None:
    """cli_adapter_base runner 使用的總入口（字串路徑，直接進 subprocess cmd）。"""
    uv = ensure_uv(timeout=timeout)
    return str(uv) if uv is not None else None
