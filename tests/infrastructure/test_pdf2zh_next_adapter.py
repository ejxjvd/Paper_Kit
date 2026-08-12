"""Pdf2zhNextAdapter 單元測試（FakeRunner 注入，不碰真實引擎）。

POC 教訓入測：.com 國際站端點預設、key 走 CLI 旗標（不吃 process env）、
50507 暫時性錯誤要 retry、錯誤要轉成友善訊息（不透傳 traceback）。
"""

import subprocess

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.pdf2zh_next_adapter import (
    DEFAULT_BASE_URL,
    EngineConfig,
    Pdf2zhNextAdapter,
    build_command,
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
    "INFO Mono PDF: /out/paper.zh.mono.pdf\n"
    "INFO Dual PDF: /out/paper.zh.dual.pdf\n"
    "Total Token Usage: Total 9346, Prompt 7127, Cache Hit Prompt 1664, Completion 2219\n"
)


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


def test_build_command_no_pages_omits_flag():
    cmd = build_command(make_job(pages=None), EngineConfig(api_key="KEY"))
    assert "--pages" not in cmd


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


# ── translate：成功解析 ──────────────────────────────────


def test_translate_success_parses_outputs_and_tokens():
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=FakeRunner((0, LOG)))
    result = adapter.translate(make_job())
    assert isinstance(result, JobResult)
    assert result.mono_path == "/out/paper.zh.mono.pdf"
    assert result.dual_path == "/out/paper.zh.dual.pdf"
    assert result.input_tokens == 7127
    assert result.output_tokens == 2219


def test_translate_fallback_paths_when_log_lacks_paths():
    adapter = Pdf2zhNextAdapter(
        EngineConfig(api_key="KEY"),
        runner=FakeRunner((0, "Total Token Usage: Total 1, Prompt 1, Cache Hit Prompt 0, Completion 1\n")),
    )
    result = adapter.translate(make_job())
    assert result.mono_path == "/in/paper.zh.mono.pdf"  # 慣例路徑
    assert result.dual_path == "/in/paper.zh.dual.pdf"


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


def test_translate_runs_engine_in_job_source_directory():
    """babeldoc 輸出走子程序 CWD → cwd 必須是任務資料夾，產出才落在該處（票 03 實測教訓）。"""
    runner = FakeRunner((0, LOG))
    job = make_job()  # source_path = /in/paper.pdf
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    adapter.translate(job)
    _, _, cwd = runner.calls[0]
    assert cwd == "/in", f"引擎要以任務資料夾為 cwd（實得 {cwd!r}）"
