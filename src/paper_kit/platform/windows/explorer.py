"""Windows 版專屬：explorer 開啟資料夾（WSL 路徑語意正規化，#20 實測）。

macOS 版（Finder：open <path>，無正規化語意）在 platform/macos/finder.py。
"""

import re
import subprocess
from pathlib import Path

# #20：路徑語意判別（Windows 盤符路徑 vs UNC——瀏覽資料夾的正規化基礎）
_WIN_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_WIN_UNC_RE = re.compile(r"^\\\\")


def win_to_wsl(raw: str) -> str:
    """純函式：Windows 絕對路徑 → WSL 路徑（C:\\Users\\qaref → /mnt/c/Users/qaref）。"""
    m = re.match(r"^([A-Za-z]):[\\/](.*)$", raw)
    if m:
        return f"/mnt/{m.group(1).lower()}/{m.group(2).replace(chr(92), '/')}"
    return raw


def explorer_target(raw: str) -> str:
    """純函式：任意路徑語意 → explorer.exe 可開的 Windows 路徑字串。

    Windows 絕對路徑（C:\\...）／UNC（\\\\...）→ 原樣（已是 Windows 語意）；
    /mnt/<drive>/... → 手轉 C:\\...（免 subprocess，最可靠——#20 實測
    explorer 對 C:\\ 與 \\\\wsl.localhost UNC 都能開窗）；
    其餘 Linux 路徑（/home/... 等）→ wslpath -w（\\\\wsl.localhost UNC）；
    wslpath 不可用／失敗 → 原樣回傳（呼叫端 try/except 接手 notify）。
    """
    if _WIN_DRIVE_RE.match(raw) or _WIN_UNC_RE.match(raw):
        return raw
    if raw.startswith("/mnt/"):
        parts = raw.split("/")
        return f"{parts[2].upper()}:\\" + "\\".join(parts[3:])
    try:
        out = subprocess.run(
            ["wslpath", "-w", raw], capture_output=True, text=True, timeout=5
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return raw


def open_folder(path: Path) -> str:
    """explorer.exe 開啟資料夾（WSL 語意正規化＋防呆）。回傳顯示 target。

    「瀏覽資料夾」輸入可為 Windows 路徑（C:\\...）或 WSL 路徑
    （/mnt/c/...、/home/...）——mkdir 與 explorer 目標各自正規化（Windows
    路徑在 /mnt 對應建、UNC 不需 mkdir）；任何失敗由呼叫端 try/except
    接手 notify（使用者實測「點按無回應」的靜默感從此消除）。
    """
    raw = str(path)
    if _WIN_DRIVE_RE.match(raw):
        Path(win_to_wsl(raw)).mkdir(parents=True, exist_ok=True)
    elif not _WIN_UNC_RE.match(raw):
        path.mkdir(parents=True, exist_ok=True)
    target = explorer_target(raw)
    subprocess.Popen(["explorer.exe", target])
    return target
