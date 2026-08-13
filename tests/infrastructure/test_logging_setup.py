"""票 09 切片 B：結構化 log（JSON、元件、錯誤鏈）＋ API key redaction。

規格書 story 15「可追蹤的 log」＋「log 不含 API key」——key 只該出現在
CLI 命令／引擎輸出，進 log 前一律遮罩。
"""

import json
import logging
import subprocess

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.logging_setup import (
    format_error_chain,
    redact,
    redact_command,
    setup_logging,
)
from paper_kit.infrastructure.pdf2zh_next_adapter import (
    EngineConfig,
    build_command,
)
from paper_kit.domain.translation_job import TranslationJob


@pytest.fixture(autouse=True)
def _clean_handlers():
    """每個測試獨立 log 設定（避免 FileHandler 疊加污染）。"""
    yield
    logging.getLogger("paper_kit").handlers.clear()


def test_redact_replaces_every_secret_occurrence():
    text = "--siliconflow-api-key sk-123456 之後再出現 sk-123456 也要遮"
    assert redact(text, ["sk-123456"]) == "--siliconflow-api-key *** 之後再出現 *** 也要遮"


def test_redact_command_masks_api_key_values():
    cmd = ["uv", "tool", "run", "pdf2zh_next", "a.pdf",
           "--siliconflow-api-key", "sk-SECRET", "--pages", "1-2"]
    masked = redact_command(cmd)
    assert "sk-SECRET" not in masked
    assert masked[masked.index("--siliconflow-api-key") + 1] == "***"
    # 非機密旗標值不動
    assert "1-2" in masked


def test_build_command_redacted_never_leaks_key():
    """adapter 的命令若進 log，redact 後不得含 key（票 09 紅線）。"""
    job = TranslationJob(job_id="j1", source_path="/in/paper.pdf")
    cfg = EngineConfig(api_key="sk-TOPSECRET")
    cmd = build_command(job, cfg)
    assert "sk-TOPSECRET" in cmd  # 命令本身有 key（CLI 直傳是必要設計）
    masked = redact_command(cmd)
    assert "sk-TOPSECRET" not in masked
    assert "***" in masked


def test_format_error_chain_walks_cause_chain():
    """review：手動塞 __cause__ 是 over-specified（production 不會這樣產生），
    用真實的 raise-from 形狀測 __cause__ 鏈。"""
    inner = EngineError("上游 500")
    with pytest.raises(EngineError) as exc_info:
        try:
            raise inner
        except EngineError:
            raise EngineError("翻譯失敗") from inner
    assert exc_info.value.__cause__ is inner
    assert format_error_chain(exc_info.value) == "翻譯失敗 | caused by 上游 500"


def test_format_error_chain_falls_back_to_context():
    """review：`raise X` 在 except 內沒有 `from` 時 Python 設 __context__ 非 __cause__，
    鏈也要走得出來（例如 JobService 兜底轉成 EngineError 時）。"""
    inner = ValueError("引擎崩了")
    outer = EngineError("翻譯失敗")
    with pytest.raises(EngineError) as exc_info:
        try:
            raise inner
        except ValueError:
            raise outer  # 無 from → __context__
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__context__ is inner
    assert format_error_chain(exc_info.value) == "翻譯失敗 | caused by 引擎崩了"


def test_format_error_chain_single_error_no_bar():
    assert format_error_chain(EngineError("就一個錯誤")) == "就一個錯誤"


def test_log_file_is_json_with_component_and_job_id(tmp_path):
    log_path = setup_logging(tmp_path)
    logger = logging.getLogger("paper_kit.application.job_service")
    logger.error("任務失敗", extra={"job_id": "abc123"})

    line = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["level"] == "ERROR"
    assert line["component"] == "paper_kit.application.job_service"
    assert line["job_id"] == "abc123"
    assert line["message"] == "任務失敗"
    assert "time" in line


def test_log_captures_error_chain_extra(tmp_path):
    log_path = setup_logging(tmp_path)
    logger = logging.getLogger("paper_kit.infrastructure.pdf2zh_next_adapter")
    logger.error("翻譯失敗", extra={"error_chain": "翻譯失敗 | caused by 上游 500"})

    line = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["error_chain"] == "翻譯失敗 | caused by 上游 500"


# ── 接線：adapter 錯誤 log（命令含 key 也不得進 log）────────────


def test_adapter_error_log_has_chain_and_no_api_key(tmp_path):
    """adapter 翻譯失敗 → log 記錯誤鏈；命令含的 key 一律遮罩（票 09 紅線）。"""
    import pytest

    from paper_kit.infrastructure.pdf2zh_next_adapter import (
        EngineConfig,
        Pdf2zhNextAdapter,
    )

    log_path = setup_logging(tmp_path)
    cfg = EngineConfig(api_key="sk-TOPSECRET")

    class FailingRunner:
        def __call__(self, cmd, timeout=None, cwd=None):
            raise subprocess.TimeoutExpired("pdf2zh_next", 600)

    adapter = Pdf2zhNextAdapter(cfg, runner=FailingRunner())
    job = TranslationJob(job_id="j1", source_path="/in/paper.pdf")
    with pytest.raises(EngineError):
        adapter.translate(job)

    text = log_path.read_text(encoding="utf-8")
    assert "sk-TOPSECRET" not in text, "log 不得含 API key"
    last = json.loads(text.strip().splitlines()[-1])
    assert "逾時" in last["message"]


