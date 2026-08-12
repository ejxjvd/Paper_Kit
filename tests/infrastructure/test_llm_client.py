"""票 15：共用 LLM client——OpenAI 相容 chat/completions 單次呼叫。

urllib std lib（同 siliconflow_vision）；urlopen 可注入（FakeUrlopen 接縫）。
票 14 視覺 translator 已遷移共用（呼叫端組 payload，這裡只管傳輸＋解析）。
"""

import json

from paper_kit.infrastructure.llm_client import chat_completion


class FakeUrlopen:
    """記錄請求；回傳預設 choices/usage，可設例外。"""

    def __init__(self, content="translated text", error: Exception | None = None,
                 prompt_tokens=100, completion_tokens=50):
        self._content = content
        self._error = error
        self._prompt = prompt_tokens
        self._completion = completion_tokens
        self.calls: list[tuple[object, int]] = []  # (request, timeout)

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if self._error:
            raise self._error
        body = json.dumps({
            "choices": [{"message": {"content": self._content}}],
            "usage": {
                "prompt_tokens": self._prompt,
                "completion_tokens": self._completion,
            },
        }).encode("utf-8")

        class FakeResp:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return FakeResp()


def test_chat_completion_returns_text_and_tokens():
    fake = FakeUrlopen(content="譯文內容", prompt_tokens=7, completion_tokens=3)
    text, in_tokens, out_tokens = chat_completion(
        "https://api.example.com/v1/chat/completions",
        "KEY-123",
        {"model": "m", "messages": [{"role": "user", "content": "hi"}]},
        timeout=12,
        urlopen=fake,
    )
    assert text == "譯文內容"
    assert in_tokens == 7
    assert out_tokens == 3
    # Authorization 帶 key、逾時透傳
    req, timeout = fake.calls[0]
    assert req.headers["Authorization"] == "Bearer KEY-123"
    assert req.headers["Content-type"] == "application/json"  # urllib 慣例：capitalize
    assert timeout == 12


def test_chat_completion_missing_usage_returns_zero_tokens():
    class NoUsage(FakeUrlopen):
        def __call__(self, request, timeout):
            body = json.dumps({
                "choices": [{"message": {"content": "ok"}}],
            }).encode("utf-8")

            class FakeResp:
                def read(self):
                    return body

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    return False

            return FakeResp()

    text, in_tokens, out_tokens = chat_completion(
        "https://api.example.com/v1/chat/completions", "k",
        {"model": "m", "messages": []}, urlopen=NoUsage(),
    )
    assert text == "ok"
    assert in_tokens == 0  # 缺 usage → 0（成本記錄不炸）
    assert out_tokens == 0
