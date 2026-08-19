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
from pathlib import Path

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
    parse_output,
)


@pytest.fixture(autouse=True)
def _preflight_ok(monkeypatch):
    """卡②（2026-08-14）：BabelDoc 有 key 即 preflight（骨架鉤子）——全部
    translate 測試的 preflight 打 200（探測單點由 test_llm_probe 自行涵蓋）；
    專門的 preflight 測試（401/404/200 呼叫）在測試內覆寫此 patch。"""
    import paper_kit.infrastructure.llm_probe as probe_mod

    monkeypatch.setattr(probe_mod, "probe_model", lambda *a, **k: (200, "ok"))


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
    # v0.1.9.7：--python 釘死插在 tool run 與工具名之間
    assert cmd[0:3] == ["uv", "tool", "run"]
    assert "babeldoc" in cmd
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


def test_build_command_only_selected_pages_off_omits_flag():
    """#85：仅选中页面 toggle OFF → 不送 --only-include-translated-page。"""
    cmd = build_babeldoc_command(
        make_job(pages="3-4", only_selected_pages=False),
        BabelDocConfig(api_key="KEY"),
    )
    assert "--pages" in cmd
    assert "--only-include-translated-page" not in cmd


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


# ── #85 切片C：babeldoc 進階旗標（僅 babeldoc 引擎，一手 CLI 源碼實證） ──


def test_build_command_advanced_flags_default_off():
    """#85：進階開關預設全關——相容模式／移除非公式線條不送；行號增強預設
    開（不送反向 --no-merge-...）；字體預設 serif（不送 --primary-font-family）。"""
    cmd = build_babeldoc_command(make_job(), BabelDocConfig(api_key="KEY"))
    assert "--enhance-compatibility" not in cmd
    assert "--remove-non-formula-lines" not in cmd
    assert "--no-merge-alternating-line-numbers" not in cmd
    assert "--primary-font-family" not in cmd


def test_build_command_advanced_flags_when_enabled():
    """#85：勾選進階開關 → 對應旗標送達（源碼：--enhance-compatibility／
    --no-merge-alternating-line-numbers／--remove-non-formula-lines／
    --primary-font-family serif|sans-serif|script）。"""
    cmd = build_babeldoc_command(
        make_job(
            enhance_compatibility=True,
            merge_alternating_line_numbers=False,  # 行號增強關閉 → 送反向旗標
            remove_non_formula_lines=True,
            font_family="script",
        ),
        BabelDocConfig(api_key="KEY"),
    )
    assert "--enhance-compatibility" in cmd
    assert "--no-merge-alternating-line-numbers" in cmd
    assert "--remove-non-formula-lines" in cmd
    assert cmd[cmd.index("--primary-font-family") + 1] == "script"


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


def test_default_runner_sets_wide_columns_env():
    """#23 root fix：runner 必須把 COLUMNS=1000 傳給子程序——rich 才不會折行
    （實測 COLUMNS=1000 後 babeldoc 三行 token 統計皆單行完整）。"""
    import sys

    adapter = BabelDocAdapter(BabelDocConfig(api_key="KEY"))  # 真實 runner
    rc, out = adapter._runner(
        [sys.executable, "-c", "import os; print(os.environ.get('COLUMNS'))"],
        timeout=15,
    )
    assert rc == 0
    assert out.strip() == "1000"


# ── #23：rich 折行 token 解析（2026-08-13 實跑定案） ──────

# 實跑實證（CH4 頁 29,30 同參數重現）：babeldoc 0.6.2 非 TTY 輸出由 rich 以
# 固定寬度折行——"Completion tokens: 2830" 被拆成兩行、source 標記 main.py:774
# 夾在冒號與數字之間 → 原 regex 同行搜不到 → DB 誤記 out=0（10070=7240+2830
# 驗算：真實 completion 就是 2830，不是 0）。
WRAPPED_LOG = (
    "INFO     INFO:babeldoc.main:Total tokens: 10070  main.py:772\n"
    "INFO     INFO:babeldoc.main:Prompt tokens: 7240  main.py:773\n"
    "INFO     INFO:babeldoc.main:Completion tokens:   main.py:774\n"
    "                             2830\n"
    "INFO     INFO:babeldoc.main:Cache hit prompt     main.py:775\n"
    "                             tokens: 2688\n"
)


