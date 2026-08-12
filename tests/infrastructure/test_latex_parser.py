"""票 15：LaTeX 源碼解析器——分段（可譯文字 vs 原封保留）＋行內指令佔位。

公式 100% 原樣（AC2）的關鍵：equation 環境整段 keep、行內 $...$/\\cite/\\ref
抽成 \\PKP{n} 佔位符保護（LLM 不會改動），翻譯後原樣還原。
"""

import pytest

from paper_kit.infrastructure.latex_parser import (
    inject_cjk_support,
    protect_tex_inline,
    restore_tex_inline,
    split_tex_segments,
)


def test_split_keeps_equation_environment_and_translates_text():
    source = (
        "\\begin{equation}\n"
        "E = mc^2\n"
        "\\end{equation}\n"
        "This is a plain sentence.\n"
    )
    segments = split_tex_segments(source)
    assert [(s.kind, s.content) for s in segments] == [
        ("keep", "\\begin{equation}\n"),
        ("keep", "E = mc^2\n"),
        ("keep", "\\end{equation}\n"),
        ("translate", "This is a plain sentence.\n"),
    ]


def test_split_merges_consecutive_text_lines_into_one_translate_segment():
    source = "First line of paragraph.\nSecond line, same paragraph.\n\\end{document}\n"
    segments = split_tex_segments(source)
    translate = [s for s in segments if s.kind == "translate"]
    assert len(translate) == 1  # 合併成一段（一次 API 呼叫）
    assert "First line" in translate[0].content
    assert "Second line" in translate[0].content


def test_split_keeps_comments_preamble_and_packages():
    source = (
        "% comment line\n"
        "\\documentclass{article}\n"
        "\\usepackage{amsmath}\n"
        "\\begin{document}\n"
        "Real text here.\n"
    )
    segments = split_tex_segments(source)
    keeps = [s.content for s in segments if s.kind == "keep"]
    assert "% comment line\n" in keeps
    assert "\\documentclass{article}\n" in keeps
    assert "\\usepackage{amsmath}\n" in keeps
    translate = [s for s in segments if s.kind == "translate"]
    assert len(translate) == 1
    assert "Real text here." in translate[0].content


def test_split_translates_section_title_bracket_content_only():
    """\\section{...} 指令字首原封、花括號內文可譯（fixture 論文標題要翻）。"""
    source = "\\section{Transformer Architecture}\n"
    segments = split_tex_segments(source)
    assert segments[0].kind == "translate"
    assert "\\section{Transformer Architecture}" in segments[0].content
    # 翻譯側再處理：指令字首與內文分離（adapter 負責）


def test_split_title_line_stays_its_own_segment():
    """標題行獨立段（回歸：與後文合併會讓 rfind('}') 錯切到 \\cite 閉括）。"""
    source = (
        "\\section{Transformer Architecture}\n"
        "We show $E = mc^2$ and cite \\cite{knuth84}.\n"
    )
    segments = split_tex_segments(source)
    assert [s.kind for s in segments] == ["translate", "translate"]
    assert segments[0].content == "\\section{Transformer Architecture}\n"


def test_split_document_environment_body_is_translatable():
    """\\begin{document} 是正文容器非內容環境——內文照常可譯。"""
    source = "\\begin{document}\nReal text here.\n\\end{document}\n"
    segments = split_tex_segments(source)
    translate = [s for s in segments if s.kind == "translate"]
    assert len(translate) == 1
    assert "Real text here." in translate[0].content


def test_protect_inline_math_citations_and_refs_roundtrip():
    text = "We show $E = mc^2$ and cite \\cite{knuth84} plus \\ref{eq:1}."
    protected, placeholders = protect_tex_inline(text)
    assert "$E = mc^2$" not in protected
    assert "\\cite{knuth84}" not in protected
    assert "\\ref{eq:1}" not in protected
    assert len(placeholders) == 3  # 公式 + cite + ref
    # 還原：佔位符換回原文
    restored = restore_tex_inline(protected, placeholders)
    assert restored == text


