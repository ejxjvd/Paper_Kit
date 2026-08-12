"""BabelDocAdapter 單元測試（FakeRunner 注入，不碰真實引擎）。

一手查證（2026-08-12）：
- BabelDOC 線上服務（Immersive Translate 託管 web app）無公開 API、無 key 產品
  → 本 adapter = BabelDOC 官方 CLI（AGPL v0.6.4）＋OpenAI 相容雲端後端
  （README 唯一支援整合方式：「only OpenAI-compatible LLM is supported」）
- token 行格式源碼實證：logger.info("Total tokens: {value}") 等三行
- 檔名慣例源碼實證（result_merger.py）：{stem}.{lang_out}.mono.pdf / .dual.pdf
- --only-include-translated-page 僅在 --pages 使用時有效（CLI help 原文）
"""

import json
import logging
import subprocess

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.babeldoc_adapter import (
    DEFAULT_BABELDOC_BASE_URL,
    DEFAULT_BABELDOC_MODEL,
    BabelDocAdapter,
    BabelDocConfig,
    build_babeldoc_command,
)


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
    "INFO Translate started\n"
    "INFO Total tokens: 9346\n"
    "INFO Prompt tokens: 7127\n"
    "INFO Completion tokens: 2219\n"
)


# ── build_babeldoc_command：旗標組裝 ─────────────────────


def test_build_command_openai_flags():
    cfg = BabelDocConfig(api_key="KEY")
    cmd = build_babeldoc_command(make_job(), cfg)
    assert cmd[0:4] == ["uv", "tool", "run", "babeldoc"]
    assert "--files" in cmd and "/in/paper.pdf" in cmd
    assert "--openai" in cmd
    assert cmd[cmd.index("--openai-model") + 1] == DEFAULT_BABELDOC_MODEL
    assert cmd[cmd.index("--openai-base-url") + 1] == DEFAULT_BABELDOC_BASE_URL
    assert cmd[cmd.index("--openai-api-key") + 1] == "KEY"
    assert cmd[cmd.index("--lang-out") + 1] == "zh-TW"


def test_build_command_defaults_to_deepseek_openai_endpoint():
    """README 推薦後端：deepseek-chat（OpenAI 相容端點 https://api.deepseek.com/v1）。"""
    cfg = BabelDocConfig(api_key="KEY")
    cmd = build_babeldoc_command(make_job(), cfg)
    assert "https://api.deepseek.com/v1" in cmd
    assert "deepseek-chat" in cmd


def test_build_command_pages_uses_only_include_flag():
    """babeldoc 的 --only-include-translated-page 只在 --pages 時有效（CLI help 原文）。"""
    cmd = build_babeldoc_command(make_job(pages="3-4"), BabelDocConfig(api_key="KEY"))
    assert cmd[cmd.index("--pages") + 1] == "3-4"
    assert "--only-include-translated-page" in cmd


def test_build_command_no_pages_omits_both_flags():
    cmd = build_babeldoc_command(make_job(pages=None), BabelDocConfig(api_key="KEY"))
    assert "--pages" not in cmd
    assert "--only-include-translated-page" not in cmd


def test_build_command_glossaries_comma_joined_with_auto_extract_off():
    cmd = build_babeldoc_command(
        make_job(glossary_files=["/gl/a.csv", "/gl/b.csv"]),
        BabelDocConfig(api_key="KEY"),
    )
    assert cmd[cmd.index("--glossary-files") + 1] == "/gl/a.csv,/gl/b.csv"
    assert "--no-auto-extract-glossary" in cmd


def test_build_command_no_glossary_omits_flags():
    cmd = build_babeldoc_command(make_job(glossary_files=[]), BabelDocConfig(api_key="KEY"))
    assert "--glossary-files" not in cmd
    assert "--no-auto-extract-glossary" not in cmd


def test_build_command_glossary_with_auto_extract_keeps_extraction_enabled():
    """UI 兩開關可同開：有術語表＋自動提取 → 不禁用提取（--no-auto-extract-glossary 缺席）。"""
    cmd = build_babeldoc_command(
        make_job(glossary_files=["/gl/a.csv"], auto_extract=True),
        BabelDocConfig(api_key="KEY"),
    )
    assert "--glossary-files" in cmd
    assert "--no-auto-extract-glossary" not in cmd


