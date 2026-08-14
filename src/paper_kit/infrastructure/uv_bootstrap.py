"""uv 工具自動安裝（v0.1.1）：引擎中介（pdf2zh_next/babeldoc）不打包是 AGPL
散佈紅線的既定決策——改由應用程式自動偵測＋安裝 uv，開箱即用、無需使用者
手動裝任何東西（2026-08-14 使用者要求：「偵測並自動執行安裝，而不是讓使用者
自行安裝」）。

偵測鏈：系統 PATH → ~/.local/bin（uv 官方 install script 落點）→
app 資料目錄/bin（v0.1.2 起 = 程式旁 data/bin，portable；見
infrastructure/app_paths.py）。自動安裝直接下載 uv 官方二進制 release
（平台分支）解壓到 app 專屬目錄——不改使用者環境（不寫 PATH）、不需
shell（Windows 無 sh）。全鏈失敗才回 None，呼叫方給可操作錯誤。

平台分離（2026-08-14）：平台分支（資產查表、執行檔名）收斂於
paper_kit.platform.uv_assets——本模組僅剩下載/安裝邏輯（平台無關）。
"""

import json
import logging
import re
import shutil
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from paper_kit.infrastructure.app_paths import app_data_dir  # v0.1.2：資料目錄單一權威（portable）
from paper_kit.platform.uv_assets import (
    platform_asset_name,
    platform_key,
    uv_executable_name,
)

logger = logging.getLogger(__name__)

_APP_DIR_NAME = ".paper_kit"  # 開發/測試落點名（v0.1.2 起資料目錄單一權威在 app_paths.app_data_dir）

_UV_DOWNLOAD_BASE = "https://github.com/astral-sh/uv/releases/latest/download"
# v0.1.9.3 多源（2026-08-15 真機實測）：單一 GitHub 源在部分網路（域被擋/
# 慢/超時）直接全滅——GitHub 官方 release → PyPI 官方（uv 同發 PyPI wheel）
# → 清華/阿里雲鏡像（PEP 503 簡單索引）依序嘗試，任何一源可用即成功。
_PYPI_JSON_URL = "https://pypi.org/pypi/uv/json"
_PYPI_MIRRORS = [
    "https://pypi.tuna.tsinghua.edu.cn/simple/uv/",
    "https://mirrors.aliyun.com/pypi/simple/uv/",
]
_DOWNLOAD_TIMEOUT = 120  # 慢網下 60s 可能中斷大檔下載（v0.1.9.3 調高）

_last_failures: list[str] = []  # 最近一次 download_uv 全敗的各源原因（呼叫方組訊息）
_RETRY_DELAY = 2.0  # 源失敗後重試間隔（秒）——測試 monkeypatch 為 0


def download_url() -> str | None:
    """平台 → 完整下載 URL（純函式）。"""
    asset = platform_asset_name()
    return f"{_UV_DOWNLOAD_BASE}/{asset}" if asset else None