def test_protect_inline_math_bracket_form():
    text = "Inline math \\(a+b\\) stays protected."
    protected, placeholders = protect_tex_inline(text)
    assert "\\(a+b\\)" not in protected
    assert restore_tex_inline(protected, placeholders) == text


def test_protect_display_math_between_paragraphs():
    """\\[...\\] 與 $$...$$ 段落間公式（不屬環境時）也要保護——spec review 缺口。"""
    text = "Paragraph with \\[E = mc^2\\] display and $$F = ma$$ formula."
    protected, placeholders = protect_tex_inline(text)
    assert "\\[E = mc^2\\]" not in protected
    assert "$$F = ma$$" not in protected
    assert len(placeholders) == 2
    assert restore_tex_inline(protected, placeholders) == text


def test_split_item_lines_are_translatable():
    """\\item 行獨立段可譯（spec review 補：原被「\\ 開頭 keep」擋住）。"""
    source = (
        "\\begin{itemize}\n"
        "\\item First point.\n"
        "\\item Second point.\n"
        "\\end{itemize}\n"
    )
    segments = split_tex_segments(source)
    kinds = [s.kind for s in segments]
    assert kinds == ["keep", "translate", "translate", "keep"]
    assert segments[1].content == "\\item First point.\n"


def test_split_keeps_label_figures_and_tables():
    source = (
        "\\begin{figure}\n"
        "\\includegraphics{img.png}\n"
        "\\caption{A diagram.}\n"
        "\\label{fig:1}\n"
        "\\end{figure}\n"
    )
    segments = split_tex_segments(source)
    assert all(s.kind == "keep" for s in segments)


# ── 真論文 e2e 補（2026-08-12）：CJK 支援自動注入 ──────────────────


def test_inject_cjk_into_english_preamble():
    """原文無 xeCJK（英文論文）＋譯文含中文 → 前置區注入 xeCJK＋中文字型。"""
    src = (
        "\\documentclass{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\begin{document}\n"
        "轉換器基於純注意力機制。\n"  # 組裝後：譯文已含中文
        "\\end{document}\n"
    )
    out = inject_cjk_support(src)
    assert "\\usepackage{xeCJK}" in out
    assert "\\setCJKmainfont" in out
    # 注入位置：\begin{document} 之前
    assert out.index("\\usepackage{xeCJK}") < out.index("\\begin{document}")
    # 原內容不破壞
    assert "\\usepackage[utf8]{inputenc}" in out
    assert "轉換器基於純注意力機制。" in out


def test_inject_cjk_does_not_duplicate():
    src = (
        "\\documentclass{article}\n"
        "\\usepackage{xeCJK}\n"
        "\\begin{document}\n"
        "\\end{document}\n"
    )
    assert inject_cjk_support(src) == src  # 已含 xeCJK → 原樣


def test_inject_cjk_only_with_options_form():
    src = (
        "\\documentclass{article}\n"
        "\\usepackage[boldfont]{xeCJK}\n"
        "\\begin{document}\n"
        "\\end{document}\n"
    )
    assert inject_cjk_support(src) == src


def test_author_block_kept_whole():
    """\\author 區塊（\\AND/\\thanks 分隔結構）整段 keep——送 LLM 會被重排。"""
    source = (
        "\\author{\n"
        "  \\AND\n"
        "  Ashish Vaswani\\thanks{Equal contribution.}\\\\\n"
        "  Google Brain\\\\\n"
        "  \\texttt{ava@google.com}\\\\\n"
        "}\n"
    )
    segments = split_tex_segments(source)
    assert all(s.kind == "keep" for s in segments)
    assembled = "".join(s.content for s in segments)
    assert assembled == source  # 位元組原樣


def test_restore_tolerates_space_after_placeholder_prefix():
    """LLM 偶發 \PKP {n}（多一個空格）——restore 需容忍（e2e 實測缺口）。"""
    placeholders = ["$E = mc^2$"]
    assert restore_tex_inline("譯文 \PKP {0} 結束", placeholders) == "譯文 $E = mc^2$ 結束"
    assert restore_tex_inline("譯文 \PKP{0} 結束", placeholders) == "譯文 $E = mc^2$ 結束"
