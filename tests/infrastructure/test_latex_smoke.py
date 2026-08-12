"""票 15 AC1/AC2：真實 xelatex 冒煙——xeCJK 中文 fixture 可編譯、公式原樣。

真實 LLM 翻譯屬慢冒煙（花錢＋上游依賴），以 FakeTranslator 取代（同票 14
smoke 模式）；本測試驗證「真 .tex → 分段/佔位/還原 → 真 xelatex 編譯」
管線（真實編譯——xeCJK 中文是 xelatex 關鍵能力，pdflatex 做不到）。
xelatex 未裝時 skip（訊息含 MiKTeX 安裝指引）。
"""

from pathlib import Path

import pytest

from paper_kit.domain.text_translation import TextTranslation
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.latex_adapter import LatexAdapter, LatexConfig
from paper_kit.infrastructure.tex_compiler import TeXCompiler, find_xelatex

pytestmark = pytest.mark.slow

# AC1 fixture：xeCJK 中文＋equation 公式（Microsoft JhengHei = Windows 內建字體，
# xelatex.exe 是 Windows 程式 → 直接可用；PDF 字體嵌入）
_FIXTURE_TEX = (
    "% 票 15 smoke fixture：xeCJK 中文＋equation 公式保真\n"
    "\\documentclass{article}\n"
    "\\usepackage{amsmath}\n"
    "\\usepackage{xeCJK}\n"
    "\\setCJKmainfont{Microsoft JhengHei}\n"
    "\\begin{document}\n"
    "\\title{論文翻譯測試}\n"
    "\\author{Paper Kit}\n"
    "\\maketitle\n"
    "\\section{引言}\n"
    "這是繁體中文測試文字。\n"
    "\\begin{equation}\n"
    "E = mc^2\n"
    "\\label{eq:einstein}\n"
    "\\end{equation}\n"
    "請見公式 \\eqref{eq:einstein}。\n"
    "\\end{document}\n"
)


@pytest.fixture(scope="module")
def xelatex():
    xelatex = find_xelatex()
    if not xelatex:
        pytest.skip("未偵測到 xelatex（winget install MiKTeX.MiKTeX）")
    return xelatex


def test_real_xelatex_compiles_cjk_fixture(tmp_path, xelatex):
    """AC1：真 xelatex 編譯中文 fixture → PDF 存在、中文渲染成文字層。"""
    tex = tmp_path / "fixture.tex"
    tex.write_text(_FIXTURE_TEX, encoding="utf-8")
    pdf = TeXCompiler(xelatex=xelatex).compile(tex, tmp_path / "out")

    import pymupdf

    doc = pymupdf.open(str(pdf))
    try:
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
        assert "論文翻譯測試" in text  # xeCJK 中文渲染成功
        assert "引言" in text
    finally:
        doc.close()


def test_latex_pipeline_real_compile_fake_translator(tmp_path, xelatex):
    """AC2 全鏈：Fake 譯文（含中文）→ 佔位還原 → 真編譯——公式原樣＋中文可編譯。

    Fake 譯文 = 「繁體譯文：」前綴＋原樣 chunk（含 \\PKP 佔位）——還原後
    行內公式/引用原樣回填；equation 環境整段 keep 不送翻譯（公式 100% 原樣）。
    """
    class FakeTranslator:
        def translate_chunk(self, chunk: str, target_lang: str = "zh-TW"):
            return TextTranslation(text="繁體譯文：" + chunk, input_tokens=5, output_tokens=2)

    src = tmp_path / "paper.tex"
    src.write_text(_FIXTURE_TEX, encoding="utf-8")
    job = TranslationJob(job_id="smoke", source_path=str(src), target_lang="zh-TW")
    adapter = LatexAdapter(
        LatexConfig(api_key="FAKE-KEY"),
        translator=FakeTranslator(),
        compiler=TeXCompiler(xelatex=xelatex),
    )
    result = adapter.translate(job)

    # 翻譯後源碼：公式原樣（AC2）、標題字首保留＋內文翻譯（Fake 前綴「繁體譯文：」）
    out_tex = src.parent / "latex" / "paper-zh-TW.tex"
    rendered = out_tex.read_text(encoding="utf-8")
    assert "E = mc^2" in rendered
    assert "\\section{繁體譯文：引言}" in rendered  # 字首不變、內文替換
    assert "\\title{繁體譯文：論文翻譯測試}" in rendered
    assert "\\eqref{eq:einstein}" in rendered

    # 編譯 PDF：中文＋原文段落（Fake 譯文帶中文前綴）
    assert result.mono_path and Path(result.mono_path).exists()
    import pymupdf

    doc = pymupdf.open(result.mono_path)
    try:
        text = "".join(doc[i].get_text() for i in range(doc.page_count))
        assert "繁體譯文" in text  # xeCJK 渲染 Fake 中文譯文
    finally:
        doc.close()
