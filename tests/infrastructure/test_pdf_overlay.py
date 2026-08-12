"""票 12：隱形文字層內嵌——OCR 文字放回掃描頁，pypdf 就能提取、pdf2zh 就能翻。

設計：文字層只要「存在且順序正確」即可——pdf2zh 的版面分析會自己接手排版，
不需要精確 bbox 對位（ocrmypdf 同款做法的簡化版）。
"""

from pathlib import Path

from paper_kit.infrastructure.pdf_overlay import overlay_text_layer


def extract_all_text(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def test_overlay_adds_searchable_text_layer(tmp_path: Path, make_blank_pdf):
    """OCR 版 PDF：pypdf 能提取出每頁 OCR 文字（文字層存在）。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=2)
    out = overlay_text_layer(scan, {1: "hello page one", 2: "world page two"}, tmp_path / "ocr-scan.pdf")
    text = extract_all_text(out)
    assert "hello page one" in text
    assert "world page two" in text


def test_overlay_extracts_cjk_text(tmp_path: Path, make_blank_pdf):
    """CJK 掃描件（中文論文場景）：隱形文字層用內建 CJK 字體——pypdf 可提取。

    spec review 抓出：Helvetica（base-14）無 CJK glyph，中文會變 ?（實測）。
    """
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=1)
    out = overlay_text_layer(scan, {1: "中文測試頁 機械学習"}, tmp_path / "ocr-scan.pdf")
    text = extract_all_text(out)
    assert "中文測試頁" in text
    assert "機械学習" in text


def test_overlay_keeps_missing_pages_untouched(tmp_path: Path, make_blank_pdf):
    """只內嵌給定的頁（缺頁 → 該頁無文字層，不崩）。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=3)
    out = overlay_text_layer(scan, {1: "only first"}, tmp_path / "ocr-scan.pdf")
    text = extract_all_text(out)
    assert "only first" in text
    assert "only first" in text.split("\n")[0]  # 第一頁才有


def test_overlay_output_is_valid_pdf(tmp_path: Path, make_blank_pdf):
    """產出可被 pypdf 開、頁數不變（掃描圖像原樣保留）。"""
    scan = make_blank_pdf(tmp_path / "scan.pdf", pages=2)
    out = overlay_text_layer(scan, {1: "x"}, tmp_path / "ocr-scan.pdf")
    from pypdf import PdfReader

    reader = PdfReader(str(out))
    assert len(reader.pages) == 2
