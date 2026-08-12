"""SqliteJobRepository：任務歷史持久化（票 08，SQLite std 庫）。

JSON 序列化 list/Decimal/JobResult；狀態存 enum 名；重啟後 list() 依建立順序回傳。
"""

import json
import sqlite3
import threading
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob

# 欄位清單＝schema 單一真相（review 修正：CREATE/INSERT/UPDATE/序列化統一由此派生；
# 加欄位只改這裡＋_deserialize 的取值映射）
_COLUMNS = (
    "job_id", "created_at", "status", "source_path", "target_lang", "pages",
    "output_dir", "glossary_files", "auto_extract", "engine_id",
    "estimated_cost", "result", "error",
)
_PLACEHOLDERS = ", ".join("?" for _ in _COLUMNS)


class SqliteJobRepository:
    """任務歷史持久化。

    check_same_thread=False＋寫入鎖：worker thread（StartTranslation）也會 save()，
    所有連線操作靠單一 lock 序列化（sqlite3 跨 thread 使用的前提）。
    """

    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS jobs ("
            + ", ".join(f"{c} TEXT" for c in _COLUMNS)
            + ", PRIMARY KEY (job_id))"
        )
        self._conn.commit()

    def add(self, job: TranslationJob) -> None:
        with self._lock:
            self._conn.execute(
                f"INSERT INTO jobs ({', '.join(_COLUMNS)}) VALUES ({_PLACEHOLDERS})",
                self._serialize(job),
            )
            self._conn.commit()

    def get(self, job_id: str) -> TranslationJob | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return self._deserialize(row) if row else None

    def save(self, job: TranslationJob) -> None:
        updates = ", ".join(f"{c}=?" for c in _COLUMNS[1:])
        with self._lock:
            self._conn.execute(
                f"UPDATE jobs SET {updates} WHERE job_id=?",
                self._serialize(job)[1:] + (job.job_id,),
            )
            self._conn.commit()

    def list(self) -> list[TranslationJob]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs ORDER BY created_at, rowid"
            ).fetchall()
        return [self._deserialize(row) for row in rows]

    def _serialize(self, job: TranslationJob) -> tuple:
        return (
            job.job_id,
            job.created_at,
            job.status.name,
            job.source_path,
            job.target_lang,
            job.pages,
            job.output_dir,
            json.dumps(job.glossary_files),
            int(job.auto_extract),
            job.engine_id,
            str(job.estimated_cost) if job.estimated_cost is not None else None,
            json.dumps(asdict(job.result)) if job.result else None,
            job.error,
        )

    def _deserialize(self, row) -> TranslationJob:
        data = dict(zip(_COLUMNS, row))
        result = None
        if data["result"]:
            result = JobResult(**json.loads(data["result"]))
        return TranslationJob(
            job_id=data["job_id"],
            created_at=float(data["created_at"]),
            status=JobStatus[data["status"]],
            source_path=data["source_path"],
            target_lang=data["target_lang"],
            pages=data["pages"],
            output_dir=data["output_dir"] or "",
            glossary_files=json.loads(data["glossary_files"] or "[]"),
            auto_extract=bool(data["auto_extract"]),
            engine_id=data["engine_id"],
            estimated_cost=Decimal(data["estimated_cost"]) if data["estimated_cost"] else None,
            result=result,
            error=data["error"],
        )
