#!/usr/bin/env python3
"""Free-LLM-Collection 25 提供者端點活性探測（2026-08-13，票 47）。

對每個 OpenAI 相容端點 POST /chat/completions（假 key），記錄 HTTP 碼＋回應摘要。
判定基準：
- 401/403/429 = 端點存活、需認證（正常——拿到免費 key 即可用）
- 404/405    = 路徑可能錯誤（校正 base_url 後重探）
- 000/逾時    = 端點不通（連線失敗／掛掉）
- 200        = 意外開通（假 key 竟通過——安全警訊）

用法：python3 scripts/free_llm_probe.py [--models]   （--models 改用 GET /models）
"""
import json
import ssl
import sys
import urllib.error
import urllib.request

TIMEOUT = 10  # 秒

# base_url 清單（依 Free-LLM-Collection README 轉錄，2026-08-13）
ENDPOINTS = {
    "siliconflow(有key)": "https://api.siliconflow.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "internai": "https://chat.intern-ai.org.cn/api/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "cohere": "https://api.cohere.ai/compatibility/v1",
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "llm7": "https://api.llm7.io/v1",
    # #78（2026-08-14）：使用者管道全為國際站——.cn 改 .ai（國際站 key 跨站不互通）；
    # v0.1.7：Z.AI（智譜國際站）實測免費（glm-4.7-flash/glm-4.5-flash 小寫 ID）。
    "modelscope": "https://api-inference.modelscope.ai/v1",
    "zai": "https://api.z.ai/api/paas/v4",
    "kilo": "https://api.kilo.ai/api/gateway",
    "huggingface": "https://router.huggingface.co/v1",
    "groq": "https://api.groq.com/openai/v1",
    "celebras": "https://api.celebras.ai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "opencodezen": "https://opencode.ai/zen/v1",
    "dxnt": "https://www.dxnt.com/v1",
    "agens": "https://apihub.agnes-ai.com/v1",
    "cloudflare": "https://api.cloudflare.com/client/v4/accounts/<ACCT>/ai/v1",
    "sensenova": "https://token.sensenova.cn/v1",
    "g4f": "https://g4f.space/v1",
    "xfyun": "https://spark-api-open.xf-yun.com/v1",
    "inception": "https://api.inceptionlabs.ai/v1",
    "poolside": "https://inference.poolside.ai/v1",
    "chatanywhere(排除)": "https://api.chatanywhere.tech/v1",
    "xiaoen": "https://speed.toter.me/v1",
}

ctx = ssl.create_default_context()


def probe(name: str, base: str, use_models: bool) -> str:
    url = f"{base}/models" if use_models else f"{base}/chat/completions"
    payload = json.dumps({
        "model": "test",
        "messages": [{"role": "user", "content": "hi"}],
    }).encode()
    req = urllib.request.Request(url, method="GET" if use_models else "POST")
    # 2026-08-13 實測：groq/opencodezen/xiaoen 走 Cloudflare 機器人防護，
    # urllib 預設 UA 觸發 1010 → 一律帶瀏覽器 UA
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
    if not use_models:
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer test-probe-key")
        req.data = payload
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
            body = resp.read(200).decode("utf-8", "replace").replace("\n", " ")
            return f"{resp.status}  {body[:90]}"
    except urllib.error.HTTPError as e:
        body = e.read(200).decode("utf-8", "replace").replace("\n", " ")
        return f"{e.code}  {body[:90]}"
    except Exception as e:
        return f"FAIL {type(e).__name__}: {str(e)[:80]}"


def main() -> None:
    use_models = "--models" in sys.argv
    kind = "GET /models" if use_models else "POST /chat/completions (假 key)"
    print(f"== Free-LLM-Collection 端點探測：{kind} ==")
    results = []
    for name, base in ENDPOINTS.items():
        r = probe(name, base, use_models)
        results.append((name, r))
        print(f"{name:<22} {r}")
    print("\n== 摘要 ==")
    alive = [n for n, r in results if r.startswith(("401", "403", "429", "404", "405"))]
    dead = [n for n, r in results if r.startswith("FAIL")]
    open_ = [n for n, r in results if r.startswith("200")]
    print(f"端點存活(需認證/路徑待校正): {len(alive)} 個 — {', '.join(alive)}")
    if open_:
        print(f"!! 意外開通(假key通過): {', '.join(open_)}")
    if dead:
        print(f"連線失敗: {len(dead)} 個 — {', '.join(dead)}")


if __name__ == "__main__":
    main()
