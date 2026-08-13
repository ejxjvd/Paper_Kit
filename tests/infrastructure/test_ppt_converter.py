"""票 14：LibreOfficeConverter——.pptx 每頁轉一張 PNG（soffice 渲染＋pymupdf）。

soffice 是系統依賴（本機已裝 LibreOffice）；單測以 FakeRunner 為接縫
（不碰真實 soffice），真實渲染冒煙在 test_ppt_vision_smoke.py（skip 若無 soffice）。
"""

import shutil
import subprocess
from pathlib import Path

import pymupdf
import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.ppt_converter import (
    LibreOfficeConverter,
    build_soffice_command,
    find_soffice,
)


def make_pdf_with_pages(path: Path, pages: int = 2) -> Path:
    """inline 造「每頁一張圖」的 PDF（FakeRunner 產物，pymupdf 可開）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page(width=640, height=360)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 64, 36))
        page.insert_image(pymupdf.Rect(0, 0, 64, 36), pixmap=pix)
    doc.save(str(path))
    doc.close()
    return path


class FakeRunner:
    """記錄命令；rc 可設。轉換成功的產物 = 預先造好的 PDF（converter 之後開它）。"""

    def __init__(self, pdf_path: Path | None, rc: int = 0, output: str = ""):
        self._pdf = pdf_path
        self._rc = rc
        self._output = output
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str]) -> tuple[int, str]:
        self.calls.append(list(cmd))
        return self._rc, self._output


def test_build_soffice_command_flags():
    cmd = build_soffice_command(
        "/usr/bin/soffice", "/tmp/in/deck.pptx", "/tmp/out"
    )
    assert cmd == [
        "/usr/bin/soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        "/tmp/out",
        "/tmp/in/deck.pptx",
    ]


def test_converter_missing_soffice_gives_friendly_error(tmp_path):
    conv = LibreOfficeConverter(soffice="")  # 找不到 soffice
    with pytest.raises(EngineError, match="LibreOffice"):
        conv.convert_to_images(tmp_path / "deck.pptx", tmp_path / "out")


def test_converter_missing_input_gives_friendly_error(tmp_path):
    conv = LibreOfficeConverter(soffice="/usr/bin/soffice")
    with pytest.raises(EngineError, match="找不到簡報"):
        conv.convert_to_images(tmp_path / "no-such.pptx", tmp_path / "out")


def test_converter_renders_one_png_per_page(tmp_path):
    (tmp_path / "deck.pptx").write_bytes(b"fake pptx")
    # soffice 產物 = outdir/輸入 stem.pdf（converter 依此尋找）
    pdf = make_pdf_with_pages(tmp_path / "out" / "deck.pdf", pages=2)
    conv = LibreOfficeConverter(soffice="/usr/bin/soffice", runner=FakeRunner(pdf))
    images = conv.convert_to_images(tmp_path / "deck.pptx", tmp_path / "out")
    assert [p.name for p in images] == ["slide-01.png", "slide-02.png"]
    assert all(p.exists() for p in images)


def test_converter_soffice_failure_gives_error(tmp_path):
    (tmp_path / "deck.pptx").write_bytes(b"fake pptx")
    conv = LibreOfficeConverter(
        soffice="/usr/bin/soffice",
        runner=FakeRunner(None, rc=78, output="soffice exploded"),
    )
    with pytest.raises(EngineError, match="soffice exploded"):
        conv.convert_to_images(tmp_path / "deck.pptx", tmp_path / "out")


@pytest.mark.skipif(shutil.which("wslpath") is None,
                     reason="需要 WSL interop（wslpath）")
def test_build_soffice_command_windows_exe_windowsifies_paths():
    """WSL 內跑 soffice.exe：/mnt/c/... 必須轉成 C:\\ 形式（interop 事實）。"""
    cmd = build_soffice_command(
        "C:\\Program Files\\LibreOffice\\program\\soffice.exe",
        "/mnt/c/tmp/in/deck.pptx",
        "/mnt/c/tmp/out",
    )
    assert cmd[0].endswith("soffice.exe")
    assert cmd[5].startswith("C:")  # outdir 已轉 Windows 形式
    assert cmd[6].startswith("C:")  # 輸入檔已轉 Windows 形式
    assert "\\" in cmd[6]  # wslpath 回傳 Windows 反斜線形式
