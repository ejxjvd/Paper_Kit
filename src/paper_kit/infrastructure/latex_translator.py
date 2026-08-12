"""LaTeX 純文字翻譯（票 15）：LaTeX 源碼片段 → 目標語言。

§8 模型鏈（Vault CLAUDE.md 強制）：主 deepseek-chat（40s）＋備援
deepseek-reasoner（40s）——同端點雙模型（防模型級整顆掛事件；備援罕見
觸發，成本影響可忽略）。佔位符 \\PKP{n} 保真是硬規則、寫進 prompt
（AC2 公式 100% 原樣——LLM 不得改動佔位符）。key 走既有 SettingsService
槽位；失敗訊息不外洩 key。
"""

import re
import urllib.request

from paper_kit.application.ports import EngineError, MISSING_API_KEY_MESSAGE
from paper_kit.domain.text_translation import TextTranslation
from paper_kit.infrastructure.llm_client import chat_completion

DEFAULT_LATEX_BASE_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_LATEX_MODEL = "deepseek-chat"
BACKUP_LATEX_MODEL = "deepseek-reasoner"
LATEX_TIMEOUT = 40

_LANG_NAMES = {"zh-TW": "繁體中文", "zh": "繁體中文", "en": "英文"}


def _lang_name(target_lang: str) -> str:
    return _LANG_NAMES.get(target_lang, target_lang)


def build_latex_prompt(chunk: str, target_lang: str) -> str:
    """組裝 LaTeX 翻譯 prompt：佔位符保真＋指令保留是硬性規則（AC2）。"""
    return (
        f"請把下面的 LaTeX 源碼片段逐字翻譯成{_lang_name(target_lang)}。硬性規則：\n"
        "1. \\PKP{數字} 佔位符必須原樣保留、位置不變（內含公式/引用，不可改動）\n"
        "2. 保留全部 LaTeX 指令與結構，只翻譯自然語言文字\n"
        "3. 不改動任何數字、名稱與數學符號\n"
        "4. 只回傳翻譯後的 LaTeX 源碼，不要加任何說明\n"
        "---\n"
        f"{chunk}"
    )


_FENCE_START_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*\n?")
_FENCE_END_RE = re.compile(r"\n?\s*```\s*$")


def strip_markdown_fence(text: str) -> str:
    """LLM 偶發把譯文包在 markdown 程式碼圍欄（```latex ... ```）——剝離。

    真論文 e2e 補（2026-08-12）：圍欄標記原樣注入源碼 → xelatex
    Undefined control sequence（``` 被當指令）。無圍欄輸入位元組原樣
    回傳——L1 無損性質（IdentityTranslator 輸出==原文）不得被破壞。
    """
    if not _FENCE_START_RE.match(text):
        return text
    text = _FENCE_START_RE.sub("", text, count=1)
    return _FENCE_END_RE.sub("", text, count=1)


def _friendly_latex_error(detail: str) -> str:
    if "401" in detail or "Unauthorized" in detail or (
        "key" in detail.lower() and "invalid" in detail.lower()
    ):
        return "API key 無效或已過期（檢查設定頁的 DeepSeek key）"
    return f"LaTeX 翻譯失敗（所有模型無回應）：{detail[-200:]}"


class LatexTranslator:
    """LaTeX 源碼片段翻譯（模型鏈：deepseek-chat 主 → deepseek-reasoner 備援）。"""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_LATEX_MODEL,
        base_url: str = DEFAULT_LATEX_BASE_URL,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._models = (model, BACKUP_LATEX_MODEL)

    def translate_chunk(
        self, chunk: str, target_lang: str = "zh-TW"
    ) -> TextTranslation:
        if not self._api_key:
            raise EngineError(MISSING_API_KEY_MESSAGE)
        last_error = ""
        for model in self._models:
            try:
                return self._call(model, chunk, target_lang)
            except Exception as exc:  # noqa: BLE001——模型鏈：任何失敗都換備援
                last_error = str(exc)
        raise EngineError(_friendly_latex_error(last_error))

    def _call(self, model: str, chunk: str, target_lang: str) -> TextTranslation:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": build_latex_prompt(chunk, target_lang)}
            ],
        }
        if model != BACKUP_LATEX_MODEL:
            # deepseek-reasoner 官方不支援 temperature（送參數可能被拒——備援會死）
            payload["temperature"] = 0.1
        text, in_tokens, out_tokens = chat_completion(
            self._base_url, self._api_key, payload, timeout=LATEX_TIMEOUT
        )
        return TextTranslation(
            text=strip_markdown_fence(text),
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )
