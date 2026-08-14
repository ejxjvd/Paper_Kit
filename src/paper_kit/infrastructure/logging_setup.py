"""票 09：結構化 log 設定（JSON Lines：time／level／component／message／extra）。

- setup_logging(log_dir)：paper_kit logger → 檔案 handler（JSON formatter）
- redact / redact_command：API key 遮罩（log 紅線——key 只進 CLI 命令，不進 log）
- format_error_chain(exc)：錯誤鏈（A | caused by B，走 __cause__）
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_JSON_KEYS = ("time", "level", "component", "message")


class JsonFormatter(logging.Formatter):
    """一行一 JSON 物件；extra（job_id／error_chain）自動納入。"""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        for key in ("job_id", "error_chain", "error"):  # error＝失敗最後訊息（debug 頁顯示）
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        return json.dumps(entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    """CMD 狀態列人類可讀行（2026-08-14 使用者要求 exe CMD 顯示 log）：
    `2026-08-14 14:05:03 INFO [job_service] 任務已建立 (任務 abc123) ← 錯誤鏈`。

    檔案維持 JSON（JsonFormatter）——console 讀者是人類，可讀優先；
    顯示格式與 debug 頁（format_log_line）同源（時間本地時區）。
    """


class FlushingConsoleHandler(logging.StreamHandler):
    """CMD 即時顯示的 console handler（2026-08-15 ricky 真機實測修復）。

    基類 StreamHandler 寫入 stream 後**不 flush**：dev 的 stdout 是 tty
    （line-buffered）→ 恰好即時；PyInstaller frozen exe 的 stdout 是
    block-buffered → log 卡在緩衝區、CMD 永遠看不到（實測 CMD 只有
    NiceGUI ready，uv 安裝進度一行都沒有）。emit 後立即 flush 保證
    每行 log 即時出現在 exe 的 CMD 視窗。
    """

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }
        for key in ("job_id", "error_chain", "error"):
            value = getattr(record, key, None)
            if value is not None:
                entry[key] = value
        return format_log_line(entry)


def setup_logging(
    log_dir: str | Path, level: int = logging.INFO, console: bool = True
) -> Path:
    """paper_kit logger 掛檔案 handler（JSON）＋console handler（人類可讀）。

    2026-08-14（使用者：「你的視窗應該要顯示 LOG 紀錄，不然都看不到執行碼或
    錯誤碼」→「我指的是 CMD 的狀態列」）：console 預設開啟——exe（console=True）
    的 CMD 視窗即時滾動顯示任務／引擎 log，不再只剩 uvicorn 啟動訊息；
    檔案維持 JSON（debug 頁與後續分析讀同一份）。回傳 log 檔路徑（debug 頁用）。
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "paper_kit.log"
    root = logging.getLogger("paper_kit")
    root.setLevel(level)
    # 防重複掛 handler（setup_logging 可能被多次呼叫；file 與 console 各自防重複）
    if not any(getattr(h, "baseFilename", None) == str(log_path) for h in root.handlers):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
    if console and not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        # FlushingConsoleHandler（2026-08-15）：emit 後即 flush——frozen exe
        # 的 stdout block-buffered，基類不 flush 會讓 log 卡緩衝、CMD 看不到
        console_handler = FlushingConsoleHandler(sys.stdout)
        console_handler.setFormatter(ConsoleFormatter())
        root.addHandler(console_handler)
    return log_path


def redact(text: str, secrets: list[str]) -> str:
    """把機密值全部遮成 ***（引擎輸出／命令字串進 log 前用）。"""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def redact_command(cmd: list[str]) -> list[str]:
    """命令列遮罩：`--*-api-key` 旗標的下一個值換成 ***（其他參數不動）。"""
    masked = list(cmd)
    for i, token in enumerate(masked):
        if token.startswith("--") and "api-key" in token and i + 1 < len(masked):
            masked[i + 1] = "***"
    return masked


def format_error_chain(exc: BaseException) -> str:
    """錯誤鏈：'A: 訊息 | caused by B: 訊息'（沿 __cause__，沒有則沿 __context__）。"""
    parts = [str(exc) or exc.__class__.__name__]
    cause = exc.__cause__ or exc.__context__
    while cause is not None:
        parts.append(str(cause) or cause.__class__.__name__)
        cause = cause.__cause__ or cause.__context__
    return " | caused by ".join(parts)


def recent_log_entries(
    log_path: str | Path, n: int, job_id: str | None = None
) -> list[dict]:
    """debug 檢視頁 viewmodel：最近 n 筆 log，可依 job_id 過濾（壞行跳過）。"""
    path = Path(log_path)
    if not path.exists():
        return []
    entries = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if job_id and entry.get("job_id") != job_id:
            continue
        entries.append(entry)
    return entries[-n:] if n > 0 else []


def _local_time_str(raw: str) -> str:
    """UTC ISO → 本地時區顯示（debug 頁；2026-08-14 使用者指出 log 差 8 小時）。"""
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw


def format_log_line(entry: dict) -> str:
    """JSON log 行 → debug 頁顯示字串（time level [短元件] message）。

    時間轉本地時區（log 存 UTC，2026-08-14 使用者實測 Debug 頁顯示差 8 小時）。
    """
    time_part = _local_time_str(str(entry.get("time", "")))
    component = entry.get("component", "").rsplit(".", 1)[-1] or entry.get("component", "")
    parts = [time_part, entry.get("level", ""), f"[{component}]", entry.get("message", "")]
    job_id = entry.get("job_id")
    if job_id:
        parts.append(f"(任務 {job_id[:8]})")
    # 票 09 review：失敗 log 統一記 error（最後錯誤訊息），有真實鏈才用 error_chain
    error = entry.get("error_chain") or entry.get("error")
    if error:
        parts.append(f"← {error}")
    return " ".join(p for p in parts if p)
