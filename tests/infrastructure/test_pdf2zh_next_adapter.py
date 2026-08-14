"""Pdf2zhNextAdapter 單元測試（FakeRunner 注入，不碰真實引擎）。

POC 教訓入測：.com 國際站端點預設、key 走 CLI 旗標（不吃 process env）、
50507 暫時性錯誤要 retry、錯誤要轉成友善訊息（不透傳 traceback）。
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.pdf2zh_next_adapter import (
    DEFAULT_BASE_URL,
    EngineConfig,
    Pdf2zhNextAdapter,
    build_command,
    parse_output,
)


def test_uv_missing_gives_friendly_error(monkeypatch, tmp_path):
    """2026-08-12 UI 實測：環境缺 uv 時使用者看到「發生未預期錯誤：No such file
    or directory: 'uv'」——應是「可操作」訊息（安裝指令）而非裸 Errno。

    檢查在真實 runner（_default_runner）層——FakeRunner 注入的測試不受影響。
    """
    monkeypatch.setattr("paper_kit.infrastructure.cli_adapter_base.shutil.which",
                        lambda _: None)
    # 家目錄也隔離（回退檢查 ~/.local/bin/uv 不存在）→ 仍是安裝指引
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    # v0.1.1：自動安裝也失敗（離線模擬）→ 可操作錯誤（不觸網）
    monkeypatch.setattr("paper_kit.infrastructure.cli_adapter_base.resolve_uv",
                        lambda timeout=60: None)
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))  # 真 runner，不注入
    with pytest.raises(EngineError, match="uv"):
        adapter.translate(make_job())


def test_uv_falls_back_to_home_local_bin(monkeypatch, tmp_path):
    """2026-08-12 實機 e2e：`wsl -e bash script.sh`（非登入 shell）PATH 缺
    ~/.local/bin → which("uv") 找不到 → 翻譯 1 秒 FAILED（「系統缺少 uv 工具」）。
    修正：which 找不到時回退 uv 官方安裝位置 ~/.local/bin/uv（Windows 為
    uv.exe）——存在就改用絕對路徑執行，任何啟動方式（systemd/手動/無頭）
    都免疫；兩者皆無才給安裝指引。檢查在真實 runner 層。
    """
    from paper_kit.infrastructure.uv_bootstrap import uv_executable_name

    (tmp_path / ".local" / "bin").mkdir(parents=True)
    (tmp_path / ".local" / "bin" / uv_executable_name()).touch()
    monkeypatch.setattr("paper_kit.infrastructure.cli_adapter_base.shutil.which",
                        lambda _: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    captured: dict = {}

    class FakeProc:  # 流式介面（#73）：stdout 迭代逐行＋poll/wait，不再用 communicate
        returncode = 0

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs
            self.stdout = _LineStream(LOG)

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(
        "paper_kit.infrastructure.cli_adapter_base.subprocess.Popen", FakeProc
    )
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))  # 真 runner，不注入
    result = adapter.translate(make_job())
    # 用的絕對路徑 uv，不是裸 "uv"（PATH 找不到時裸名直接 Errno）
    assert captured["cmd"][0] == str(tmp_path / ".local" / "bin" / uv_executable_name())
    # #76：PYTHONUNBUFFERED=1（pdf2zh tqdm 非 TTY 不 flush → 活性信號斷 → 誤殺
    # 的修復契約）；#23：COLUMNS=1000（rich 寬 console token 行不折）
    assert captured["kwargs"]["env"]["PYTHONUNBUFFERED"] == "1"
    assert captured["kwargs"]["env"]["COLUMNS"] == "1000"
    assert isinstance(result, JobResult)


def make_job(**kw) -> TranslationJob:
    base = dict(
        job_id="job-1",
        source_path="/in/paper.pdf",
        target_lang="zh-TW",
        pages="1-2",
        glossary_files=["/gl/a.csv"],
    )
    base.update(kw)
    return TranslationJob(**base)


class FakeRunner:
    """注入的執行器：依序回傳 (rc, output) 或丟例外。"""

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, cmd, timeout=None, cwd=None):
        self.calls.append((cmd, timeout, cwd))
        r = self.results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


LOG = (
    "INFO Mono PDF: /out/paper.zh.mono.pdf\n"
    "INFO Dual PDF: /out/paper.zh.dual.pdf\n"
    "Total Token Usage: Total 9346, Prompt 7127, Cache Hit Prompt 1664, Completion 2219\n"
)


class _LineStream:
    """流式 runner 的 stdout 替身：逐行 yield 文字，最後 StopIteration＝EOF。"""

    def __init__(self, text: str):
        self._lines = iter(text.splitlines(keepends=True))

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self._lines)


# ── build_command：旗標組裝 ──────────────────────────────


def test_build_command_siliconflow_flags():
    cfg = EngineConfig(api_key="KEY")
    cmd = build_command(make_job(), cfg)
    assert cmd[0:4] == ["uv", "tool", "run", "pdf2zh_next"]
    assert "/in/paper.pdf" in cmd
    assert "--siliconflow" in cmd
    assert cmd[cmd.index("--siliconflow-api-key") + 1] == "KEY"
    assert cmd[cmd.index("--siliconflow-base-url") + 1] == DEFAULT_BASE_URL
    assert cmd[cmd.index("--siliconflow-model") + 1] == "google/gemma-4-31B-it"
    assert cmd[cmd.index("--pages") + 1] == "1-2"
    assert "--only-include-translated-page" in cmd
    assert cmd[cmd.index("--lang-out") + 1] == "zh-TW"


def test_build_command_default_base_url_is_international_com():
    cfg = EngineConfig(api_key="KEY")
    cmd = build_command(make_job(), cfg)
    assert "--siliconflow-base-url" in cmd
    assert "https://api.siliconflow.com/v1" in cmd
    assert ".cn" not in cmd  # POC 教訓：中國站端點會 401


def test_build_command_deepseek_uses_deepseek_flags():
    cfg = EngineConfig(provider="deepseek", api_key="DSKEY")
    cmd = build_command(make_job(), cfg)
    assert "--deepseek" in cmd
    assert cmd[cmd.index("--deepseek-api-key") + 1] == "DSKEY"
    assert "--siliconflow" not in cmd


def test_build_command_openai_provider_uses_openai_flags():
    """免費 LLM 接入（2026-08-13）：OpenAI 相容免費端點（Free-LLM-Collection）
    走 --openai 三旗標——base-url/model/api-key 全由 spec 提供。"""
    cfg = EngineConfig(
        provider="openai",
        api_key="FREEKEY",
        model="openai/gpt-oss-20b:free",
        base_url="https://openrouter.ai/api/v1",
    )
    cmd = build_command(make_job(), cfg)
    assert "--openai" in cmd
    assert cmd[cmd.index("--openai-base-url") + 1] == "https://openrouter.ai/api/v1"
    assert cmd[cmd.index("--openai-model") + 1] == "openai/gpt-oss-20b:free"
    assert cmd[cmd.index("--openai-api-key") + 1] == "FREEKEY"
    assert "--siliconflow" not in cmd and "--deepseek" not in cmd


def test_build_command_no_pages_omits_flag():
    cmd = build_command(make_job(pages=None), EngineConfig(api_key="KEY"))
    assert "--pages" not in cmd


def test_build_command_only_selected_pages_off_omits_flag():
    """#85：仅选中页面 toggle OFF → 不送 --only-include-translated-page
    （引擎預設輸出全部頁面、未選頁原樣保留；ON＝現行行為只輸出翻譯頁）。"""
    cmd = build_command(
        make_job(only_selected_pages=False), EngineConfig(api_key="KEY")
    )
    assert "--only-include-translated-page" not in cmd


def test_build_command_glossaries_comma_joined_with_auto_extract_off():
    cmd = build_command(
        make_job(glossary_files=["/gl/a.csv", "/gl/b.csv"]),
        EngineConfig(api_key="KEY"),
    )
    assert cmd[cmd.index("--glossaries") + 1] == "/gl/a.csv,/gl/b.csv"
    assert "--no-auto-extract-glossary" in cmd


def test_build_command_no_glossary_omits_flags():
    cmd = build_command(make_job(glossary_files=[]), EngineConfig(api_key="KEY"))
    assert "--glossaries" not in cmd
    assert "--no-auto-extract-glossary" not in cmd


def test_build_command_term_siliconflow_when_auto_extract_on():
    """票 05＋Bug 1：自動術語提取開關 → term 引擎旗標齊全（key/model/base-url）。

    真因（2026-08-13）：adapter 只送 --term-siliconflow、漏送 --term-siliconflow-api-key，
    引擎 term settings validate 丟「SiliconFlow API key is required」→ UI 4 筆任務全滅。
    """
    cfg = EngineConfig(api_key="KEY")
    cmd = build_command(make_job(auto_extract=True), cfg)
    assert "--term-siliconflow" in cmd
    assert cmd[cmd.index("--term-siliconflow-api-key") + 1] == "KEY"
    assert cmd[cmd.index("--term-siliconflow-model") + 1] == "google/gemma-4-31B-it"
    assert cmd[cmd.index("--term-siliconflow-base-url") + 1] == DEFAULT_BASE_URL


def test_build_command_term_siliconflow_absent_by_default():
    cmd = build_command(make_job(), EngineConfig(api_key="KEY"))
    assert "--term-siliconflow" not in cmd


def test_build_command_term_api_key_independent():
    """#84：術語提取 key 獨立化——EngineConfig.term_api_key 設定時
    --term-siliconflow-api-key 用獨立 key（不再複用主引擎 key）。"""
    cfg = EngineConfig(api_key="MAIN-KEY", term_api_key="TERM-KEY")
    cmd = build_command(make_job(auto_extract=True), cfg)
    assert cmd[cmd.index("--term-siliconflow-api-key") + 1] == "TERM-KEY"
    # 主引擎旗標不受影響（各用各的 key）
    assert cmd[cmd.index("--siliconflow-api-key") + 1] == "MAIN-KEY"


def test_build_command_term_api_key_blank_falls_back_to_main():
    """#84：term_api_key 未設定（預設空）→ 沿用主 key（舊行為不變，向後相容）。"""
    cfg = EngineConfig(api_key="MAIN-KEY")  # term_api_key 預設 ""
    cmd = build_command(make_job(auto_extract=True), cfg)
    assert cmd[cmd.index("--term-siliconflow-api-key") + 1] == "MAIN-KEY"


