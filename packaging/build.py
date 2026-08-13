"""跨平台打包 script（v0.1.1）：PyInstaller → 冒煙 → zip。

用法：
    uv run python packaging/build.py          # 版本取自 pyproject
    PK_VERSION=0.1.1 uv run python packaging/build.py   # 覆寫版本名

產物：dist/paper-kit-<PK_VERSION>-<platform>.zip
    zip 內含產物目錄（exe + _internal/）+ README-使用手冊.md

冒煙（防止打包出死 exe）：啟動產物 → poll http://127.0.0.1:8080 回 200 →
驗證 8080 監聽 PID == exe PID → terminate 關閉。任何一步失敗即非零退出。
（v0.1.0 實測教訓：貼圖視覺 hook 佔用 8080 時 exe 秒閃退——冒煙專抓這類。）
"""

import os
import platform
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.request
from pathlib import Path

# Windows runner 的 stdout/stderr 預設 cp1252——中文輸出（進度行、錯誤訊息）
# 直接 UnicodeEncodeError 秒炸（CI win-x64 實測 2026-08-14）；強制 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    if _stream is not None and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
SPEC_PATH = REPO_ROOT / "packaging" / "paper-kit.spec"
MANUAL_PATH = REPO_ROOT / "packaging" / "README-使用手冊.md"
PORT = 8080
READY_TIMEOUT = 90  # 首次啟動（onedir 解壓依賴）可能慢


def project_version() -> str:
    """pyproject version（PK_VERSION 環境變數可覆寫）。"""
    env = os.environ.get("PK_VERSION")
    if env:
        return env
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def platform_tag() -> str:
    """win32 → win-x64；darwin arm64 → macos-arm64；linux → linux-x86_64。"""
    machine = platform.machine().lower()
    if sys.platform == "win32":
        return "win-x64"
    if sys.platform == "darwin":
        return "macos-arm64" if machine in ("arm64", "aarch64") else "macos-x64"
    return "linux-x86_64"


def exe_name(version: str) -> str:
    return f"paper-kit-{version}{'.exe' if sys.platform == 'win32' else ''}"


def build(version: str) -> Path:
    """PyInstaller 打包（spec 內 name 讀 PK_VERSION env）。"""
    env = dict(os.environ, PK_VERSION=version)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", str(SPEC_PATH)],
        check=True,
        env=env,
        cwd=REPO_ROOT,
    )
    return DIST_DIR / f"paper-kit-{version}"


# ── 冒煙 ──────────────────────────────────────────────


def _http_ready(proc, timeout: int) -> bool:
    """poll http://127.0.0.1:8080 直到 200（或進程退出/逾時）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"exe 提前退出（returncode={proc.returncode}）")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # 尚未就緒（連接拒絕/逾時都算）
            pass
        time.sleep(1)
    return False


def _listener_pid() -> str | None:
    """8080 監聽 PID（平台分支：Windows netstat／mac/Linux lsof）。"""
    if sys.platform == "win32":
        out = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True
        ).stdout
        for line in out.splitlines():
            if ":8080" in line and "LISTENING" in line:
                return line.split()[-1]
        return None
    out = subprocess.run(
        ["lsof", "-nP", "-iTCP:8080", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
    ).stdout
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            return parts[1]
    return None


def smoke(app_dir: Path, version: str) -> None:
    """啟動產物 → HTTP 200 → 監聽 PID == exe PID → 關閉。失敗即拋。"""
    exe = app_dir / exe_name(version)
    if not exe.is_file():
        raise RuntimeError(f"產物不存在：{exe}")
    proc = subprocess.Popen([str(exe)], cwd=app_dir)
    try:
        if not _http_ready(proc, READY_TIMEOUT):
            raise RuntimeError("8080 未在時限內回 HTTP 200")
        listener = _listener_pid()
        if listener is None:
            raise RuntimeError("找不到 8080 監聽者（port 衝突或啟動失敗）")
        if listener != str(proc.pid):
            raise RuntimeError(f"監聽者 PID {listener} ≠ exe PID {proc.pid}（port 被他人佔用？）")
        print(f"冒煙 OK：HTTP 200、監聽者 PID {listener} == exe PID {proc.pid}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def package(app_dir: Path, version: str) -> Path:
    """產物目錄 + 手冊 → zip（dist/paper-kit-<ver>-<platform>.zip）。"""
    shutil.copy2(MANUAL_PATH, app_dir / "README-使用手冊.md")
    zip_path = DIST_DIR / f"paper-kit-{version}-{platform_tag()}"
    shutil.make_archive(
        str(zip_path), "zip", root_dir=app_dir.parent, base_dir=app_dir.name
    )
    return Path(str(zip_path) + ".zip")


def main() -> None:
    version = project_version()
    print(f"── Paper_Kit {version}（{platform_tag()}）──")
    app_dir = build(version)
    smoke(app_dir, version)
    zip_path = package(app_dir, version)
    print(f"完成：{zip_path}")


if __name__ == "__main__":
    main()