def test_job_service_events_carry_job_id(tmp_path):
    """JobService 事件 log 帶 job_id（debug 檢視頁按任務過濾的基礎）。"""
    from paper_kit.application.job_service import JobService
    from paper_kit.infrastructure.memory_repo import InMemoryJobRepository

    log_path = setup_logging(tmp_path)
    service = JobService(jobs=InMemoryJobRepository(), outputs_dir=tmp_path / "outputs")
    upload = tmp_path / "a.pdf"
    upload.write_bytes(b"%PDF-1.4")
    job = service.create_job(upload_path=upload)

    lines = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines()]
    created = [l for l in lines if l["message"] == "任務已建立"]
    assert created and created[0]["job_id"] == job.job_id


# ── 切片 C：debug 檢視頁的純函式 ──────────────────────────────


def test_recent_log_entries_filters_by_job_id(tmp_path):
    from paper_kit.infrastructure.logging_setup import recent_log_entries

    log_path = setup_logging(tmp_path)
    logger = logging.getLogger("paper_kit.test")
    logger.info("任務已建立", extra={"job_id": "aaa111"})
    logger.info("任務已建立", extra={"job_id": "bbb222"})
    logger.info("任務失敗", extra={"job_id": "aaa111", "error_chain": "boom"})

    all_entries = recent_log_entries(log_path, n=10)
    assert len(all_entries) == 3
    filtered = recent_log_entries(log_path, n=10, job_id="aaa111")
    assert len(filtered) == 2
    assert all(e["job_id"] == "aaa111" for e in filtered)
    assert recent_log_entries(log_path, n=10, job_id="zzz") == []


def test_format_log_line_for_display():
    """debug 頁顯示行：time level [component] message；job_id 過濾。"""
    from datetime import datetime

    from paper_kit.infrastructure.logging_setup import format_log_line

    # v0.1.3：時間轉本地時區（log 存 UTC，2026-08-14 使用者指出差 8 小時）——
    # 期望值用相同轉換自己算（測試時區無關，CI runner 可能是 UTC 或 +8）
    expected_local = datetime.fromisoformat("2026-08-12T10:00:00+00:00").astimezone().strftime("%Y-%m-%d %H:%M:%S")
    line = format_log_line(
        {"time": "2026-08-12T10:00:00+00:00", "level": "ERROR",
         "component": "paper_kit.application.job_service", "message": "任務失敗",
         "job_id": "abc123"}
    )
    assert expected_local in line
    assert "ERROR" in line
    assert "[job_service]" in line  # 元件短名
    assert "任務失敗" in line
    assert "abc123" in line


def test_format_log_line_shows_error_field_too():
    """票 09 review：失敗 log 統一記 error 欄位（訊息），display 要讀到。"""
    from paper_kit.infrastructure.logging_setup import format_log_line

    line = format_log_line(
        {"time": "2026-08-12T10:00:00+00:00", "level": "ERROR",
         "component": "paper_kit.infrastructure.pdf2zh_next_adapter",
         "message": "翻譯失敗", "error": "API key 無效或已過期"}
    )
    assert "API key 無效或已過期" in line


# ── CMD 狀態列 log（2026-08-14 使用者：「你的視窗應該要顯示 LOG 紀錄，
#    不然都看不到執行碼或錯誤碼」→「我指的是 CMD 的狀態列」→
#    「也就是 paper-kit-0.1.4.exe」）────────────────────────────


def test_setup_logging_adds_console_handler(tmp_path, capsys):
    """exe 的 CMD 視窗即時顯示 log（人類可讀，非 JSON 行）；檔案維持 JSON。"""
    log_path = setup_logging(tmp_path)
    logger = logging.getLogger("paper_kit.application.job_service")
    logger.info("任務已建立", extra={"job_id": "abc123"})

    out = capsys.readouterr().out
    assert "任務已建立" in out, f"CMD 狀態列應印出 log，實際：{out!r}"
    assert "abc123" in out, "console 行應含任務 id（格式化行同 debug 頁格式）"
    assert not out.lstrip().startswith("{"), "console 人類可讀，不得是 JSON 行"
    # 檔案仍為 JSON（debug 頁/後續分析用）
    line = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["message"] == "任務已建立" and line["job_id"] == "abc123"


def test_console_handler_not_duplicated_on_repeat_setup(tmp_path, capsys):
    """setup_logging 重複呼叫不得疊加 console handler（同 file handler 防重複）。"""
    setup_logging(tmp_path)
    setup_logging(tmp_path)
    root = logging.getLogger("paper_kit")
    console_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
    ]
    assert len(console_handlers) == 1, "console handler 只應有一個"
    file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1, "file handler 只應有一個"


def test_console_line_has_error_chain_when_failed(tmp_path, capsys):
    """失敗 log 在 CMD 狀態列也帶錯誤鏈（使用者看得到錯誤碼）。"""
    setup_logging(tmp_path)
    logger = logging.getLogger("paper_kit.infrastructure.pdf2zh_next_adapter")
    logger.error(
        "翻譯失敗",
        extra={"error_chain": "翻譯失敗 | caused by 上游 500", "job_id": "abc123"},
    )
    out = capsys.readouterr().out
    assert "翻譯失敗" in out
    assert "上游 500" in out, "CMD 狀態列應顯示錯誤鏈"