def test_build_command_deepseek_auto_extract_no_term_flags():
    """#83（紅）：deepseek provider＋auto_extract → 不得送任何 --term-* 旗標。

    真因鏈（2026-08-13 實測）：term 引擎＝SiliconFlow，收到 deepseek key →
    401「Token is invalid」（code 30014）→ 引擎 rc=0 靜默吞掉子進程失敗 → 零
    產出 → parse_output 假路徑 COMPLETED → 下載 404「失敗 - 沒有檔案」。
    引擎源碼實證：無 --term-* 旗標 → term_extraction_engine_settings=None →
    get_term_translator=None → 提取整個跳過（不需 key、不呼叫、不上雲）。

    敏感紅線回歸：sensitive_ok=True 只有 deepseek（票 10）→ 機密內容
    不得送 SiliconFlow 雲端做術語提取——本測試同時守住這條。
    """
    cfg = EngineConfig(provider="deepseek", api_key="DSKEY")
    cmd = build_command(make_job(auto_extract=True), cfg)
    assert "--deepseek" in cmd
    assert not any(flag.startswith("--term-") for flag in cmd), cmd


def test_build_command_glossary_with_auto_extract_keeps_extraction_enabled():
    """票 13 統一：UI 兩開關可同開 → 有術語表＋自動提取時不禁用提取。"""
    cmd = build_command(
        make_job(glossary_files=["/gl/a.csv"], auto_extract=True),
        EngineConfig(api_key="KEY"),
    )
    assert "--glossaries" in cmd
    assert "--no-auto-extract-glossary" not in cmd


