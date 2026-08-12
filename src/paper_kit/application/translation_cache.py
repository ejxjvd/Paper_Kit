"""TranslationCache（application）：任務層快取（票 24 快取核心）。

SQLite 索引（fingerprint → 快取檔）＋快取檔自有副本於 cache_dir——
不記路徑指向 outputs/<job_id>/（票 18 刪任務會刪輸出目錄，快取必須自持副本）。

**快取是優化不是依賴**：DB 損壞／外部刪檔一律安靜降級（get 回 None、put 空轉），
絕不讓翻譯任務被快取炸掉。enabled 旗標是開關的承載點（票 25 設定頁切換；
JobService 層決定查不查——enabled=False 時根本不呼叫 get/put）。
"""

import hashlib
import logging
import shutil
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("paper_kit.application.translation_cache")

_INDEX_DB = "index.db"


@dataclass(frozen=True)
class CachedResult:
    """快取命中回傳：快取檔路徑（呼叫端複製回任務目錄）。"""

    mono_path: str | None
    dual_path: str | None


class TranslationCache:
    def __init__(self, cache_dir: str | Path, enabled: bool = True):
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self.enabled = enabled
        self._lock = threading.Lock()  # 2026-08-12 實測 bug：worker thread 跨執行緒用 DB
        self._db: sqlite3.Connection | None = None
        try:
            # check_same_thread=False：connection 建於主 thread、_run 在 worker thread
            # 呼叫 get/put——預設 True 直接拒絕（「SQLite objects created in a thread…」）；
            # 跨執行緒安全由本類 Lock 序列化保證
            self._db = sqlite3.connect(self._dir / _INDEX_DB, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS cache_entries ("
                "fingerprint TEXT PRIMARY KEY, mono TEXT, dual TEXT)"
            )
            self._db.commit()
        except sqlite3.Error as exc:
            # DB 損壞：整個快取停用（優化不是依賴）
            self._db = None
            logger.warning("快取 DB 無法開啟，快取停用: %s", exc)

    @staticmethod
    def _file_name(fingerprint: str, kind: str, suffix: str) -> str:
        # 指紋含 `|`（不能當 Windows 檔名）→ sha256 消化成安全檔名
        digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
        return f"{digest}.{kind}{suffix}"

    def put(self, fingerprint: str, mono_path: str | None, dual_path: str | None) -> None:
        if self._db is None:
            return
        try:
            mono = self._copy_in(fingerprint, "mono", mono_path)
            dual = self._copy_in(fingerprint, "dual", dual_path)
            with self._lock:
                self._db.execute(
                    "INSERT OR REPLACE INTO cache_entries (fingerprint, mono, dual) VALUES (?, ?, ?)",
                    (fingerprint, mono, dual),
                )
                self._db.commit()
        except sqlite3.Error as exc:
            logger.warning("快取寫入失敗（忽略，翻譯不受影響）: %s", exc)

    def _copy_in(self, fingerprint: str, kind: str, path: str | None) -> str | None:
        if not path:
            return None
        src = Path(path)
        dest = self._dir / self._file_name(fingerprint, kind, src.suffix)
        try:
            shutil.copy2(src, dest)
        except OSError as exc:
            logger.warning("快取檔複製失敗（忽略）: %s", exc)
            return None
        return str(dest)

    def get(self, fingerprint: str) -> CachedResult | None:
        if self._db is None:
            return None
        try:
            with self._lock:
                row = self._db.execute(
                    "SELECT mono, dual FROM cache_entries WHERE fingerprint = ?", (fingerprint,)
                ).fetchone()
        except sqlite3.Error as exc:
            logger.warning("快取讀取失敗（視同 miss）: %s", exc)
            return None
        if row is None:
            return None
        mono, dual = row
        for path in (mono, dual):  # 外部刪檔 → 自癒：清死索引、回 None
            if path and not Path(path).exists():
                self._drop(fingerprint)
                return None
        return CachedResult(mono_path=mono, dual_path=dual)

    def _drop(self, fingerprint: str) -> None:
        try:
            with self._lock:
                self._db.execute("DELETE FROM cache_entries WHERE fingerprint = ?", (fingerprint,))
                self._db.commit()
        except sqlite3.Error:
            pass

    def clear(self) -> None:
        """刪除全部快取檔＋清空索引（票 25「清除快取」按鈕）。"""
        if self._db is None:
            return
        for entry in self._dir.iterdir():
            if entry.is_file() and entry.name != _INDEX_DB:
                entry.unlink(missing_ok=True)
        with self._lock:
            self._db.execute("DELETE FROM cache_entries")
            self._db.commit()

    def stats(self) -> tuple[int, int]:
        """(任務數, 總位元組)——掃目錄實算（檔案才是真值，DB 可能失準）。"""
        count, total = 0, 0
        for entry in self._dir.iterdir():
            if entry.is_file() and entry.name != _INDEX_DB:
                count += 1
                total += entry.stat().st_size
        return count, total
