"""票 14：SiliconFlow 視覺翻譯——單頁圖 → 繁中譯文（gemma 眼睛模型鏈）。

紅線（內部規範 §8 立法）：外部 API 一律 fallback 鏈＋逾時——主模型
google/gemma-4-31B-it（40s，複雜圖品質實測定案）＋備援 12B（8s），成功即停、
全掛才失敗。測試以 monkeypatch urlopen 為接縫（不碰真實 API）。
"""

import json
import urllib.error
from pathlib import Path

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.siliconflow_vision import (
    DEFAULT_VISION_BASE_URL,
    DEFAULT_VISION_MODEL,
    SiliconFlowVisionTranslator,
    VISION_BACKUPS,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32  # 假 PNG（測試只驗證 payload 組裝）


class FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeUrlopen:
    """依 model 分派：Exception → raise，dict → 回傳 payload。記錄收到的請求。"""

    def __init__(self, outcomes: dict[str, object]):
        self._outcomes = outcomes
        self.calls: list[dict] = []

    def __call__(self, req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        self.calls.append({"model": body["model"], "body": body, "url": req.full_url})
        outcome = self._outcomes.get(body["model"])
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


def make_image(tmp_path) -> Path:
    img = tmp_path / "slide1.png"
    img.write_bytes(PNG_BYTES)
    return img


def install(monkeypatch, outcomes: dict[str, object]) -> FakeUrlopen:
    fake = FakeUrlopen(outcomes)
    monkeypatch.setattr(
        "paper_kit.infrastructure.siliconflow_vision.urllib.request.urlopen", fake
    )
    return fake


def test_translate_image_sends_vision_payload_and_parses_tokens(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    fake = install(monkeypatch, {
        DEFAULT_VISION_MODEL: {
            "choices": [{"message": {"content": "這是譯文"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    })
    result = SiliconFlowVisionTranslator("SF-KEY").translate_image(img)
    assert result.text == "這是譯文"
    assert result.input_tokens == 100
    assert result.output_tokens == 50
    call = fake.calls[0]
    assert call["model"] == DEFAULT_VISION_MODEL
    assert call["url"] == DEFAULT_VISION_BASE_URL
    content = call["body"]["messages"][0]["content"]
    assert any(b["type"] == "image_url" and "base64" in b["image_url"]["url"] for b in content)


def test_translate_image_prompt_mentions_target_lang_and_slide(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    fake = install(monkeypatch, {
        DEFAULT_VISION_MODEL: {"choices": [{"message": {"content": "x"}}]},
    })
    SiliconFlowVisionTranslator("SF-KEY").translate_image(img, target_lang="en")
    text_block = fake.calls[0]["body"]["messages"][0]["content"][0]["text"]
    assert "English" in text_block or "英文" in text_block
    assert "幻燈片" in text_block


def test_translate_image_missing_key_friendly_error(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    fake = install(monkeypatch, {})
    with pytest.raises(EngineError, match="API key"):
        SiliconFlowVisionTranslator("").translate_image(img)
    assert fake.calls == []  # 缺 key 不發 HTTP


def test_translate_image_success_does_not_try_backup(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    fake = install(monkeypatch, {
        DEFAULT_VISION_MODEL: {"choices": [{"message": {"content": "ok"}}]},
    })
    SiliconFlowVisionTranslator("SF-KEY").translate_image(img)
    assert len(fake.calls) == 1  # 主成功即停，備援不呼叫


def test_translate_image_falls_back_to_backup_model(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    fake = install(monkeypatch, {
        DEFAULT_VISION_MODEL: urllib.error.HTTPError(
            DEFAULT_VISION_BASE_URL, 500, "Server Error", {}, None
        ),
        VISION_BACKUPS[0]: {"choices": [{"message": {"content": "備援譯文"}}]},
    })
    result = SiliconFlowVisionTranslator("SF-KEY").translate_image(img)
    assert result.text == "備援譯文"
    assert [c["model"] for c in fake.calls] == [DEFAULT_VISION_MODEL, VISION_BACKUPS[0]]


def test_translate_image_all_models_fail_gives_friendly_error(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    err401 = urllib.error.HTTPError(DEFAULT_VISION_BASE_URL, 401, "Unauthorized", {}, None)
    fake = install(monkeypatch, {DEFAULT_VISION_MODEL: err401, VISION_BACKUPS[0]: err401})
    with pytest.raises(EngineError, match="API key"):
        SiliconFlowVisionTranslator("SF-KEY").translate_image(img)
    assert len(fake.calls) == 2  # 主＋備援都試過


def test_translate_image_missing_usage_yields_zero_tokens(tmp_path, monkeypatch):
    img = make_image(tmp_path)
    install(monkeypatch, {
        DEFAULT_VISION_MODEL: {"choices": [{"message": {"content": "無 usage 欄位"}}]},
    })
    result = SiliconFlowVisionTranslator("SF-KEY").translate_image(img)
    assert result.input_tokens == 0
    assert result.output_tokens == 0