# ── translate：成功解析 ──────────────────────────────────


def test_free_engine_translate_without_key_skips_key_guard():
    """免費引擎（requires_key=False、無 key）translate 不 raise「尚未設定 key」。

    2026-08-13 使用者實測回報：siliconflowfree/google/bing 三支免費引擎全被
    CliAdapterBase.translate 的 key 守衛誤擋（「錯誤：尚未設定 API key」）——
    免費引擎送 pdf2zh 的指令根本不含 key 旗標，守衛應只對需要 key 的引擎檢查。
    """
    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="siliconflowfree", requires_key=False, api_key=""),
        runner=FakeRunner((0, LOG)),
    )
    result = adapter.translate(make_job())
    assert result.mono_path == "/out/paper.zh.mono.pdf"
    assert len(adapter._runner.calls) == 1, "免費引擎無 key 也應真正執行引擎"


def test_key_required_engine_without_key_raises_missing_key():
    """需要 key 的引擎無 key → 維持 raise（守衛不移除，只對免費引擎放行）。"""
    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="siliconflow", requires_key=True, api_key=""),
        runner=FakeRunner((0, LOG)),
    )
    with pytest.raises(EngineError, match="尚未設定.*key"):
        adapter.translate(make_job())
    assert len(adapter._runner.calls) == 0, "缺 key 時不得執行引擎"