def test_parse_output_unwraps_rich_wrapped_completion():
    result = parse_output(WRAPPED_LOG, make_job())
    assert result.input_tokens == 7240
    assert result.output_tokens == 2830  # 折行前是 0（bug）


def test_parse_output_unwraps_wrapped_total_and_prompt():
    """折行也可能落在 Total/Prompt 行——正規化後三者都要能解析。"""
    wrapped = (
        "INFO     INFO:babeldoc.main:Total tokens:       main.py:772\n"
        "                             10070\n"
        "INFO     INFO:babeldoc.main:Prompt tokens:      main.py:773\n"
        "                             7240\n"
        "INFO     INFO:babeldoc.main:Completion tokens:  main.py:774\n"
        "                             2830\n"
    )
    result = parse_output(wrapped, make_job())
    assert result.input_tokens == 7240
    assert result.output_tokens == 2830


# ── translate：preflight 預檢（卡②：BabelDoc 同走 OpenAI 相容端點）──


def test_translate_preflight_401_blocks_before_engine(monkeypatch):
    """卡②（2026-08-14 架構健檢）：#78 假成功防禦原本只內嵌 Pdf2zhNextAdapter
    ——BabelDoc 同走 OpenAI 相容端點（--openai 三旗標）、同受「上游吞錯 rc=0
    假成功」風險（查證 BabelDOC 官方 README：only OpenAI-compatible LLM is
    supported）。preflight 骨架化後 BabelDoc 自動獲得：401 → EngineError 帶
    診斷、引擎根本不上（FakeRunner 不被呼叫）。"""

    import paper_kit.infrastructure.llm_probe as probe_mod

    runner = FakeRunner((0, LOG))
    adapter = BabelDocAdapter(
        BabelDocConfig(api_key="bad-key", base_url="https://x/v1", model="m1"),
        runner=runner,
    )
    monkeypatch.setattr(probe_mod, "probe_model", lambda *a, **k: (401, "Authentication failed"))
    with pytest.raises(EngineError, match="key 無效"):
        adapter.translate(make_job())
    assert runner.calls == [], "preflight 失敗不得啟動引擎子進程"


def test_translate_preflight_404_blocks_with_model_hint(monkeypatch):
    """preflight 404（模型不存在）→ 診斷訊息帶「模型」提示。"""

    import paper_kit.infrastructure.llm_probe as probe_mod

    runner = FakeRunner((0, LOG))
    adapter = BabelDocAdapter(
        BabelDocConfig(api_key="k", base_url="https://x/v1", model="bad-model"),
        runner=runner,
    )
    monkeypatch.setattr(probe_mod, "probe_model", lambda *a, **k: (404, "not found"))
    with pytest.raises(EngineError, match="模型不存在"):
        adapter.translate(make_job())
    assert runner.calls == []


def test_translate_preflight_ok_continues_to_engine(monkeypatch):
    """preflight 200 → 照常翻譯（FakeRunner 被呼叫、正常產出）；並證明
    preflight 真的被執行（探測單點被呼叫）。"""

    import paper_kit.infrastructure.llm_probe as probe_mod

    called = []
    runner = FakeRunner((0, LOG))
    adapter = BabelDocAdapter(
        BabelDocConfig(api_key="good", base_url="https://x/v1", model="m1"),
        runner=runner,
    )
    monkeypatch.setattr(
        probe_mod, "probe_model", lambda *a, **k: (called.append(a) or (200, "ok"))
    )
    result = adapter.translate(make_job())
    assert called, "BabelDoc 有 key 必須 preflight（骨架鉤子生效）"
    assert runner.calls, "preflight 通過後應啟動引擎"
    assert result.input_tokens == 7127


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
    # Path 比較：Windows 上 Path("/in").parent str 為 "\\in"（CI win-x64 實測）
    assert Path(cwd) == Path("/in"), f"引擎要以任務資料夾為 cwd（實得 {cwd!r}）"


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


def test_babeldoc_command_pins_engine_python():
    """v0.1.9.7：與 pdf2zh_next 同一個版本漂移故障——babeldoc 也走 uv tool run。"""
    from paper_kit.infrastructure.uv_bootstrap import ENGINE_PYTHON

    cmd = build_babeldoc_command(make_job(), BabelDocConfig(api_key="KEY"))
    assert cmd[cmd.index("--python") + 1] == ENGINE_PYTHON
    assert cmd.index("--python") < cmd.index("babeldoc")
