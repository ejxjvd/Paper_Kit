"""LibreOfficeConverter（票 14）：把 .pptx 每頁轉成一張 PNG。

管線：soffice --headless --convert-to pdf（版面 100% 由 LibreOffice 渲染，
動畫/備註以外設計原樣保留）→ pymupdf 逐頁 render PNG（zoom 2x ≈ 1920px
幻燈片，gemma 眼睛實測品質區間）。soffice 是系統依賴（本機已裝）——
不存在時丟 EngineError（友善訊息）。

WSL interop 事實：soffice.exe 是 Windows 程式，收不到 /mnt/c/... 路徑 →
命令組裝時以 wslpath -w 轉成 C:\\ 形式（wslpath 不存在時回原樣）。
"""

import shutil
from pathlib import Path

import pymupdf

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.process_utils import run_command, windowsify

# 候選路徑：PATH 優先，再試常見安裝位置（含 WSL 掛載形式——本機 soffice.exe
# 裝在 Windows，WSL 側的檢查路徑是 /mnt/c/...，C:\\... 在 Linux 下永遠不存在）
_SOFFICE_CANDIDATES = (
    "/mnt/c/Program Files/LibreOffice/program/soffice.exe",  # WSL 掛載（桌機實況）
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/usr/bin/soffice",
    "/opt/libreoffice/program/soffice",
)


def find_soffice() -> str | None:
    """找 LibreOffice 可執行檔（PATH＋常見安裝位置）；找不到回 None。"""
    found = shutil.which("soffice")
    if found:
        return found
    for candidate in _SOFFICE_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def build_soffice_command(soffice: str, pptx_path: str, out_dir: str) -> list[str]:
    """組裝 soffice headless 轉 PDF 命令（純函式，測試直接斷言旗標）。

    soffice.exe（Windows 程式）在 WSL 下跑 → 路徑轉 Windows 形式。
    """
    if soffice.lower().endswith(".exe"):
        pptx_path = windowsify(pptx_path)
        out_dir = windowsify(out_dir)
    return [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, pptx_path]


class LibreOfficeConverter:
    """實作 PptToImagePort：soffice 渲染 → pymupdf 逐頁 PNG（依頁序命名）。"""

    def __init__(self, soffice: str | None = None, zoom: float = 2.0, runner=None):
        self._soffice = soffice if soffice is not None else (find_soffice() or "")
        self._zoom = zoom
        self._runner = runner or (lambda cmd: run_command(cmd, 180, "soffice"))

    def convert_to_images(self, pptx_path: str | Path, out_dir: str | Path) -> list[Path]:
        if not self._soffice:
            raise EngineError(
                "未偵測到 LibreOffice——PPT 拆圖需要它（Windows 安裝："
                "winget install TheDocumentFoundation.LibreOffice）"
            )
        src = Path(pptx_path)
        if not src.exists():
            raise EngineError(f"找不到簡報檔：{src.name}")
        work = Path(out_dir)
        work.mkdir(parents=True, exist_ok=True)
        cmd = build_soffice_command(self._soffice, str(src), str(work))
        rc, output = self._runner(cmd)
        if rc != 0:
            raise EngineError(f"LibreOffice 轉換失敗：{output.strip()[-200:] or '(無輸出)'}")
        pdf_path = work / f"{src.stem}.pdf"
        if not pdf_path.exists():
            raise EngineError("LibreOffice 轉換完成但找不到 PDF 產出")
        doc = pymupdf.open(str(pdf_path))
        images: list[Path] = []
        try:
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=pymupdf.Matrix(self._zoom, self._zoom))
                img = work / f"slide-{i:02d}.png"
                pix.save(str(img))
                images.append(img)
        finally:
            doc.close()
        return images
