"""LaTeX 密集 PDF 偵測（v0.1.9.5）。

背景（2026-08-15 實測診斷）：LaTeX 論文翻譯後中文行重疊——BabelDOC 引擎
把翻譯行距壓縮到 8.7-9.4pt，小於 Source Han Serif TW 字形 17.2pt → 行間
視覺重疊。公式參數與 mono 模式實測皆無效 → UI 標注方案：偵測 LaTeX 數學
密集 PDF（Computer Modern／AMS 字體系），翻譯完成後標記卡片提示行重疊風險。

判定規則：文件含 Computer Modern 系正文字體（CMR/CMMI）＋公式符號字體
（CMSY/CMEX/LASY/MSAM/MSBM——「密集」的關鍵），且 LaTeX 頁面覆蓋率過半。
PDF 子集嵌入字體名帶 6 字元前綴（XXXXXX+CMR10）——比對前先剝離。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("paper_kit.infrastructure.latex_detector")

# Computer Modern 系（LaTeX 預設）＋AMS 數學系＋Latin Modern（lmodern 套件，
# 現代 LaTeX 常見預設——字體名 LMRoman/LMMath 而非 CMR）字體前綴。
# CMR=羅馬正文、CMMI=數學斜體、CMSY/CMEX=數學符號/大符號、LASY=邏輯符號、
# MSAM/MSBM=AMS 符號、EUFM/EUSM=歐拉數學字體。
# 注意（2026-08-15 使用者質詢後補強）：字體名判定是啟發式——TeX Gyre 系正文
# 字體（TeXGyrePagella 等）同時被 LibreOffice 散佈，不列入正文標誌（誤報風險
# 大於漏報）；unicode-math 系（LatinModernMath/STIXTwoMath/XITSMath）列入
# 符號字體——它們只在「數學密集」判定生效，正文判定仍看 LM/CM 系。
_CM_PREFIXES = (
    "CMR", "CMMI", "CMSY", "CMEX", "CMBX", "CMSS", "CMSL", "CMSM",
    "LASY", "MSAM", "MSBM", "EUFM", "EUSM", "EUFB", "EUSB", "RSFS",
    "LMRoman", "LMMath", "LMSans", "LMMono", "LMSS", "LMTypewriter",
)
# 公式符號字體——存在任一即代表「數學密集」（正文字體 CMR 也常見於
# 非數學 LaTeX 文件，符號字體才表明有大量數學式）。
# CM/AMS 系＋unicode-math 系（Latin Modern Math／STIX Two Math／XITS Math／
# TeX Gyre Math——XeLaTeX/lualatex 預設路徑）。
_SYMBOL_PREFIXES = (
    "CMSY", "CMEX", "LASY", "MSAM", "MSBM", "RSFS", "STIX",
    "LatinModernMath", "LMMathSymbols",
    "STIXTwoMath", "STIXMath", "XITSMath", "AsanaMath", "CambriaMath",
    "TeXGyrePagellaMath", "TeXGyreTermesMath", "TeXGyreBonumMath",
    "TeXGyreScholaMath", "TeXGyreAdventorMath", "TeXGyreCursorMath",
    "TeXGyreHerosMath",
)

# 判定門檻：LaTeX 頁面覆蓋率（含 LaTeX 字體的頁數／總頁數）
_LATEX_PAGE_RATIO = 0.5


def _is_dense(symbol_seen: bool, latex_pages: int, total: int) -> bool:
    """密集判定（純函式）：公式符號字體存在＋LaTeX 頁面覆蓋率 ≥50%。

    覆蓋率閾值防誤報：論文合集（296 頁僅 2-3 頁殘留 LaTeX 字體，實測
    ALL-Agents PDF）與混合文件不判密集——標注只在整份文件都是 LaTeX
    時出現，避免警告疲勞。
    """
    return bool(symbol_seen) and total > 0 and latex_pages / total >= _LATEX_PAGE_RATIO


@dataclass(frozen=True)
class LatexDetectResult:
    """偵測結果（frozen——UI 標注只讀取）。"""

    is_dense: bool
    total_pages: int
    latex_pages: int
    latex_fonts: frozenset[str] = field(default_factory=frozenset)


def is_latex_font(font_name: str) -> bool:
    """字體名是否屬 Computer Modern／AMS 系（LaTeX 產出標誌）。

    子集前綴（XXXXXX+）剝離後比對；空名→False。
    """
    if not font_name:
        return False
    name = font_name
    if "+" in name:
        name = name.split("+", 1)[1]
    return name.startswith(_CM_PREFIXES)


def _is_symbol_font(font_name: str) -> bool:
    """公式符號字體判定（「數學密集」的關鍵信號）。"""
    if not font_name:
        return False
    name = font_name.split("+", 1)[1] if "+" in font_name else font_name
    return name.startswith(_SYMBOL_PREFIXES)


def detect_latex_dense(pdf_path: str) -> LatexDetectResult | None:
    """掃描 PDF 全部頁字體，判定是否 LaTeX 數學密集。讀取失敗回 None。

    - 無文字層（掃描件）：頁字體清單空 → latex_pages=0 → is_dense=False
    - 檔案不存在／損壞：回 None（呼叫方跳過標注，不中斷既有流程）
    """
    try:
        import pymupdf
    except ImportError:
        logger.warning("pymupdf 未安裝，LaTeX 偵測停用")
        return None
    try:
        doc = pymupdf.open(pdf_path)
    except Exception as exc:
        logger.debug("LaTeX 偵測無法開啟檔案", extra={"path": pdf_path, "error": str(exc)})
        return None
    try:
        total = max(doc.page_count, 0)
        latex_pages = 0
        latex_fonts: set[str] = set()
        symbol_seen = False
        for pno in range(total):
            page_latex = False
            for font in doc[pno].get_fonts():
                fname = font[3]
                if is_latex_font(fname):
                    latex_fonts.add(fname)
                    page_latex = True
                    if _is_symbol_font(fname):
                        symbol_seen = True
            if page_latex:
                latex_pages += 1
        if total == 0:
            return LatexDetectResult(False, 0, 0)
        is_dense = _is_dense(symbol_seen, latex_pages, total)
        return LatexDetectResult(
            is_dense=is_dense,
            total_pages=total,
            latex_pages=latex_pages,
            latex_fonts=frozenset(latex_fonts),
        )
    finally:
        doc.close()
