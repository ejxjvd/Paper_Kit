"""e2e 真論文實測：merge_inputs 合併工具的 TDD 測試。

素材：arXiv 1706.03762（Attention Is All You Need）多檔結構——
ms.tex 主檔 \input 七個分章 + thebibliography。合併成單一 .tex
才能走 Paper_Kit LatexAdapter（單檔輸入）→ xelatex 編譯。
"""

import pytest

from merge_inputs import expand_inputs


def _mk(tmp_path, files: dict[str, str]) -> None:
    for name, content in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def test_expand_single_input(tmp_path):
    _mk(tmp_path, {
        "main.tex": "\\begin{document}\n\\input{intro}\n\\end{document}\n",
        "intro.tex": "Hello world.\n",
    })
    assert "Hello world." in expand_inputs(tmp_path, "main.tex")


def test_expand_with_and_without_tex_extension(tmp_path):
    _mk(tmp_path, {
        "main.tex": "\\input{a}\n\\input{b.tex}\n",
        "a.tex": "AAA\n",
        "b.tex": "BBB\n",
    })
    out = expand_inputs(tmp_path, "main.tex")
    assert "AAA" in out and "BBB" in out


def test_input_line_replaced_not_kept(tmp_path):
    _mk(tmp_path, {
        "main.tex": "pre\n\\input{intro}\npost\n",
        "intro.tex": "MID",
    })
    out = expand_inputs(tmp_path, "main.tex")
    assert "\\input{intro}" not in out
    assert out.index("pre") < out.index("MID") < out.index("post")


def test_recursive_input(tmp_path):
    """遞迴展開：\input 內再 \input。展開內容的換行保留（TeX 語意）。"""
    _mk(tmp_path, {
        "main.tex": "\\input{outer}\n",
        "outer.tex": "O>\\input{inner}<O\n",
        "inner.tex": "INNER",
    })
    assert "O>INNER<O" in expand_inputs(tmp_path, "main.tex")


def test_commented_input_not_expanded(tmp_path):
    _mk(tmp_path, {
        "main.tex": "% \\input{intro}\n\\input{intro}\n",
        "intro.tex": "REAL\n",
    })
    out = expand_inputs(tmp_path, "main.tex")
    assert out.count("REAL") == 1
    assert "% \\input{intro}" in out  # 註解行原樣保留


def test_inline_comment_not_expanded(tmp_path):
    """行內註解（% 之後）的 \input 不展開——註解在 LaTeX 是行尾範圍。"""
    _mk(tmp_path, {
        "main.tex": "text % \\input{intro}\n\\input{intro}\n",
        "intro.tex": "REAL\n",
    })
    out = expand_inputs(tmp_path, "main.tex")
    assert out.count("REAL") == 1
    assert "text % \\input{intro}" in out


def test_inline_input_expands(tmp_path):
    _mk(tmp_path, {
        "main.tex": "A>\\input{mid}<A\n",
        "mid.tex": "MID",
    })
    assert "A>MID<A" in expand_inputs(tmp_path, "main.tex")


def test_missing_input_raises_with_path(tmp_path):
    _mk(tmp_path, {"main.tex": "\\input{nope}\n"})
    with pytest.raises(FileNotFoundError, match="nope"):
        expand_inputs(tmp_path, "main.tex")


def test_cycle_detection(tmp_path):
    _mk(tmp_path, {
        "main.tex": "\\input{a}\n",
        "a.tex": "\\input{b}\n",
        "b.tex": "\\input{a}\n",
    })
    with pytest.raises(RuntimeError, match="cycle"):
        expand_inputs(tmp_path, "main.tex")


def test_relative_subdir_input(tmp_path):
    _mk(tmp_path, {
        "main.tex": "\\input{sub/part}\n",
        "sub/part.tex": "SUBDIR\n",
    })
    assert "SUBDIR" in expand_inputs(tmp_path, "main.tex")


def test_comment_lines_and_newcommands_untouched(tmp_path):
    """前置區（\documentclass/\newcommand/註解）不是 \input 行——必須原樣。"""
    _mk(tmp_path, {
        "main.tex": "\\documentclass{article}\n% a note\n\\newcommand\\kq{q}\n\\begin{document}\n\\input{intro}\n\\end{document}\n",
        "intro.tex": "Body.\n",
    })
    out = expand_inputs(tmp_path, "main.tex")
    assert "\\documentclass{article}" in out
    assert "% a note" in out
    assert "\\newcommand\\kq{q}" in out