def test_translate_success_parses_outputs_and_tokens():
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=FakeRunner((0, LOG)))
    result = adapter.translate(make_job())
    assert isinstance(result, JobResult)
    assert result.mono_path == "/out/paper.zh.mono.pdf"
    assert result.dual_path == "/out/paper.zh.dual.pdf"
    assert result.input_tokens == 7127
    assert result.output_tokens == 2219


def test_translate_no_path_lines_raises_engine_error():
    """#83（紅→綠主角）：log 無 MonoPDF/DualPDF 行＝引擎零產出（子進程失敗被
    rc=0 靜默吞掉，2026-08-13 實測 401 場景）→ 不得靜默 fallback 慣例檔名製造
    ghost COMPLETED（下載「失敗 - 沒有檔案」+ .htm 的根因層二）→ EngineError。
    """
    adapter = Pdf2zhNextAdapter(
        EngineConfig(api_key="KEY"),
        runner=FakeRunner((0, "Total Token Usage: Total 1, Prompt 1, Cache Hit Prompt 0, Completion 1\n")),
    )
    with pytest.raises(EngineError, match="產出"):
        adapter.translate(make_job())


def test_parse_output_no_path_lines_raises_engine_error():
    """#83：parse_output 直接層——任何產出宣告都沒有 → 拒絕製造假路徑。"""
    out = "Total Token Usage: Total 1, Prompt 1, Cache Hit Prompt 0, Completion 1\n"
    with pytest.raises(EngineError, match="產出"):
        parse_output(out, make_job())


def test_parse_output_no_path_diagnoses_404():
    """#78（2026-08-14 Gemini 404 實測教訓）：pdf2zh 對上游 404 吞錯、rc=0 退出
    ——假成功訊息必須帶出引擎 log 的真實 HTTP 錯誤（gemini-3-pro-latest 案例）。"""
    out = (
        "ERROR pdf2zh_next.high_level: Subprocess initialization error: "
        "Error code: 404 - [{'error': {'code': 404, 'message': "
        "'not found for API version v1main..."
    )
    with pytest.raises(EngineError, match="上游 404"):
        parse_output(out, make_job())


def test_parse_output_no_path_diagnoses_429():
    """#78：429 限流（免費層 RPM/配額）→ 錯誤訊息帶「限流」原因。"""
    out = "ERROR: Too Many Requests (429)"
    with pytest.raises(EngineError, match="429"):
        parse_output(out, make_job())


def test_parse_output_no_path_diagnoses_auth_failed():
    """#78（2026-08-14 ModelScope 實測）：401 訊息「Authentication failed」
    不含 401 字樣——regex 補 authentication 才抓得到（跨站 key 案例）。"""
    out = ("ERROR pdf2zh_next.high_level: Authentication failed, "
           "please make sure that a valid ModelScope token is supplied.")
    with pytest.raises(EngineError, match="401"):
        parse_output(out, make_job())


