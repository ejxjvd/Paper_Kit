"""macOS 版專屬：Finder 開啟資料夾。

open <path>（Finder）；Linux 開發兜底共用 POSIX 通則（xdg-open）——不是
Windows 版行為，不進 windows/。Windows 版（explorer.exe＋WSL 路徑正規化）
在 platform/windows/explorer.py。
"""

import subprocess
import sys
from pathlib import Path


def open_folder(path: Path) -> str:
    """Finder（macOS）／xdg-open（Linux 兜底）開啟資料夾＋先建目錄。

    回傳顯示 target（＝原始路徑字串，本平台無正規化語意）。
    """
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    path.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([opener, str(path)])
    return str(path)
