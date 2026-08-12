"""票 15：LatexAdapter——LaTeX 源碼翻譯主管線。

管線：讀 .tex（UTF-8）→ 分段（equation 等整段 keep）→ 行內公式/引用
\\PKP 佔位 → LLM 翻譯（模型鏈）→ 還原佔位 → 組裝 → xelatex 編譯 →
JobResult（mono = 編譯 PDF；tokens 累加 → CostService 記錄入歷史）。
Fake 接縫：translator / compiler 注入（同 PptVisionAdapter 模式）。
"""

import pytest

from paper_kit.application.ports import EngineError, MISSING_API_KEY_MESSAGE
from paper_kit.domain.text_translation import TextTranslation
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.latex_adapter import LatexAdapter, LatexConfig

_SOURCE = (
    "% preamble comment\n"
    "\\documentclass{article}\n"
    "\\usepackage{amsmath}\n"
    "\\begin{document}\n"
    "\\section{Transformer Architecture}\n"
    "We show $E = mc^2$ and cite \\cite{knuth84}.\n"
    "\\begin{itemize}\n"
    "\\item First point.\n"
    "\\end{itemize}\n"
    "\\begin{equation}\n"
    "F = ma\n"
    "\\end{equation}\n"
    "\\end{document}\n"
)


class FakeTranslator:
    """記錄 (chunk, lang)；譯文 = 原樣回傳（還原佔位可驗證）；tokens 固定。"""

    def __init__(self, cancel_cb=None):
        self.calls: list[tuple[str, str]] = []
        self._cancel_cb = cancel_cb

    def translate_chunk(self, chunk: str, target_lang: str = "zh-TW"):
        self.calls.append((chunk, target_lang))
        if self._cancel_cb:
            self._cancel_cb()
        return TextTranslation(text=chunk, input_tokens=7, output_tokens=3)


class FakeCompiler:
    def __init__(self):
        self.calls: list[object] = []
        self.pdf = None

    def compile(self, tex_path, out_dir):
        self.calls.append(tex_path)
        self.pdf = out_dir / "out.pdf"
        self.pdf.write_bytes(b"%PDF-fake")
        return self.pdf


def _job(tmp_path) -> TranslationJob:
    src = tmp_path / "paper.tex"
    src.write_text(_SOURCE, encoding="utf-8")
    return TranslationJob(
        job_id="j1", source_path=str(src), target_lang="zh-TW", engine_id="latex"
    )


def test_translate_full_pipeline(tmp_path):
    translator = FakeTranslator()
    compiler = FakeCompiler()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=compiler)
    result = adapter.translate(_job(tmp_path))

    # JobResult：mono = 編譯 PDF、tokens 累加（3 段可譯 × 7/3）
    assert result.mono_path == str(compiler.pdf)
    assert result.dual_path is None
    assert result.input_tokens == 21
    assert result.output_tokens == 9

    # 組裝輸出：前置/註解/equation 原樣，標題字首保留、內文翻譯
    out_tex = compiler.calls[0]
    rendered = out_tex.read_text(encoding="utf-8")
    assert "% preamble comment" in rendered
    assert "\\documentclass{article}" in rendered
    assert "\\begin{equation}\nF = ma\n\\end{equation}" in rendered  # 公式 100% 原樣（AC2）
    assert "\\section{Transformer Architecture}" in rendered  # 字首＋內文原樣（Fake 回傳原樣）
    assert "\\item First point." in rendered  # item 字首保留＋內文翻譯（spec review 補）
    assert "$E = mc^2$" in rendered  # 行內公式還原
    assert "\\cite{knuth84}" in rendered


def test_translate_protects_inline_math_before_sending(tmp_path):
    translator = FakeTranslator()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=FakeCompiler())
    adapter.translate(_job(tmp_path))
    sent_chunks = [c for c, _ in translator.calls]
    assert all("$E = mc^2$" not in c for c in sent_chunks)  # 保護後才送翻譯
    assert any("\\PKP{0}" in c for c in sent_chunks)


def test_translate_missing_key_early_error(tmp_path):
    translator = FakeTranslator()
    compiler = FakeCompiler()
    adapter = LatexAdapter(LatexConfig(api_key=""), translator=translator, compiler=compiler)
    with pytest.raises(EngineError, match=MISSING_API_KEY_MESSAGE):
        adapter.translate(_job(tmp_path))
    assert translator.calls == []  # 缺 key 先於任何翻譯/編譯（不白跑）
    assert compiler.calls == []


def test_translate_missing_source_friendly_error(tmp_path):
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), compiler=FakeCompiler())
    job = TranslationJob(job_id="j1", source_path=str(tmp_path / "nope.tex"), target_lang="zh-TW", engine_id="latex")
    with pytest.raises(EngineError, match="找不到"):
        adapter.translate(job)


def test_cancel_before_translate_rejects(tmp_path):
    translator = FakeTranslator()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=FakeCompiler())
    adapter.cancel()
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(_job(tmp_path))
    assert translator.calls == []


def test_cancel_mid_pipeline_stops_after_first_chunk(tmp_path):
    # 第一段翻譯後取消（模擬使用者在翻譯中途按取消）
    holder = {}
    adapter_ref = {}

    def cancel_cb():
        holder["adapter"].cancel()

    translator = FakeTranslator(cancel_cb=lambda: None)
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=FakeCompiler())
    holder["adapter"] = adapter
    # 覆寫：翻譯呼叫第二次時取消
    original = translator.translate_chunk

    def interrupt(*args, **kwargs):
        out = original(*args, **kwargs)
        if len(translator.calls) == 1:
            adapter.cancel()
        return out

    translator.translate_chunk = interrupt
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(_job(tmp_path))
    assert len(translator.calls) == 1  # 第二段沒送翻譯


def test_translate_non_utf8_source_gives_friendly_error(tmp_path):
    src = tmp_path / "paper.tex"
    src.write_bytes(b"\x80\x81 not utf8")
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), compiler=FakeCompiler())
    job = TranslationJob(job_id="j1", source_path=str(src), target_lang="zh-TW", engine_id="latex")
    with pytest.raises(EngineError, match="UTF-8"):
        adapter.translate(job)