def test_parse_output_missing_mono_fallback_uses_target_lang():
    """檔名小瑕疵（frontier）：log 只有 DualPDF 行 → mono fallback 檔名必須用
    實際 target_lang（zh-TW）——舊行為硬編碼 .zh.mono.pdf 與引擎產出
    zh-TW.mono.pdf 不符 → fallback 路徑不存在 → 下載失敗。"""
    out = "INFO Dual PDF: /out/paper.zh-TW.dual.pdf\n"
    result = parse_output(out, make_job())
    assert result.mono_path == "/in/paper.zh-TW.mono.pdf", f"實際 {result.mono_path}"
    assert result.dual_path == "/out/paper.zh-TW.dual.pdf"  # 既有行不受影響


# ── translate：preflight 預檢（#78 假成功杜絕第三層）──────────────────


def test_translate_preflight_401_blocks_before_engine(monkeypatch):
    """#78（2026-08-14）：翻譯前先 POST chat/completions 驗證 key＋模型——
    401（ModelScope 跨站 key／Gemini 壞 key）→ 直接 EngineError 帶診斷、
    引擎根本不上（FakeRunner 不被呼叫）——吞錯 rc=0 假成功從根杜絕。"""

    import paper_kit.infrastructure.pdf2zh_next_adapter as mod

    runner = FakeRunner((0, LOG))
    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="openai", api_key="bad-key", base_url="https://x/v1", model="m1"),
        runner=runner,
    )
    monkeypatch.setattr(mod, "preflight_openai", lambda *a, **k: (401, "Authentication failed"))
    with pytest.raises(EngineError, match="key 無效"):
        adapter.translate(make_job())
    assert runner.calls == [], "preflight 失敗不得啟動引擎子進程"


def test_translate_preflight_404_blocks_with_model_hint(monkeypatch):
    """preflight 404（模型不存在，Gemini gemini-3-pro-latest 案例）→ 診斷訊息帶
    「模型」提示。"""

    import paper_kit.infrastructure.pdf2zh_next_adapter as mod

    runner = FakeRunner((0, LOG))
    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="openai", api_key="k", base_url="https://x/v1", model="bad-model"),
        runner=runner,
    )
    monkeypatch.setattr(mod, "preflight_openai", lambda *a, **k: (404, "not found"))
    with pytest.raises(EngineError, match="模型不存在"):
        adapter.translate(make_job())
    assert runner.calls == []


def test_translate_preflight_ok_continues_to_engine(monkeypatch):
    """preflight 200 → 照常翻譯（FakeRunner 被呼叫、正常產出）。"""

    import paper_kit.infrastructure.pdf2zh_next_adapter as mod

    runner = FakeRunner((0, LOG))
    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="openai", api_key="good", base_url="https://x/v1", model="m1"),
        runner=runner,
    )
    monkeypatch.setattr(mod, "preflight_openai", lambda *a, **k: (200, "ok"))
    result = adapter.translate(make_job())
    assert runner.calls, "preflight 通過後應啟動引擎"
    assert result.mono_path == "/out/paper.zh.mono.pdf"


def test_translate_skips_preflight_when_no_key_required():
    """needs_key=False（零 key 免費引擎：siliconflowfree/google/bing）→
    不 preflight（無 key 可驗）——runner 照常被呼叫。"""

    runner = FakeRunner((0, LOG))
    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="openai", api_key="", requires_key=False, base_url="https://x/v1", model="m1"),
        runner=runner,
    )
    result = adapter.translate(make_job())
    assert runner.calls, "無 key 免費引擎不應被 preflight 擋住"
    assert result.mono_path == "/out/paper.zh.mono.pdf"


def test_preflight_sends_browser_user_agent(monkeypatch):
    """v0.1.7（2026-08-14 Groq 實測回歸）：urllib 預設 UA（Python-urllib/3.x）
    被 Groq 的 Cloudflare 指紋封鎖（403 error 1010）——curl 200 但 preflight 誤擋
    真翻譯。preflight 必須帶瀏覽器式 UA。"""
    import urllib.request

    import paper_kit.infrastructure.pdf2zh_next_adapter as mod

    captured = {}

    class FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            return b"{}"

    def fake_urlopen(req, timeout=10):
        captured["ua"] = req.get_header("User-agent")
        return FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    code, _ = mod.preflight_openai("https://api.groq.com/openai/v1", "k", "m")
    assert code == 200
    assert captured["ua"] and "Python-urllib" not in captured["ua"], (
        f"preflight UA 不得是 urllib 預設（被 Cloudflare 1010 封鎖）：{captured['ua']!r}"
    )


