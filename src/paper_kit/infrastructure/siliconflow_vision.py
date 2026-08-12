"""SiliconFlow 視覺翻譯（票 14）：把幻燈片圖送 gemma 眼睛翻譯成目標語言。

紅線（Vault CLAUDE.md §8 立法）：外部 API 一律 fallback 鏈＋逾時——主模型
google/gemma-4-31B-it（40s，複雜圖品質實測定案；同 paste-vision hook）＋
備援 12B（8s），成功即停、全掛才失敗（EngineError）。key 走既有
SettingsService 槽位（與設定頁一致）；失敗訊息不外洩 key。
"""

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

from paper_kit.application.ports import EngineError, MISSING_API_KEY_MESSAGE
from paper_kit.domain.vision_translation import VisionTranslation

DEFAULT_VISION_BASE_URL = "https://api.siliconflow.com/v1/chat/completions"
DEFAULT_VISION_MODEL = "google/gemma-4-31B-it"
# 08-12 複雜圖品質實測定案：31B 是唯一可靠模型；12B 快且便宜當備援（26B 已移除）
VISION_BACKUPS: tuple[str, ...] = ("google/gemma-4-12B-it",)
# 時限分層：主 31B 40s（完整涵蓋實測區間 4.7s～33s），備援 8s（實測 4.7s）
VISION_TIMEOUTS: dict[str, int] = {"google/gemma-4-31B-it": 40}

_LANG_NAMES = {"zh-TW": "繁體中文", "zh": "繁體中文", "en": "英文"}


def _lang_name(target_lang: str) -> str:
    return _LANG_NAMES.get(target_lang, target_lang)


def build_vision_payload(model: str, image_path: str | Path, target_lang: str) -> dict:
    """組裝 chat/completions payload（純函式，測試直接斷言；同 paste-vision 格式）。"""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    prompt = (
        f"請把這張幻燈片的所有文字完整翻譯成{_lang_name(target_lang)}：逐字翻譯、"
        "保留專有名詞與數字、不要描述圖片、不要跳過任何文字。"
        "沒有文字的版面請回「（無文字）」。"
    )
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64}",
                            "detail": "auto",
                        },
                    },
                ],
            }
        ],
        "max_tokens": 2000,  # 一頁幻燈片譯文上限（與 paste-vision 一致）
        "temperature": 0.1,
    }


def _friendly_vision_error(detail: str) -> str:
    if "401" in detail or "Unauthorized" in detail or (
        "key" in detail.lower() and "invalid" in detail.lower()
    ):
        return "API key 無效或已過期（檢查設定頁的 SiliconFlow key）"
    return f"視覺翻譯失敗（所有模型無回應）：{detail[-200:]}"


class SiliconFlowVisionTranslator:
    """實作 VisionTranslatorPort：圖 → 譯文（SiliconFlow chat/completions 模型鏈）。"""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_VISION_MODEL,
        base_url: str = DEFAULT_VISION_BASE_URL,
    ):
        self._api_key = api_key
        self._base_url = base_url
        self._models = (model, *VISION_BACKUPS)  # 主→備援鏈

    def translate_image(
        self, image_path: str | Path, target_lang: str = "zh-TW"
    ) -> VisionTranslation:
        if not self._api_key:
            raise EngineError(MISSING_API_KEY_MESSAGE)
        last_error = ""
        for model in self._models:
            try:
                return self._call(model, image_path, target_lang)
            except Exception as exc:  # noqa: BLE001——模型鏈：任何失敗都換備援
                last_error = str(exc)
        raise EngineError(_friendly_vision_error(last_error))

    def _call(self, model: str, image_path: str | Path, target_lang: str) -> VisionTranslation:
        payload = build_vision_payload(model, image_path, target_lang)
        req = urllib.request.Request(
            self._base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=VISION_TIMEOUTS.get(model, 8)) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return VisionTranslation(
            text=text,
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
        )