def app_uv_path() -> Path:
    """app 專屬 uv 落點（v0.1.2 起 = 程式旁 data/bin/uv[.exe]，portable）。

    走 app_paths.app_data_dir() 單一權威（打包後 exe 旁、開發 ~/.paper_kit）；
    測試 monkeypatch Path.home / sys.executable 隔離。
    """
    return app_data_dir() / "bin" / uv_executable_name()


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

    官方 zip/tar 內含平台前綴目錄（uv-x86_64-pc-windows-msvc/uv.exe）、
    PyPI wheel 內含 uv/ 套件目錄＋dist-info——一律解壓到暫存子目錄，只把
    執行檔（檔案，非同名目錄）搬到穩定落點，其餘捨棄（v0.1.9.3 實測：wheel
    的 uv/ 目錄會與既有執行檔衝突、rglob 會先命中同名目錄）。
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    tmp = dest_dir / f".extract-{archive.name}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    try:
        if archive.suffix in (".zip", ".whl"):  # .whl 本質是 zip（PyPI wheel 源）
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(tmp)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(tmp)
        found = next(
            (p for p in tmp.rglob(uv_executable_name()) if p.is_file()), None
        )
        if found is None:
            raise ValueError(f"解壓後找不到 uv 執行檔（{tmp}）")
        stable = dest_dir / uv_executable_name()
        if stable.is_dir():
            shutil.rmtree(stable)  # 舊壞狀態（目錄型殘留）
        elif stable.exists():
            stable.unlink()  # 重複安裝（不同源）先清舊檔，避免目錄/檔案衝突
        shutil.move(str(found), stable)
        if sys.platform != "win32":
            # 真網實測（2026-08-15）：PyPI wheel 的執行檔不帶執行權限位
            # （zip 不保留）——解壓後補上，否則 Permission denied
            stable.chmod(stable.stat().st_mode | 0o111)
        return stable
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _wheel_matches(filename: str) -> bool:
    """平台 → PyPI wheel 檔名匹配（真網實測 2026-08-15 教訓：寬關鍵字曾誤選
    aarch64 wheel 致 Exec format error——必須平台＋架構雙重精準）。"""
    key = platform_key()
    if key == "win32":
        return "win_amd64" in filename
    if key == "darwin-arm64":
        return "macosx" in filename and "arm64" in filename
    if key == "darwin-x86_64":
        return "macosx" in filename and "x86_64" in filename
    if key == "linux":
        return "manylinux" in filename and "x86_64" in filename
    return False