def test_build_command_auto_extract_uses_term_extraction_flags():
    """票 05 慣例：自動術語提取開關 → 同 key 的術語提取後端旗標。"""
    cmd = build_babeldoc_command(
        make_job(auto_extract=True), BabelDocConfig(api_key="KEY")
    )
    assert cmd[cmd.index("--openai-term-extraction-model") + 1] == DEFAULT_BABELDOC_MODEL
    assert cmd[cmd.index("--openai-term-extraction-api-key") + 1] == "KEY"
    assert "--no-auto-extract-glossary" not in cmd


# ── translate：成功解析 ──────────────────────────────────


def test_translate_success_parses_tokens_and_fallback_paths():
    """babeldoc CLI 不 print MonoPDF/DualPDF 行 → 檔名走源碼實證的慣例
    （result_merger.py：{basename}.{lang_out}.mono.pdf，lang_out 是完整 "zh-TW"）。"""
    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"), runner=FakeRunner((0, LOG)))
    result = adapter.translate(make_job())
    assert isinstance(result, JobResult)
    assert result.mono_path == "/in/paper.zh-TW.mono.pdf"
    assert result.dual_path == "/in/paper.zh-TW.dual.pdf"
    assert result.input_tokens == 7127
    assert result.output_tokens == 2219


def test_translate_zero_tokens_when_log_lacks_usage():
    adapter = BabelDocAdapter(
        BabelDocConfig(api_key="KEY"), runner=FakeRunner((0, "INFO done\n"))
    )
    result = adapter.translate(make_job())
    assert result.input_tokens == 0
    assert result.output_tokens == 0


# ── translate：共用骨架行為（跨插頭守證） ────────────────


def test_missing_key_raises_friendly_error():
    adapter = BabelDocAdapter(BabelDocConfig(api_key=""), runner=FakeRunner((0, LOG)))
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(make_job())


def test_401_maps_to_friendly_key_message():
    adapter = BabelDocAdapter(
        BabelDocConfig(api_key="BAD"),
        runner=FakeRunner((1, "openai.AuthenticationError: 401 Api key is invalid\n")),
    )
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(make_job())


def test_transient_50507_retries_then_succeeds():
    fail_log = "openai.InternalServerError: 50507 Request failed: Unknown error\n"
    runner = FakeRunner((1, fail_log), (1, fail_log), (0, LOG))
    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"), runner=runner)
    result = adapter.translate(make_job())
    assert len(runner.calls) == 3
    assert result.input_tokens == 7127


def test_non_transient_error_no_retry():
    runner = FakeRunner((1, "AuthenticationError 401\n"))
    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"), runner=runner)
    with pytest.raises(EngineError):
        adapter.translate(make_job())
    assert len(runner.calls) == 1


def test_timeout_maps_to_timeout_message():
    runner = FakeRunner(subprocess.TimeoutExpired("babeldoc", 600))
    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"), runner=runner)
    with pytest.raises(EngineError, match="逾時"):
        adapter.translate(make_job())


def test_translate_runs_engine_in_job_source_directory():
    """輸出走子程序 CWD → cwd 必須是任務資料夾（票 03 實測教訓跨插頭）。"""
    runner = FakeRunner((0, LOG))
    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"), runner=runner)
    adapter.translate(make_job())  # source_path = /in/paper.pdf
    _, _, cwd = runner.calls[0]
    assert cwd == "/in", f"引擎要以任務資料夾為 cwd（實得 {cwd!r}）"


def test_engine_output_leaking_api_key_is_redacted_in_error_and_log(tmp_path):
    """票 09 紅線（跨插頭）：失敗輸出回顯 key → EngineError 與 log 都不許含 key。"""
    from paper_kit.infrastructure.logging_setup import setup_logging

    log_path = setup_logging(tmp_path)
    try:
        output = "RuntimeError: boom\n--openai-api-key sk-TOPSECRET\n"
        adapter = BabelDocAdapter(
            BabelDocConfig(api_key="sk-TOPSECRET"),
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


# ── 票 08：取消 ─────────────────────────────────────────


def test_translate_after_cancel_raises_without_running_engine():
    def runner(cmd, timeout=None, cwd=None):
        raise AssertionError("取消後不該再跑引擎")

    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"), runner=runner)
    adapter.cancel()
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(make_job())
