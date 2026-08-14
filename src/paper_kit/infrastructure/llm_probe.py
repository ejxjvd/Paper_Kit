"""LLM 端點探測單點模組（架構健檢卡①：四份探測收斂於此）。

歷史：探測邏輯散在 app.py（_probe_api/_fetch_models——設定頁「測試 API」按鈕與
「載入模型清單」下拉）與 pdf2zh_next_adapter（preflight_openai——翻譯前防呆）
四份。v0.1.7 的瀏覽器 UA 修復只落在 preflight 一份上，設定頁「測試 API」對
Groq 仍會誤擋 403（Cloudflare 指紋封鎖 urllib 預設 UA）——收斂後 UA、payload、
診斷文案、時限全部單點，任一端改動即全端生效。llm_client.chat_completion 是
真實翻譯呼叫（非探測），不在此列。

語意（沿用既有行為，呼叫方觀察結果不變）：
- probe_key：GET {base_url}/models 驗 key 活性（零成本；模型清單未載入前先驗
  key）。200 → (200, "ok")；HTTPError → (code, "key 驗證失敗")；連線失敗 → (0, 訊息)。
- probe_model：POST {base_url}/chat/completions（max_tokens=1）驗「模型可生成」
  ——#78（2026-08-14 Gemini 404 教訓）：GET /models 只驗 key 不驗模型
  （gemini-3-pro-latest 在清單但 generateContent 404）。回 (status, body[:80])；
  0 ＝ 連線層失敗。
- list_models：GET /models → 排序後的 id 清單；失敗回 []（呼叫方以空清單
  提示檢查 key／網路）。v0.1.3：NVIDIA EOL 410 教訓（registry 寫死的 model
  會過期）——模型改由使用者即時拉取挑選。
- diagnose：HTTP 碼 → 使用者可操作診斷文案（設定頁通知／preflight 錯誤共用）。
"""

import json
import urllib.error
import urllib.request

# v0.1.7（2026-08-14 Groq 實測）：urllib 預設 UA（Python-urllib/3.x）被
# Cloudflare 指紋封鎖（403 error 1010）——curl 200 但探測誤擋。全部探測請求
# 帶瀏覽器式 UA；同場域（OpenRouter 等）亦受惠。
BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def _request(
    method: str,
    base_url: str,
    path: str,
    api_key: str,
    payload: dict | None = None,
) -> urllib.request.Request:
    """組探測請求：Authorization Bearer＋瀏覽器式 UA（payload 時加 Content-Type）。"""
    url = f"{base_url.rstrip('/')}/{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("User-Agent", BROWSER_USER_AGENT)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    return req


def probe_key(base_url: str, api_key: str, timeout: int = 10) -> tuple[int, str]:
    """GET {base_url}/models 驗 key 活性（零成本）。200 → (200, "ok")；
    HTTP 錯誤 → (code, "key 驗證失敗")；連線失敗 → (0, 錯誤訊息)。"""
    req = _request("GET", base_url, "models", api_key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(200)
    except urllib.error.HTTPError as e:
        e.read(200)
        return e.code, "key 驗證失敗"
    except Exception as e:  # 連線失敗／逾時（urlopen 拋 URLError 等）
        return 0, str(e)[:80]
    return 200, "ok"


def probe_model(
    base_url: str, api_key: str, model: str, timeout: int = 10
) -> tuple[int, str]:
    """POST /chat/completions（max_tokens=1 零成本 ping）驗「模型可生成」。

    #78（2026-08-14 實測教訓）：GET /models 只驗 key 活性不驗模型可用——
    gemini-3-pro-latest 在清單但 generateContent 404（使用者 3 任務全滅）。
    200＝可生成；401/403＝key 無效；404＝模型不存在；429＝限流；0＝連線失敗；
    #79（v0.1.8）：200 但 choices 為空（登錄未服務空殼）→ 590「模型未提供服務」。
    """
    payload = {
        "model": model,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "ping"}],
    }
    req = _request("POST", base_url, "chat/completions", api_key, payload)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(200).decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read(200).decode("utf-8", "replace")
        return e.code, body[:80]
    except Exception as e:  # 連線失敗／逾時
        return 0, str(e)[:80]
    # 空殼檢測（v0.1.8，#79 誤報根因）：HTTP 200 但 choices=null/[]（ERNIE×2/
    # Hy3/Intern-S1/GLM-4.7-Flash 實測）——不得當「可翻譯」放行（pdf2zh 在
    # choices[0] 對 NoneType 拋錯崩潰），也不得誤報 401。
    if status == 200 and _is_empty_shell(body):
        return 590, body[:80]
    return status, body[:80]


def list_models(base_url: str, api_key: str, timeout: int = 20) -> list[str]:
    """GET {base_url}/models → 模型 id 清單（排序；失敗回 []）。

    v0.1.3：設定頁「載入模型清單」——NVIDIA EOL 410 教訓（2026-08-14 使用者
    實測 deepseek-v4-flash 於 08-07 下線）：registry 寫死的 model 會過期，
    改由使用者即時拉取挑選。失敗（401／例外）→ []（呼叫方以空清單提示）。
    """
    req = _request("GET", base_url, "models", api_key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return []
    return sorted(
        m.get("id")
        for m in payload.get("data", [])
        if isinstance(m, dict) and m.get("id")
    )


def _is_empty_shell(body: str) -> bool:
    """HTTP 200 但 choices 為空（null／[]）＝「登錄但未提供服務」空殼模型。"""
    try:
        data = json.loads(body)
    except ValueError:
        return False
    return data.get("choices") in (None, [])


def diagnose(code: int, body: str) -> str:
    """HTTP 碼 → 使用者可操作診斷文案（設定頁「測試 API」通知／preflight 錯誤共用）。

    呼叫方自加前綴（引擎名／「上游 {code}：」語境）——文案本身不含重複的碼
    （500 與 0 分支除外，那兩者是 body 訊息的上下文）。
    """
    if code == 590:
        return (
            "模型未提供服務（HTTP 200 但 choices 為空）——"
            "該模型登錄但未開放，換模型或換引擎"
        )
    if code in (401, 403):
        return "API key 無效——請檢查是否複製完整"
    if code == 404:
        return (
            "模型不存在或不支援此用法——檢查模型 ID"
            "（設定頁「載入模型清單」挑選可生成模型）"
        )
    if code == 429:
        return "限流（免費額度/RPM 用完）——稍後重試或換引擎"
    if code == 0:
        return f"連線失敗：無法連到上游 API（{body}）"
    return f"上游 HTTP {code}：{body[:60]}"
