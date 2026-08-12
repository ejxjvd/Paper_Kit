"""票 09：結構化 log 設定（JSON Lines：time／level／component／message／extra）。

- setup_logging(log_dir)：paper_kit logger → 檔案 handler（JSON formatter）
- redact / redact_command：API key 遮罩（log 紅線——key 只進 CLI 命令，不進 log）
- format_error_chain(exc)：錯誤鏈（A | caused by B，走 __cause__）
"""

import json
import logging
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


def setup_logging(log_dir: str | Path, level: int = logging.INFO) -> Path:
    """paper_kit logger 掛檔案 handler（JSON）。回傳 log 檔路徑（debug 頁用）。"""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "paper_kit.log"
    root = logging.getLogger("paper_kit")
    root.setLevel(level)
    # 防重複掛 handler（setup_logging 可能被多次呼叫）
    if not any(getattr(h, "baseFilename", None) == str(log_path) for h in root.handlers):
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
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


def format_log_line(entry: dict) -> str:
    """JSON log 行 → debug 頁顯示字串（time level [短元件] message）。"""
    time_part = str(entry.get("time", ""))[:19]  # ISO 掐秒
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
