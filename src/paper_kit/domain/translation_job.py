"""TranslationJob 聚合根＋狀態機（純領域，無 IO）。

轉換表（規格書定案）：
  queued → translating → completed
                    ↘ failed → queued（retry）
                    ↘ cancelled
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto

from paper_kit.domain.job_result import JobResult


class JobStatus(Enum):
    QUEUED = auto()
    TRANSLATING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class InvalidTransition(Exception):
    """非法狀態轉換（如 completed→queued）。"""


_LEGAL_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.QUEUED: frozenset({JobStatus.TRANSLATING}),
    JobStatus.TRANSLATING: frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),  # retry 回 queued
    JobStatus.COMPLETED: frozenset(),  # 終態
    JobStatus.CANCELLED: frozenset(),  # 終態
}


@dataclass
class TranslationJob:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    source_path: str | None = None
    target_lang: str = "zh-TW"
    pages: str | None = None          # "1-2" 形式；None = 全文
    glossary_files: list[str] = field(default_factory=list)
    auto_extract: bool = False        # 票 05：--term-siliconflow 自動術語提取
    engine_id: str | None = None      # 用哪個引擎（票 06 計價用）
    estimated_cost: Decimal | None = None  # 票 06：上傳時的前置估算（完成後比對用）
    result: JobResult | None = None
    error: str | None = None

    def transition(self, new_status: JobStatus) -> None:
        """依轉換表嘗試遷移；非法轉換丟 InvalidTransition 且狀態不變。"""
        if new_status not in _LEGAL_TRANSITIONS[self.status]:
            raise InvalidTransition(
                f"Illegal transition: {self.status.name} -> {new_status.name}"
            )
        self.status = new_status