# ── translate：錯誤對映 ──────────────────────────────────


def test_401_maps_to_friendly_key_message():
    adapter = Pdf2zhNextAdapter(
        EngineConfig(api_key="BAD"), runner=FakeRunner((1, "AuthenticationError 401 Api key is invalid\n"))
    )
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(make_job())


def test_glossary_csv_error_maps_to_friendly_message():
    adapter = Pdf2zhNextAdapter(
        EngineConfig(api_key="KEY"),
        runner=FakeRunner((1, "ValueError: CSV must contain 'source' and 'target' columns\n")),
    )
    with pytest.raises(EngineError, match="術語表"):
        adapter.translate(make_job())


def test_generic_error_uses_excerpt_not_full_traceback():
    traceback = "Traceback (most recent call last):\n  File \"x.py\", line 1\nRuntimeError: boom\n"
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=FakeRunner((1, traceback)))
    with pytest.raises(EngineError) as exc:
        adapter.translate(make_job())
    assert "boom" in str(exc.value)
    assert "Traceback" not in str(exc.value)


def test_engine_output_leaking_api_key_is_redacted_in_error_and_log(tmp_path):
    """票 09 紅線（standards review 硬問題）：引擎失敗輸出尾段回顯 key →
    EngineError 訊息與 log 都不許含 key（job.error 來自 str(e)，再進 SQLite／卡片／log）。"""
    import json
    import logging

    from paper_kit.infrastructure.logging_setup import setup_logging

    log_path = setup_logging(tmp_path)
    try:
        output = "RuntimeError: boom\n--siliconflow-api-key sk-TOPSECRET\n"  # 末 200 字含 key
        adapter = Pdf2zhNextAdapter(
            EngineConfig(api_key="sk-TOPSECRET"),
            runner=FakeRunner((1, output)),
        )
        with pytest.raises(EngineError) as exc:
            adapter.translate(make_job())
        assert "sk-TOPSECRET" not in str(exc.value)

        text = log_path.read_text(encoding="utf-8")
        assert "sk-TOPSECRET" not in text, "log 不得含 API key"
        last = json.loads(text.strip().splitlines()[-1])
        assert "***" in last["error"], "error 欄位要顯示遮罩後訊息"
    finally:
        logging.getLogger("paper_kit").handlers.clear()


# ── translate：retry（50507 暫時性）與逾時 ────────────────


def test_transient_50507_retries_then_succeeds():
    fail_log = "openai.InternalServerError: 50507 Request failed: Unknown error\n"
    runner = FakeRunner((1, fail_log), (1, fail_log), (0, LOG))
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    result = adapter.translate(make_job())
    assert len(runner.calls) == 3
    assert result.mono_path == "/out/paper.zh.mono.pdf"


def test_non_transient_error_no_retry():
    runner = FakeRunner((1, "AuthenticationError 401\n"))
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    with pytest.raises(EngineError):
        adapter.translate(make_job())
    assert len(runner.calls) == 1


def test_timeout_maps_to_timeout_message():
    runner = FakeRunner(subprocess.TimeoutExpired("pdf2zh_next", 600))
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    with pytest.raises(EngineError, match="逾時"):
        adapter.translate(make_job())


