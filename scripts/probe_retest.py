#!/usr/bin/env python3
"""2026-08-13 探測補測：UA 重探 Cloudflare 防護端點＋nvidia 路徑校正＋g4f 複測。"""
import json
import ssl
import urllib.error
import urllib.request

ctx = ssl.create_default_context()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def post(name: str, base: str, timeout: int = 15) -> None:
    url = base + "/chat/completions"
    payload = json.dumps({"model": "test", "messages": [{"role": "user", "content": "hi"}]}).encode()
    req = urllib.request.Request(url, method="POST", data=payload)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer test-probe-key")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            print(f"{name:<14} {resp.status}  {resp.read(150).decode('utf-8', 'replace')[:100]}")
    except urllib.error.HTTPError as e:
        print(f"{name:<14} {e.code}  {e.read(150).decode('utf-8', 'replace')[:100]}")
    except Exception as e:
        print(f"{name:<14} FAIL {type(e).__name__}: {str(e)[:70]}")


def get(name: str, url: str, timeout: int = 15) -> None:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", "Bearer test-probe-key")
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = resp.read(300).decode("utf-8", "replace")
            print(f"{name:<14} {resp.status}  {body[:130]}")
    except urllib.error.HTTPError as e:
        print(f"{name:<14} {e.code}  {e.read(200).decode('utf-8', 'replace')[:100]}")
    except Exception as e:
        print(f"{name:<14} FAIL {type(e).__name__}: {str(e)[:70]}")


print("== UA 重探（瀏覽器 UA 對抗 Cloudflare 1010）==")
post("groq", "https://api.groq.com/openai/v1")
post("opencodezen", "https://opencode.ai/zen/v1")
post("xiaoen", "https://speed.toter.me/v1")
post("g4f", "https://g4f.space/v1", timeout=25)
print("== nvidia 路徑校正 ==")
get("nvidia-models", "https://integrate.api.nvidia.com/v1/models")
get("nvidia-models2", "https://api.nvcf.nvidia.com/v1/models")
