"""加密 PDF 讀取回歸測試（v0.1.2 修復）。

背景（2026-08-14 使用者實測）：Telegram 收到的 OS_Chapter01.pdf 是
AES-256（R=6）加密但無密碼——上傳時「無法讀取頁數：不是有效 PDF？」，
真因是 pypdf 讀 AES 需要 cryptography>=3.1，而 v0.1.1 依賴漏包（訊息誤導）。
本測試守住：cryptography 依賴不可移除、無密碼加密 PDF 頁數可讀、翻譯鏈
（pymupdf）不需密碼即可開。
"""

from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "encrypted-aes256.pdf"


def test_encrypted_pdf_page_count_readable_with_cryptography():
    """pypdf 讀無密碼 AES-256 加密 PDF 要能取頁數（依賴 cryptography）。"""
    pytest.importorskip("cryptography")
    from pypdf import PdfReader

    reader = PdfReader(str(FIXTURE))
    assert reader.is_encrypted is True
    assert len(reader.pages) == 3


def test_encrypted_pdf_translation_chain_readable_by_pymupdf():
    """翻譯鏈（pdf2zh 走 pymupdf）：無密碼加密 PDF 不需密碼即可開（needs_pass=0）。"""
    import pymupdf

    doc = pymupdf.open(str(FIXTURE))
    assert not doc.needs_pass  # pymupdf 回傳 int 0（非 False）
    assert doc.page_count == 3
