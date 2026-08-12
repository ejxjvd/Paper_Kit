"""票 15：LatexTranslator——純文字 LLM 模型鏈（DeepSeek chat → reasoner 備援）。

走共用 llm_client 傳輸；本模組只管模型鏈（§8 fallback：主失敗換備援、
成功即停、全掛才失敗）＋prompt（佔位符 \\PKP{n} 必須原樣保留——公式保真）。
"""

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.latex_translator import (
    DEFAULT_LATEX_MODEL,
    LatexTranslator,
    build_latex_prompt,
    strip_markdown_fence,
)


def install(monkeypatch, outcomes: dict[str, object]):
    """依 model 分派回傳（FakeUrlopen 模式，照 test_siliconflow_vision）。"""

    class FakeUrlopen:
        def __init__(self):
            self.calls: list[object] = []

        def __call__(self, request, timeout):
            self.calls.append(request)
            import json

            payload = json.loads(request.data)
            model = payload["model"]
            if model not in outcomes:
                raise RuntimeError(f"no outcome for {model}")
            out = outcomes[model]
            if isinstance(out, Exception):
                raise out
            body = json.dumps({
                "choices": [{"message": {"content": out}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }).encode("utf-8")

            class FakeResp:
                def read(self):
                    return body

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            return FakeResp()

    fake = FakeUrlopen()
    monkeypatch.setattr(
        "paper_kit.infrastructure.latex_translator.urllib.request.urlopen", fake
    )
    return fake


def test_build_latex_prompt_orders_placeholder_preservation():
    prompt = build_latex_prompt("\\section{Intro}\nText with \\PKP{0}.", "zh-TW")
    assert "繁體中文" in prompt
    assert "\\PKP" in prompt  # 佔位符規則寫進 prompt
    assert "\\section{Intro}\nText with \\PKP{0}." in prompt


def test_translate_chunk_success_does_not_try_backup(monkeypatch):
    fake = install(monkeypatch, {DEFAULT_LATEX_MODEL: "譯文：\\PKP{0} 保留"})
    result = LatexTranslator("KEY").translate_chunk("Text \\PKP{0}.", "zh-TW")
    assert result.text == "譯文：\\PKP{0} 保留"
    assert result.input_tokens == 10
    assert result.output_tokens == 5
    assert len(fake.calls) == 1  # 主成功不試備援


def test_translate_chunk_falls_back_to_reasoner_on_primary_failure(monkeypatch):
    install(
        monkeypatch,
        {DEFAULT_LATEX_MODEL: RuntimeError("upstream down"), "deepseek-reasoner": "備援譯文"},
    )
    result = LatexTranslator("KEY").translate_chunk("Text.", "zh-TW")
    assert result.text == "備援譯文"


def test_reasoner_backup_sends_no_temperature(monkeypatch):
    """deepseek-reasoner 官方不支援 temperature——備援 payload 不含該參數。"""
    fake = install(
        monkeypatch,
        {DEFAULT_LATEX_MODEL: RuntimeError("upstream down"), "deepseek-reasoner": "備援譯文"},
    )
    LatexTranslator("KEY").translate_chunk("Text.", "zh-TW")
    import json

    primary = json.loads(fake.calls[0].data)
    backup = json.loads(fake.calls[1].data)
    assert "temperature" in primary  # 主模型（chat）照送
    assert "temperature" not in backup  # 備援（reasoner）不送


def test_translate_chunk_all_models_fail_gives_friendly_error(monkeypatch):
    fake = install(
        monkeypatch,
        {DEFAULT_LATEX_MODEL: RuntimeError("boom"), "deepseek-reasoner": RuntimeError("boom2")},
    )
    translator = LatexTranslator("KEY")
    with pytest.raises(EngineError, match="LaTeX 翻譯失敗"):
        translator.translate_chunk("Text.", "zh-TW")
    assert len(fake.calls) == 2  # 鏈全試


def test_translate_chunk_missing_key_early_error(monkeypatch):
    install(monkeypatch, {})
    with pytest.raises(EngineError, match="API key"):
        LatexTranslator("").translate_chunk("Text.", "zh-TW")


# ── 真論文 e2e 補（2026-08-12）：LLM 回傳 markdown 圍欄剝離 ──────────────


def test_strip_markdown_fence_removes_latex_fence():
    """LLM 偶發把譯文包在 ```latex ... ``` 圍欄——需剝離（e2e 實測根因）。"""
    assert strip_markdown_fence("```latex\n譯文內容\n```") == "譯文內容"


def test_strip_markdown_fence_without_lang_tag():
    assert strip_markdown_fence("```\n譯文內容\n```") == "譯文內容"


def test_strip_markdown_fence_no_fence_returns_identical():
    """無圍欄輸入位元組原樣——L1 無損性質（IdentityTranslator）不得被破壞。"""
    chunk = "plain \\PKP{0} text\n"
    assert strip_markdown_fence(chunk) == chunk


def test_translate_chunk_strips_fence_from_response(monkeypatch):
    """端到端：translate_chunk 回傳的譯文不得含 ``` 圍欄（xelatex undefined 根因）。"""
    install(monkeypatch, {DEFAULT_LATEX_MODEL: "```latex\n譯文內容\n```"})
    result = LatexTranslator("KEY").translate_chunk("Text.", "zh-TW")
    assert result.text == "譯文內容"
    assert "```" not in result.text
