"""Pdf2zhNextAdapter 單元測試（FakeRunner 注入，不碰真實引擎）。

POC 教訓入測：.com 國際站端點預設、key 走 CLI 旗標（不吃 process env）、
50507 暫時性錯誤要 retry、錯誤要轉成友善訊息（不透傳 traceback）。
"""

import subprocess
import sys
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
    (tmp_path / ".local" / "bin").mkdir(parents=True)
    (tmp_path / ".local" / "bin" / "uv").touch()
    monkeypatch.setattr("paper_kit.infrastructure.cli_adapter_base.shutil.which",
                        lambda _: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    captured: dict = {}

    class FakeProc:
        returncode = 0

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            captured["kwargs"] = kwargs

        def communicate(self, timeout=None):
            return (LOG, None)

    monkeypatch.setattr(
        "paper_kit.infrastructure.cli_adapter_base.subprocess.Popen", FakeProc
    )
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))  # 真 runner，不注入
    result = adapter.translate(make_job())
    # 用的絕對路徑 uv，不是裸 "uv"（PATH 找不到時裸名直接 Errno）
    assert captured["cmd"][0] == str(tmp_path / ".local" / "bin" / "uv")
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


def test_build_command_glossary_with_auto_extract_keeps_extraction_enabled():
    """票 13 統一：UI 兩開關可同開 → 有術語表＋自動提取時不禁用提取。"""
    cmd = build_command(
        make_job(glossary_files=["/gl/a.csv"], auto_extract=True),
        EngineConfig(api_key="KEY"),
    )
    assert "--glossaries" in cmd
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


def test_translate_runs_engine_in_job_source_directory():
    """babeldoc 輸出走子程序 CWD → cwd 必須是任務資料夾，產出才落在該處（票 03 實測教訓）。"""
    runner = FakeRunner((0, LOG))
    job = make_job()  # source_path = /in/paper.pdf
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    adapter.translate(job)
    _, _, cwd = runner.calls[0]
    assert cwd == "/in", f"引擎要以任務資料夾為 cwd（實得 {cwd!r}）"


# ── 票 08：取消 ─────────────────────────────────────────────


def test_translate_after_cancel_raises_without_running_engine():
    """取消後 translate 一律拒絕，不再啟動引擎。"""
    def runner(cmd, timeout=None, cwd=None):
        raise AssertionError("取消後不該再跑引擎")

    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"), runner=runner)
    adapter.cancel()
    with pytest.raises(EngineError, match="已取消"):
        adapter.translate(make_job())


def test_cancel_kills_running_subprocess(monkeypatch):
    """真實子程序：cancel() 要真的殺掉在跑的引擎（Popen handle 掛回 adapter）。"""
    import threading
    import time

    # 讓引擎命令變成 sleep 30（build_command 換成假指令，保持預設 Popen runner）
    monkeypatch.setattr(
        "paper_kit.infrastructure.pdf2zh_next_adapter.build_command",
        lambda job, cfg: ["sleep", "30"],
    )
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))  # 預設 runner（真 Popen）
    job = make_job(source_path="/tmp/slow.pdf")
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
