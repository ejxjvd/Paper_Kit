"""TeXCompiler（票 15）：xelatex 編譯 LaTeX 源碼 → PDF。

xeCJK 中文支援需要 xelatex（pdflatex 對 CJK 支援差）。xelatex.exe 是
Windows 程式（本機 MiKTeX per-user 安裝）——WSL 下路徑轉 Windows 形式
（同 LibreOfficeConverter 模式）。runner 可注入（測試接縫）。

本機安裝路徑（winget 裝 basic-miktex，per-user）：
AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe（不在 Program Files）。
"""

import shutil
from pathlib import Path

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.process_utils import run_command, windowsify

# 候選路徑：PATH 優先，再試常見安裝位置（per-user MiKTeX = 本機實況）
_XELATEX_CANDIDATES = (
    "/mnt/c/Users/qaref/AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe",  # WSL 掛載 per-user（桌機實況）
    r"C:\Users\qaref\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe",
    r"C:\Program Files\MiKTeX\miktex\bin\x64\xelatex.exe",
    "/usr/bin/xelatex",
    "/opt/texlive/bin/x86_64-linux/xelatex",
)

_MIKTEX_GUIDANCE = (
    "未偵測到 xelatex——LaTeX 翻譯需要它（Windows 安裝："
    "winget install MiKTeX.MiKTeX；編譯中途缺套件時 MiKTeX 會自動安裝）"
)


def find_xelatex() -> str | None:
    """找 xelatex 可執行檔（PATH＋常見安裝位置）；找不到回 None。"""
    found = shutil.which("xelatex")
    if found:
        return found
    for candidate in _XELATEX_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def build_xelatex_command(xelatex: str, tex_path: str, out_dir: str) -> list[str]:
    """組裝 xelatex headless 編譯命令（純函式，測試直接斷言旗標）。

    nonstopmode 必帶：headless 編譯不能被錯誤中斷等輸入；-halt-on-error
    第一個錯誤即停（省時間）；-output-directory 產物落 work 目錄。
    MiKTeX（.exe）加 --enable-installer：缺套件自動安裝——不彈
    「Package Installation」GUI 等確認（smoke 實測：彈窗阻塞到逾時）。
    TeX Live 不認這旗標，只在 Windows MiKTeX 加。
    """
    tex = tex_path
    out = out_dir
    if xelatex.lower().endswith(".exe"):
        tex = windowsify(tex_path)
        out = windowsify(out_dir)
    cmd = [
        xelatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-output-directory={out}",
        tex,
    ]
    if xelatex.lower().endswith(".exe"):
        cmd.insert(1, "--enable-installer")
    return cmd


class TeXCompiler:
    """實作 TeXCompilePort：xelatex 編譯 .tex → 產物 PDF 路徑。"""

    def __init__(self, xelatex: str | None = None, runner=None):
        self._xelatex = xelatex if xelatex is not None else (find_xelatex() or "")
        self._runner = runner or (
            lambda cmd, cwd=None: run_command(cmd, 180, "xelatex", cwd=cwd)
        )

    def compile(
        self, tex_path: str | Path, out_dir: str | Path, include_dirs: list = ()
    ) -> Path:
        if not self._xelatex:
            raise EngineError(_MIKTEX_GUIDANCE)
        src = Path(tex_path)
        if not src.exists():
            raise EngineError(f"找不到 LaTeX 源碼：{src.name}")
        work = Path(out_dir)
        work.mkdir(parents=True, exist_ok=True)
        cmd = build_xelatex_command(self._xelatex, str(src), str(work))
        # 多檔論文（sty/Figures 在源碼目錄）：cwd = 源碼目錄——TeX 對 .sty/
        # includegraphics 的第一順位搜尋就是 cwd（TEXINPUTS 環境變數會因
        # WSL→Windows interop 白名單遺失，不能用）。run_command 是 Linux
        # 程序 → cwd 傳 Linux 路徑原樣；interop 啟動 xelatex.exe 時自動轉換。
        cwd = str(include_dirs[0]) if include_dirs else None
        rc, output = self._runner(cmd, cwd)
        if rc != 0:
            raise EngineError(f"LaTeX 編譯失敗：{output.strip()[-200:] or '(無輸出)'}")
        pdf = work / f"{src.stem}.pdf"
        if not pdf.exists():
            raise EngineError("xelatex 編譯完成但找不到 PDF 產出")
        return pdf
