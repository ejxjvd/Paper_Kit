"""票 12 standards review：共用 fixture helper（make_blank_pdf 三份重複 → 收進 conftest）。"""

from pathlib import Path

import pytest


@pytest.fixture()
def make_blank_pdf():
    """造「無文字層」PDF（整頁空白——掃描件偵測的真實條件）。"""

    def _make(path: Path, pages: int = 2) -> Path:
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=595, height=842)
        with open(path, "wb") as f:
            writer.write(f)
        return path

    return _make
