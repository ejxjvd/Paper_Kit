"""共用 LLM client（票 15）：OpenAI 相容 chat/completions 單次呼叫。

urllib std lib（同 paste-vision/siliconflow_vision 模式，無第三方依賴）；
urlopen 可注入（測試接縫，同 LibreOfficeConverter runner 模式）。
呼叫端負責組 payload（文字/視覺）與模型鏈；本模組只管傳輸＋解析 tokens。
"""

import json
import urllib.request

DEFAULT_TIMEOUT = 40


def chat_completion(
    base_url: str,
    api_key: str,
    payload: dict,
    timeout: int = DEFAULT_TIMEOUT,
    urlopen=None,
) -> tuple[str, int, int]:
    """單次 chat/completions 呼叫 → (文字, input_tokens, output_tokens)。

    缺 usage → tokens 0（成本記錄不炸，同票 14 教訓）；HTTP 錯誤向上拋
    （模型鏈/adapter 層負責 fallback 與友善錯誤）。
    """
    req = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    opener = urlopen or urllib.request.urlopen
    with opener(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return (
        text,
        int(usage.get("prompt_tokens", 0) or 0),
        int(usage.get("completion_tokens", 0) or 0),
    )