def test_inactivity_timeout_raises_when_no_output(monkeypatch, tmp_path):
    """#73（CH4 真因）：引擎還活著但超過 inactivity_seconds 無輸出行 → 逾時。

    舊機制死守 600s 總牆鐘——CH4 正在逐段翻譯（SiliconFlow 每段 API 呼叫間隔
    5–20s，段落 warning 行＝活性信號），卻被牆鐘硬殺。新機制改以「最後一行的
    時間」判 hang：有輸出就續命，只剩真的卡住才逾時。
    """
    from paper_kit.infrastructure.uv_bootstrap import uv_executable_name

    (tmp_path / ".local" / "bin").mkdir(parents=True)
    (tmp_path / ".local" / "bin" / uv_executable_name()).touch()
    monkeypatch.setattr("paper_kit.infrastructure.cli_adapter_base.shutil.which",
                        lambda _: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    class NeverStream:
        """永不產出行（模擬 rich bar 佔住 stdout、\n 行杳無蹤影的卡住段）。"""

        def __iter__(self):
            return self

        def __next__(self):
            time.sleep(3600)

    class SilentProc:
        returncode = 0
        pid = 99999  # kill_tree 會 killpg → ProcessLookupError → 放行
        args = ["taskkill", "/T", "/F", "/PID", "99999"]  # subprocess.run 收尾組 CompletedProcess

        def __init__(self, cmd, **kwargs):
            self.stdout = NeverStream()

        def poll(self):
            return None  # 一直活著（不退出也不輸出）

        def wait(self):
            return 0

        # Windows 上 _kill_tree 走 taskkill：subprocess.run 內部 `with Popen(...)`
        # （Popen 自 3.9 是 context manager）——fake 要補齊介面（Linux 走
        # killpg 不觸發，CI win-x64 實測 TypeError）
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        # subprocess.run 成功路徑會 communicate()、任何例外路徑都會 kill()——
        # 兩者 fake 都要有（taskkill 已「跑完」，返回值無關緊要）
        def communicate(self, input=None, timeout=None):
            return (None, None)

        def kill(self):
            pass

    monkeypatch.setattr(
        "paper_kit.infrastructure.cli_adapter_base.subprocess.Popen", SilentProc
    )
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY", inactivity_seconds=1))
    with pytest.raises(EngineError, match="逾時"):
        adapter.translate(make_job())


def test_translate_runs_engine_in_job_source_directory():
    """babeldoc 輸出走子程序 CWD → cwd 必須是任務資料夾，產出才落在該處（票 03 實測教訓）。"""
    runner = FakeRunner((0, LOG))
    job = make_job()  # source_path = /in/paper.pdf
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    adapter.translate(job)
    _, _, cwd = runner.calls[0]
    # Path 比較：Windows 上 Path("/in").parent str 為 "\\in"（CI win-x64 實測）
    assert Path(cwd) == Path("/in"), f"引擎要以任務資料夾為 cwd（實得 {cwd!r}）"


# ── 票 08：取消 ─────────────────────────────────────────────


def test_translate_after_cancel_raises_without_running_engine():
    """取消後 translate 一律拒絕，不再啟動引擎。"""
    def runner(cmd, timeout=None, cwd=None):
        raise AssertionError("取消後不該再跑引擎")

    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    adapter.cancel()
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(make_job())


def test_cancel_kills_running_subprocess(monkeypatch, tmp_path):
    """真實子程序：cancel() 要真的殺掉在跑的引擎（Popen handle 掛回 adapter）。"""
    import threading
    import time

    # 讓引擎命令變成長睡（build_command 換成假指令，保持預設 Popen runner）
    # Windows 的 timeout.exe 遇 stdin 重定向立刻退出（Input redirection is not
    # supported）→ 換 ping -n 30（~30s，可重定向）；POSIX 用 sleep
    sleep_cmd = (
        ["ping", "-n", "30", "127.0.0.1"] if sys.platform == "win32" else ["sleep", "30"]
    )
    monkeypatch.setattr(
        "paper_kit.infrastructure.pdf2zh_next_adapter.build_command",
        lambda job, cfg: sleep_cmd,
    )
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))  # 預設 runner（真 Popen）
    # source_path 用 tmp_path：Windows 上 "/tmp/..." 當 cwd 會 WinError 267
    job = make_job(source_path=str(tmp_path / "slow.pdf"))
    errors = []

    def run():
        try:
            adapter.translate(job)
        except EngineError as exc:
            errors.append(str(exc))

    t = threading.Thread(target=run, daemon=True)
    t0 = time.monotonic()
    t.start()
    time.sleep(0.3)  # 等子程序跑起來
    adapter.cancel()
    t.join(timeout=10)
    elapsed = time.monotonic() - t0

    assert t.is_alive() is False, "cancel 後引擎要立刻結束（不會等完 sleep 30）"
    assert elapsed < 10
    assert errors == ["已取消"]


