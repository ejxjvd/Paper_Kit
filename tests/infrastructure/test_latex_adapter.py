"""票 15：LatexAdapter——LaTeX 源碼翻譯主管線。

管線：讀 .tex（UTF-8）→ 分段（equation 等整段 keep）→ 行內公式/引用
\\PKP 佔位 → LLM 翻譯（模型鏈）→ 還原佔位 → 組裝 → xelatex 編譯 →
JobResult（mono = 編譯 PDF；tokens 累加 → CostService 記錄入歷史）。
Fake 接縫：translator / compiler 注入（同 PptVisionAdapter 模式）。
"""

from pathlib import Path

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
    """記錄 (chunk, lang)；譯文 = 前綴＋原樣（還原佔位可驗證）；tokens 固定。"""

    def __init__(self, cancel_cb=None, prefix: str = ""):
        self.calls: list[tuple[str, str]] = []
        self._cancel_cb = cancel_cb
        self._prefix = prefix

    def translate_chunk(self, chunk: str, target_lang: str = "zh-TW"):
        self.calls.append((chunk, target_lang))
        if self._cancel_cb:
            self._cancel_cb()
        return TextTranslation(text=self._prefix + chunk, input_tokens=7, output_tokens=3)


class FakeCompiler:
    def __init__(self):
        self.calls: list[object] = []
        self.pdf = None
        self.include_dirs = None

    def compile(self, tex_path, out_dir, include_dirs=()):
        self.calls.append(tex_path)
        self.include_dirs = list(include_dirs)
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


# ── 真論文 e2e 補（2026-08-12）：CJK 注入＋源碼目錄傳遞 ──────────────────


def test_translate_injects_cjk_for_chinese_translation(tmp_path):
    """譯文含中文（真論文情境）→ 組裝檔自動注入 xeCJK＋中文字型。"""
    translator = FakeTranslator(prefix="繁體譯文：")
    compiler = FakeCompiler()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=compiler)
    adapter.translate(_job(tmp_path))
    out_tex = compiler.calls[0].read_text(encoding="utf-8")
    assert "\\usepackage{xeCJK}" in out_tex
    assert "\\setCJKmainfont" in out_tex
    assert out_tex.index("\\usepackage{xeCJK}") < out_tex.index("\\begin{document}")


def test_translate_passes_source_dir_as_include_dirs(tmp_path):
    """編譯需源碼目錄（sty/Figures 附屬檔）→ include_dirs 傳給 compiler。"""
    compiler = FakeCompiler()
    adapter = LatexAdapter(
        LatexConfig(api_key="KEY"), translator=FakeTranslator(), compiler=compiler
    )
    job = _job(tmp_path)
    adapter.translate(job)
    src_dir = Path(job.source_path).parent
    assert compiler.include_dirs == [src_dir]


# ── 真論文 e2e 補（2026-08-12）：譯文 \PKP 殘留偵測＋重試 ─────────────────


class FlakyTranslator(FakeTranslator):
    """第一次回傳異常譯文（\PKP 殘留）、之後正常——模擬 LLM 偶發幻覺。

    注意：不 call super().translate_chunk（FakeTranslator 也 append 呼叫——
    重試路徑會雙重計數，e2e 診斷實測）。
    """

    def __init__(self, bad_text: str, **kw):
        super().__init__(**kw)
        self._bad_text = bad_text
        self._attempts = 0

    def translate_chunk(self, chunk, target_lang="zh-TW"):
        self.calls.append((chunk, target_lang))
        self._attempts += 1
        if self._attempts == 1:
            return TextTranslation(text=self._bad_text, input_tokens=7, output_tokens=3)
        return TextTranslation(text=chunk, input_tokens=7, output_tokens=3)


class AlwaysBadTranslator(FlakyTranslator):
    """每次都回傳異常譯文。"""

    def translate_chunk(self, chunk, target_lang="zh-TW"):
        self.calls.append((chunk, target_lang))
        self._attempts += 1
        return TextTranslation(text=self._bad_text, input_tokens=7, output_tokens=3)


def test_translate_retries_when_placeholder_left(tmp_path):
    """LLM 偶發幻覺（譯文含 \PKP{99} 等無效佔位）→ 該段重試一次、成功續跑。"""
    translator = FlakyTranslator(bad_text="\\PKP{99} 異常譯文")
    compiler = FakeCompiler()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=compiler)
    result = adapter.translate(_job(tmp_path))
    out_tex = compiler.calls[0].read_text(encoding="utf-8")
    assert "\\PKP{99}" not in out_tex  # 異常譯文被丟棄
    # _SOURCE 有 3 段可譯：標題段（第一段）異常 → 重試；其餘各 1 次 = 4 次呼叫
    assert len(translator.calls) == 4
    # 重試 tokens 計入（誠實成本）
    assert result.input_tokens == 28  # 標題段 2×7 + 正文 7 + item 7
    assert result.output_tokens == 12


def test_translate_fails_when_placeholder_always_left(tmp_path):
    """兩次都異常 → EngineError（不產出壞 PDF）。"""
    translator = AlwaysBadTranslator(bad_text="\\PKP{99} 異常譯文")
    compiler = FakeCompiler()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=compiler)
    with pytest.raises(EngineError, match="佔位符"):
        adapter.translate(_job(tmp_path))
    assert compiler.calls == []  # 沒編譯


def test_title_with_inline_body_translated_whole(tmp_path):
    """「\\paragraph{Decoder:}The decoder...」（標題＋行內正文）→ 整段送翻譯。

    e2e 實測（2026-08-12）：只送 content「Decoder:」太短、無上下文 → LLM
    幻覺補全（連續兩次虛構證明段＋編造 \\PKP 編號）——整段（含指令）送時
    回傳完美（「\\paragraph{解碼器：}解碼器同樣由...」）。
    """
    src = tmp_path / "paper.tex"
    src.write_text(
        "\\documentclass{article}\n\\begin{document}\n"
        "\\paragraph{Decoder:}The decoder is also composed of $N=6$ layers.\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    translator = FakeTranslator()
    compiler = FakeCompiler()
    adapter = LatexAdapter(LatexConfig(api_key="KEY"), translator=translator, compiler=compiler)
    adapter.translate(
        TranslationJob(
            job_id="j", source_path=str(src), target_lang="zh-TW", engine_id="latex"
        )
    )
    sent = translator.calls[0][0]
    assert sent.startswith("\\paragraph{Decoder:}")  # 整段（含指令）送翻譯
    assert "composed of" in sent  # 行內正文也一起送（不只「Decoder:」）
    assert "\\PKP{0}" in sent  # 行內公式仍保護
