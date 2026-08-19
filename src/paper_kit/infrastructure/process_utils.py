"""系統程序共用（票 15 收攏）：WSL interop 路徑轉換＋逾時程序執行。

Windows 程式（soffice.exe / xelatex.exe）在 WSL 下收不到 /mnt/c/... 路徑
→ 命令組裝時以 wslpath -w 轉成 C:\\ 形式（wslpath 不存在時回原樣）。
兩引擎（PPT／LaTeX）同形——libreoffice_runner 原本私有，票 15 收攏共用。
"""

import shutil
import subprocess


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
    # encoding 明確指定（2026-08-19，同 cli_adapter_base 的 cp950 崩潰）：text=True
    # 不帶 encoding 會回退系統地區編碼，繁中 Windows 即 cp950。xelatex 的 log 帶
    # 非 ASCII（檔名、套件訊息）時就會 UnicodeDecodeError——這裡是 subprocess.run，
    # 例外會直接往上炸掉整個編譯流程。errors="replace" 讓壞位元組退化成 U+FFFD。
    try:
        done = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=cwd,
        )
    except subprocess.TimeoutExpired:
        return 124, f"{label} 逾時（超過 {timeout} 秒無回應）"
    return done.returncode, done.stdout + done.stderr
