"""llm_probe 單元測試（架構健檢卡①：端點探測收斂單點）。

遷移自 test_settings_page 的 _probe_api/_fetch_models 測試＋test_pdf2zh_next_adapter
的 preflight UA 測試——探測知識（GET /models 驗 key／POST 驗模型／清單拉取／診斷
文案）統一在此測，UI 與 preflight 只測「呼叫方式」。
"""

import json
import threading
import urllib.request
import http.server

import pytest

from paper_kit.infrastructure import llm_probe
from paper_kit.infrastructure.llm_probe import (
    diagnose,
    list_models,
    probe_key,
    probe_model,
)


def _server(handler_cls):
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class _Base(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass


# ── probe_key（GET /models 驗 key 活性，零成本）──────────────────


def test_probe_key_returns_status():
    """GET {base_url}/models 驗證 key：200＝key 有效、401＝無效（沿用
    _probe_api 語意：壞 key 回 (401, 'key 驗證失敗')）。"""

    class Handler(_Base):
        def do_GET(self):
            auth = self.headers.get("Authorization", "")
            if auth == "Bearer good-key":
                body = b'{"object":"list","data":[]}'
                self.send_response(200)
            else:
                body = b'{"error":"invalid key"}'
                self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = _server(Handler)
    try:
        base = f"http://127.0.0.1:{server.server_port}/v1"
        code, body = probe_key(base, "good-key")
        assert code == 200, f"好 key 應 200，實際 {code} {body}"
        code, body = probe_key(base, "bad-key")
        assert code == 401, f"壞 key 應 401，實際 {code} {body}"
        assert "key 驗證失敗" in body, body
    finally:
        server.shutdown()


def test_probe_key_uses_browser_user_agent():
    """v0.1.7（2026-08-14 Groq 實測回歸）：urllib 預設 UA 被 Cloudflare 指紋
    封鎖（403 error 1010）——curl 200 但 urllib 誤擋。探測一律帶瀏覽器式 UA
    （設定頁「測試 API」與 preflight 共用——修復必須落在單點）。"""

    captured = {}

    class Handler(_Base):
        def do_GET(self):
            captured["ua"] = self.headers.get("User-Agent", "")
            body = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = _server(Handler)
    try:
        code, _ = probe_key(f"http://127.0.0.1:{server.server_port}/v1", "k")
        assert code == 200
        assert captured["ua"] and "Python-urllib" not in captured["ua"], (
            f"探測 UA 不得是 urllib 預設（被 Cloudflare 1010 封鎖）：{captured['ua']!r}"
        )
    finally:
        server.shutdown()


# ── probe_model（POST chat/completions 驗「模型可生成」，#78 盲區補驗）──


def test_probe_model_verifies_model_generation():
    """#78（2026-08-14 Gemini 404 實測教訓）：帶 model 時必須 POST
    /chat/completions 驗證「模型可生成」——GET /models 只驗 key 活性，
    不驗模型可用（gemini-3-pro-latest 在清單但 generateContent 404）。"""

    seen = {"post_paths": [], "post_bodies": []}

    class Handler(_Base):
        def do_GET(self):
            body = b'{"object":"list","data":[]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers["Content-Length"])
            seen["post_paths"].append(self.path)
            seen["post_bodies"].append(json.loads(self.rfile.read(length)))
            body = b'{"error":{"code":404,"message":"not found"}}'
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = _server(Handler)
    try:
        base = f"http://127.0.0.1:{server.server_port}/v1"
        code, _ = probe_model(base, "good-key", model="models/gemini-3.5-flash")
        assert code == 404, f"模型 404 應回 404（沿用現有通知分層），實際 {code}"
        assert seen["post_paths"] == ["/v1/chat/completions"], seen["post_paths"]
        body = seen["post_bodies"][0]
        assert body["model"] == "models/gemini-3.5-flash", body
        assert body["max_tokens"] == 1, f"應只驗生成 1 token（零成本），實際 {body}"
    finally:
        server.shutdown()


def test_probe_model_ping_payload_and_ua():
    """preflight 探測 payload 固定（model/max_tokens=1/ping）＋帶瀏覽器 UA。"""

    seen = {}

    class Handler(_Base):
        def do_POST(self):
            length = int(self.headers["Content-Length"])
            seen["body"] = json.loads(self.rfile.read(length))
            seen["ua"] = self.headers.get("User-Agent", "")
            body = b'{"choices":[{"message":{"content":"ok"}}]}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = _server(Handler)
    try:
        code, _ = probe_model(
            f"http://127.0.0.1:{server.server_port}/v1", "k", "m1", timeout=10
        )
        assert code == 200
        assert seen["body"] == {
            "model": "m1",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }, seen["body"]
        assert seen["ua"] and "Python-urllib" not in seen["ua"], seen["ua"]
    finally:
        server.shutdown()


def test_probe_model_network_error_returns_zero(monkeypatch):
    """連線失敗（urlopen 例外）→ (0, 錯誤訊息)（沿用 preflight 語意：0＝連線失敗）。"""

    def fake_urlopen(req, timeout=10):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    code, body = probe_model("https://example.com/v1", "k", "m")
    assert code == 0
    assert "connection refused" in body


# ── list_models（GET /models → id 清單，v0.1.3 模型挑選）──────────


def _list_server(payload: dict):
    class Handler(_Base):
        def do_GET(self):
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _server(Handler)


def test_list_models_parses_and_sorts():
    server = _list_server(
        {"data": [
            {"id": "nvidia/b-model"},
            {"id": "nvidia/a-model"},
            {"id": None},          # 缺 id → 跳過
            {"nope": 1},           # 非 dict 形狀 → 跳過
        ]}
    )
    try:
        models = list_models(f"http://127.0.0.1:{server.server_port}/v1", "nvapi-x")
        assert models == ["nvidia/a-model", "nvidia/b-model"], models
    finally:
        server.shutdown()


def test_list_models_failures_return_empty(monkeypatch):
    """失敗（401／例外）→ []（呼叫方以空清單提示「檢查 key／網路」）。"""

    def fake_urlopen(req, timeout=20):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert list_models("https://example.com/v1", "bad-key") == []

    def fake_urlopen2(req, timeout=20):
        raise urllib.error.URLError("timeout")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen2)
    assert list_models("https://example.com/v1", "k") == []


# ── diagnose（HTTP 碼→使用者診斷文案，單點）─────────────────────


def test_diagnose_messages():
    assert "key 無效" in diagnose(401, "{}")
    assert "key 無效" in diagnose(403, "{}")
    assert "模型不存在" in diagnose(404, "{}")
    assert "限流" in diagnose(429, "{}")
    assert "連線失敗" in diagnose(0, "boom")
    assert "500" in diagnose(500, "server error")
