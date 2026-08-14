"""LaTeX 密集 PDF 偵測（v0.1.9.5）：翻譯完成後 UI 標注「行重疊風險」的前置偵測。

背景（2026-08-15 實測診斷）：LaTeX 論文（0211159 Perelman）翻譯後中文行重疊
——BabelDOC 引擎把翻譯行距壓縮到 8.7-9.4pt，小於 Source Han Serif TW 字形
17.2pt → 行間視覺重疊（像素剖面：18.7pt 連續墨跡無間隙）。公式參數
（--formular-font-pattern）與 mono 模式實測皆無效 → 採 UI 標注方案：
偵測 LaTeX 數學密集 PDF（Computer Modern/AMS 字體系），完成後標記卡片。
"""

import pytest

import paper_kit.infrastructure.latex_detector as ld


# ── is_latex_font（純函式）──────────────────────────────────

def test_cm_fonts_are_latex():
    assert ld.is_latex_font("CMR12")
    assert ld.is_latex_font("CMMI10")
    assert ld.is_latex_font("CMSY10")
    assert ld.is_latex_font("CMEX10")
    assert ld.is_latex_font("CMBX12")
    assert ld.is_latex_font("MSBM10")
    assert ld.is_latex_font("LASY10")


def test_latin_modern_fonts_are_latex():
    """lmodern 套件（現代 LaTeX 常見預設）字體名 LMRoman/LMMath——漏判補強。"""
    assert ld.is_latex_font("LMRoman10")
    assert ld.is_latex_font("LMMathItalic10")
    assert ld.is_latex_font("LMSans8")
    assert ld.is_latex_font("LMSS10")


def test_unicode_math_symbol_fonts_count_as_symbol():
    """unicode-math（XeLaTeX/lualatex 路徑）符號字體——判定「數學密集」關鍵。"""
    assert ld._is_symbol_font("LatinModernMath-Regular")
    assert ld._is_symbol_font("STIXTwoMath-Regular")
    assert ld._is_symbol_font("XITSMath-Regular")
    assert ld._is_symbol_font("TeXGyreTermesMath-Regular")
    assert not ld._is_symbol_font("CMR12")  # 正文字體非符號
    assert not ld._is_symbol_font("ArialMT")


def test_subset_prefixed_cm_fonts_are_latex():
    """PDF 子集嵌入的字體名帶 6 字元前綴（XXXXXX+CMR10）——實測 fixture。"""
    assert ld.is_latex_font("FUIULY+CMR10")
    assert ld.is_latex_font("NSOWGJ+CMSY10")
    assert ld.is_latex_font("THPNLT+CMEX9")


def test_cjk_and_common_fonts_are_not_latex():
    assert not ld.is_latex_font("SourceHanSerifTW-Regular")
    assert not ld.is_latex_font("NotoSansCJK-Regular")
    assert not ld.is_latex_font("ArialMT")
    assert not ld.is_latex_font("TimesNewRomanPSMT")
    assert not ld.is_latex_font("")


def test_detect_dense_on_latex_fixture():
    """tests/fixtures/paper_p34.pdf 實測為 LaTeX 論文（CMR10/CMSY10/CMMI10…）。"""
    result = ld.detect_latex_dense("tests/fixtures/paper_p34.pdf")
    assert result is not None
    assert result.is_dense
    assert result.latex_pages >= result.total_pages  # 每頁都是 LaTeX
    assert any("CMSY" in f or "CMEX" in f or "LASY" in f or "MSBM" in f
               for f in result.latex_fonts), "公式符號字體必須存在才算密集"


def test_detect_not_dense_on_scan_fixture():
    """掃描件 fixture（無文字層）→ 不判定 LaTeX 密集（None=無法判定）。"""
    result = ld.detect_latex_dense("tests/fixtures/scan_fixture.pdf")
    assert result is None or not result.is_dense


def test_detect_missing_file_returns_none():
    assert ld.detect_latex_dense("tests/fixtures/no_such_file.pdf") is None


def test_mixed_pdf_below_ratio_is_not_dense():
    """296 頁論文合集實測案例：僅 2-3 頁殘留 LaTeX 字體 → 不判密集
    （覆蓋率 <50% 閾值——防合集/混合文件誤報）。"""
    assert not ld._is_dense(symbol_seen=True, latex_pages=3, total=296)
    assert not ld._is_dense(symbol_seen=True, latex_pages=1, total=10)


def test_dense_requires_symbol_font_and_ratio():
    """密集判定需同時滿足：符號字體存在＋LaTeX 頁面覆蓋率 ≥50%。"""
    assert ld._is_dense(symbol_seen=True, latex_pages=10, total=10)
    assert ld._is_dense(symbol_seen=True, latex_pages=5, total=10)
    assert not ld._is_dense(symbol_seen=True, latex_pages=4, total=10)  # 低於 50%
    assert not ld._is_dense(symbol_seen=False, latex_pages=10, total=10)  # 無符號字體
    assert not ld._is_dense(symbol_seen=True, latex_pages=0, total=0)  # 空文件