@pytest.mark.skipif(sys.platform == "win32", reason="killpg 是 POSIX 機制")
def test_kill_tree_kills_grandchildren():
    """樹殺回歸（review 硬問題）：只殺中介父程序，孫程序照跑＝管道卡死。

    父（python -c 扮演 uv 中介）→ 孫（sleep 30 扮演真正翻譯程序）。
    舊行為 proc.kill() 只殺父 → pgrep 還找得到孫；_kill_tree 後一棵不剩。
    """
    import time

    from paper_kit.infrastructure.pdf2zh_next_adapter import _kill_tree

    code = (
        "import subprocess, time;"
        "subprocess.Popen(['sleep', '30']);"
        "time.sleep(30)"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # 比照 adapter 的 runner
    )
    time.sleep(0.5)  # 等孫程序誕生
    _kill_tree(proc)
    deadline = time.monotonic() + 2
    while proc.poll() is None and time.monotonic() < deadline:
        time.sleep(0.05)  # SIGKILL 傳遞有微小延遲，輪詢等 reaped
    assert proc.poll() is not None, "父（中介）必須已死"
    time.sleep(0.2)
    found = subprocess.run(["pgrep", "-f", "sleep 30"], capture_output=True, text=True)
    assert found.returncode != 0, f"孫程序還活著（只殺父的舊行為）：{found.stdout.strip()}"

def test_timeout_log_error_chain_redacts_api_key(tmp_path):
    """#83 安全（紅）：TimeoutExpired 的 cmd 含明文 key → 逾時 log 的
    error_chain 必須 redact（實測：~/.paper_kit/logs 曾寫入明文 SF key）。"""
    import logging

    from paper_kit.infrastructure.logging_setup import setup_logging

    log_path = setup_logging(tmp_path)
    try:
        cmd = build_command(
            make_job(auto_extract=True),
            EngineConfig(provider="deepseek", api_key="sk-TOPSECRET"),
        )
        runner = FakeRunner(subprocess.TimeoutExpired(cmd, 60))
        adapter = Pdf2zhNextAdapter(
            EngineConfig(provider="deepseek", api_key="sk-TOPSECRET"),
            runner=runner,
        )
        with pytest.raises(EngineError, match="逾時"):
            adapter.translate(make_job(auto_extract=True))
        text = log_path.read_text(encoding="utf-8")
        assert "sk-TOPSECRET" not in text, "逾時 log 的 error_chain 不得含明文 key"
    finally:
        logging.getLogger("paper_kit").handlers.clear()


def test_build_command_nim_throttling_flags_when_spec_configured():
    """v0.1.3（NIM 40 RPM／並發 2-5 限制，2026-08-14 使用者情報）：spec 內建
    節流——--qps 1（每秒 1 請求上限）＋--pool-max-workers 1（不併發）。
    v0.1.4（2026-08-14 使用者實測抓 bug）：pdf2zh_next --qps 是 int（argparse
    type=int）——float 0.6 直接 "invalid int value" 退出；本測試模擬 argparse
    int 契約：旗標值必須能 int()（float 字串會 AssertionError 而非靜默通過）。"""
    cfg = EngineConfig(provider="openai", api_key="nvapi-x", qps=1, max_workers=1)
    cmd = build_command(make_job(), cfg)
    qps_val = cmd[cmd.index("--qps") + 1]
    workers_val = cmd[cmd.index("--pool-max-workers") + 1]
    # argparse type=int 契約：int() 失敗 = 真實 CLI 會以 "invalid int value" 退出
    int(qps_val)
    int(workers_val)
    assert qps_val == "1"
    assert workers_val == "1"


def test_build_command_no_throttling_flags_by_default():
    """其他引擎（spec 未設節流）不帶 --qps/--pool-max-workers——引擎預設行為不變。"""
    cfg = EngineConfig(api_key="KEY")
    cmd = build_command(make_job(), cfg)
    assert "--qps" not in cmd
    assert "--pool-max-workers" not in cmd
