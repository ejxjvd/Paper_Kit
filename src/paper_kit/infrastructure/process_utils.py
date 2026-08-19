"""系統程序共用（票 15 收攏）：WSL interop 路徑轉換＋逾時程序執行。

Windows 程式（soffice.exe / xelatex.exe）在 WSL 下收不到 /mnt/c/... 路徑
→ 命令組裝時以 wslpath -w 轉成 C:\\ 形式（wslpath 不存在時回原樣）。
兩引擎（PPT／LaTeX）同形——libreoffice_runner 原本私有，票 15 收攏共用。
"""

import shutil
import subprocess

from paper_kit.infrastructure.subprocess_exec import collect, spawn


def windowsify(path: str) -> str:
    """WSL 內把 Linux 路徑轉成 Windows 形式（wslpath -w）；失敗回原樣。"""
    wslpath = shutil.which("wslpath")
    if wslpath is None:
        return path
    try:
        out = subprocess.run(
            [wslpath, "-w", path], capture_output=True, text=True, timeout=10
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return path


def run_command(
    cmd: list[str], timeout: int = 180, label: str = "程序", cwd: str | None = None
) -> tuple[int, str]:
    """跑子程序（逾時回 rc 124＋說明）；回傳 (rc, stdout+stderr)。

    cwd：工作目錄（TeX 慣例 = 源碼目錄——多檔論文的 sty/Figures 在
    cwd 的第一順位搜尋；WSL interop 執行 .exe 時自動轉換路徑）。
    """
    # 走共用執行核心（架構深化候選 2，2026-08-19）：解碼契約與樹殺只有一份實作。
    # 先前這裡是獨立的 subprocess.run，於是同一個 cp950 解碼 bug 同時住在兩處
    # （使用者實測崩潰時兩邊都要修）。現在編碼由 subprocess_exec.spawn 釘死，
    # 逾時也改為樹殺——舊版 subprocess.run 逾時只殺直接子程序，soffice／xelatex
    # 的孫程序會留下來。
    try:
        rc, output = collect(spawn(cmd, cwd=cwd), timeout_seconds=timeout)
    except subprocess.TimeoutExpired:
        return 124, f"{label} 逾時（超過 {timeout} 秒無回應）"
    return rc, output