def _pypi_wheel_url(timeout: int) -> str:
    """PyPI JSON API → 最新版平台 wheel 的下載 URL（uv 官方同發 PyPI wheel）。

    直接下載 URL 回傳，download_uv 再統一 urlopen——與 GitHub 源同一契約。
    """
    with urllib.request.urlopen(_PYPI_JSON_URL, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    version = data["info"]["version"]
    for asset in data.get("releases", {}).get(version, []):
        filename = asset.get("filename", "")
        if filename.endswith(".whl") and _wheel_matches(filename):
            return asset["url"]
    raise RuntimeError(f"PyPI 最新版 {version} 無 {sys.platform} wheel")


def _mirror_wheel_url(mirror_url: str, timeout: int) -> str:
    """PEP 503 簡單索引 → 最後一個（最新）平台 wheel href（去 #sha256 碎片）。

    鏡像（清華/阿里雲）HTML 依上傳順序舊→新排列——取最後即最新版。
    """
    with urllib.request.urlopen(mirror_url, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", "replace")
    candidates = [
        href
        for href in re.findall(r'href="([^"]+)"', html)
        if ".whl" in href and _wheel_matches(href)  # href 帶 #sha256= 碎片
    ]
    if not candidates:
        raise RuntimeError(f"鏡像無 {sys.platform} wheel")
    # 真網實測（2026-08-15）：tuna/aliyun 的 href 是相對路徑（../../packages/…）
    # ——必須 urljoin 解析成完整 URL 才能下載
    return urllib.parse.urljoin(mirror_url, candidates[-1].split("#")[0])


def _download_sources(timeout: int) -> list[tuple[str, Callable[[], str]]]:
    """依序嘗試的下載源（label, 產生下載 URL 的函式）——任何一源可用即成功。

    v0.1.9.3（2026-08-15 真機實測）：單一 GitHub 源在部分網路直接全滅。
    未知使用者預設最壞環境（無 uv、任一域被擋）——備援源足量：
    GitHub 官方 release → PyPI 官方 → 清華鏡像 → 阿里雲鏡像。
    """
    if platform_asset_name() is None:
        return []
    sources: list[tuple[str, Callable[[], str]]] = [
        ("github", lambda: download_url()),
        ("pypi", lambda: _pypi_wheel_url(timeout=timeout)),
    ]
    for mirror in _PYPI_MIRRORS:
        sources.append(("mirror", lambda m=mirror: _mirror_wheel_url(m, timeout=timeout)))
    return sources


def _download_with_progress(resp, dest: Path, label: str) -> None:
    """分塊寫入＋進度/速度 log（2026-08-15 使用者要求：exe 的 CMD 視窗要
    看到「是否正在安裝、進度到哪裡、實時安裝速度、完成」——console handler
    即時印出，每 ~2 秒或每 8MB 一行）。"""
    total = getattr(resp, "length", None) or None
    done = 0
    last_log = time.monotonic()
    last_done = 0
    with open(dest, "wb") as f:
        while True:
            block = resp.read(512 * 1024)
            if not block:
                break
            f.write(block)
            done += len(block)
            now = time.monotonic()
            if now - last_log >= 2.0 or done - last_done >= 8 * 1024 * 1024:
                pct = f"{done / total * 100:.0f}%" if total else f"{done / 1024 / 1024:.1f}MB"
                speed = (done - last_done) / max(now - last_log, 1e-9) / 1024 / 1024
                logger.info(
                    "uv 自動安裝：%s 下載中 %s（%.1f MB / %s，速度 %.1f MB/s）",
                    label, pct, done / 1024 / 1024,
                    f"{total / 1024 / 1024:.1f}MB" if total else "?",
                    speed,
                )
                last_log, last_done = now, done
    logger.info("uv 自動安裝：%s 下載完成（%.1f MB）", label, done / 1024 / 1024)


def download_uv(timeout: int = _DOWNLOAD_TIMEOUT) -> Path | None:
    """下載官方二進制到 app 專屬目錄。多源依序嘗試（GitHub→PyPI→鏡像），
    每源重試 2 次（2026-08-15 使用者要求：失敗要自動重試——瞬時網路/牆
    問題可救回）。任一成功即回傳；全敗回 None（log 每源原因，且可經
    download_failures() 取回供呼叫方組可操作錯誤訊息）。"""
    sources = _download_sources(timeout=timeout)
    if not sources:
        logger.error("uv 自動安裝：不支援的平台 %s", sys.platform)
        return None
    bin_dir = app_uv_path().parent
    bin_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for label, url_fn in sources:
        for attempt in (1, 2):
            try:
                url = url_fn()
                # 進度 log 走 paper_kit logger——console handler 直接印在 exe
                # 的 CMD 視窗（2026-08-15 使用者要求：安裝紀錄要在 CMD 看到）。
                logger.info("uv 自動安裝：源 %s 嘗試 %d/2（%s）", label, attempt, url)
                archive = bin_dir / url.rsplit("/", 1)[-1].split("#")[0]
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    _download_with_progress(resp, archive, label)
                installed = _extract_uv(archive, bin_dir)
                archive.unlink(missing_ok=True)  # 下載檔用完即清（bin 保持乾淨）
                logger.info("uv 自動安裝成功：%s（源 %s）", installed, label)
                _last_failures.clear()
                return installed
            except Exception as exc:  # noqa: BLE001——下載失敗原因多元（離線/憑證/被擋/壞檔）
                failures.append(f"{label}（第 {attempt} 次）: {exc}")
                if attempt == 1:
                    logger.warning(
                        "uv 自動安裝源 %s 第 1 次失敗：%s——%.0f 秒後重試", label, exc, _RETRY_DELAY
                    )
                    time.sleep(_RETRY_DELAY)
                else:
                    logger.error("uv 自動安裝源 %s 重試仍失敗：%s", label, exc)
    logger.error("uv 自動安裝全源失敗（%d 次嘗試）：%s", len(failures), "；".join(failures))
    _last_failures[:] = failures
    return None


def download_failures() -> list[str]:
    """最近一次 download_uv 全敗的各源失敗原因（呼叫方組可操作錯誤訊息）。"""
    return list(_last_failures)


def ensure_uv(timeout: int = _DOWNLOAD_TIMEOUT) -> Path | None:
    """偵測→缺則自動安裝。回傳 uv 路徑或 None（呼叫方給可操作錯誤）。"""
    existing = installed_uv()
    if existing is not None:
        logger.info("uv 自動安裝：偵測到既有 uv（%s）", existing)
        return existing
    return download_uv(timeout=timeout)


def resolve_uv(timeout: int = _DOWNLOAD_TIMEOUT) -> str | None:
    """cli_adapter_base runner 使用的總入口（字串路徑，直接進 subprocess cmd）。"""
    uv = ensure_uv(timeout=timeout)
    return str(uv) if uv is not None else None
