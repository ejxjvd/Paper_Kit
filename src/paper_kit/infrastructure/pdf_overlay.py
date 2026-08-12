"""票 12：隱形文字層內嵌——OCR 文字放回掃描頁（pymupdf）。

設計：文字層只要「存在且順序正確」——pdf2zh 的版面分析接手排版，
不需精確 bbox 對位（ocrmypdf 同款做法的簡化版）。
原頁圖像（掃描內容）原樣保留，透明文字疊在上方。
"""

from pathlib import Path

import pymupdf  # 票 12：1.28+ 官方名稱（fitz API 已 deprecated）


def overlay_text_layer(pdf_path: str | Path, pages: dict[int, str], out_path: str | Path) -> Path:
    """把每頁 OCR 文字以透明文字內嵌進原頁；產出寫到 out_path。"""
    src = Path(pdf_path)
    out = Path(out_path)
    doc = pymupdf.open(str(src))
    for page_no, text in pages.items():
        page = doc[page_no - 1]  # dict 鍵＝1-based 頁號
        rect = page.rect
        # 透明文字（alpha=0）：pdf2zh 能提取、人眼看不見、不遮掃描圖
        # fontname="china-t"：pymupdf 內建 CJK 子集字體——Helvetica（base-14）無
        # CJK glyph，中文會變 '?'（spec review 實測抓出）
        page.insert_textbox(
            pymupdf.Rect(rect.x0, rect.y0, rect.x1, rect.y1),
            text,
            fontsize=1,
            fontname="china-t",
            color=(0, 0, 0, 0),
            overlay=True,
        )
    doc.save(str(out), garbage=3, deflate=True)
    doc.close()
    return out
