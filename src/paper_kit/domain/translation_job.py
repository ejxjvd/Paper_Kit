"""TranslationJob 聚合根＋狀態機（純領域，無 IO）。

轉換表（規格書定案）：
  queued → translating → completed
                    ↘ failed → queued（retry）
                    ↘ cancelled
"""

import time
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
    # FAILED 合法：應用重啟時排隊中的任務被系統中斷（spec review——重啟復原用）
    JobStatus.QUEUED: frozenset({JobStatus.TRANSLATING, JobStatus.FAILED}),
    JobStatus.TRANSLATING: frozenset({JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}),
    JobStatus.FAILED: frozenset({JobStatus.QUEUED}),  # retry 回 queued
    JobStatus.COMPLETED: frozenset(),  # 終態
    JobStatus.CANCELLED: frozenset(),  # 終態
}


@dataclass
class TranslationJob:
    job_id: str
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)  # 票 08：歷史列表顯示時間
    source_path: str | None = None
    target_lang: str = "zh-TW"
    pages: str | None = None          # "1-2" 形式；None = 全文
    output_dir: str = ""              # 票 07：完成後產出複製到的目錄；空白 = 預設 outputs/<job_id>/
    glossary_files: list[str] = field(default_factory=list)
    auto_extract: bool = False        # 票 05：--term-siliconflow 自動術語提取
    engine_id: str | None = None      # 用哪個引擎（票 06 計價用）
    estimated_cost: Decimal | None = None  # 票 06：上傳時的前置估算（完成後比對用）
    estimated_tokens: int | None = None    # 2026-08-13：上傳時估算的總 tokens（UI 顯示預估用）
    sensitive: bool = False           # 票 10：機密文件（R18／隱私）——只准純文字引擎
    ocr: bool = False                 # 票 12：掃描件（無文字層）——執行前先本機 OCR
    only_selected_pages: bool = True  # #85：僅翻譯選中頁面（引擎預設輸出全部頁面；OFF＝未選頁原樣保留）
    # #85 切片C：babeldoc 進階選項（僅 babeldoc 引擎消費；其他引擎忽略）
    enhance_compatibility: bool = False   # --enhance-compatibility（相容模式：版式較保守、錯位較少）
    merge_alternating_line_numbers: bool = True  # 行號增強（True=合併交錯行號；CLI 反向旗標 --no-merge-...）
    remove_non_formula_lines: bool = False  # --remove-non-formula-lines（移除段落中的非公式線條）
    font_family: str = "serif"           # --primary-font-family：serif / sans-serif / script
    result: JobResult | None = None
    error: str | None = None
    progress: float | None = None     # #72：翻譯進度 0.0–1.0（None＝無確定進度→UI 用 indeterminate）

    def transition(self, new_status: JobStatus) -> None:
        """依轉換表嘗試遷移；非法轉換丟 InvalidTransition 且狀態不變。"""
        if new_status not in _LEGAL_TRANSITIONS[self.status]:
            raise InvalidTransition(
                f"Illegal transition: {self.status.name} -> {new_status.name}"
            )
        self.status = new_status

    @property
    def can_retry(self) -> bool:
        """票 08：能否重試——完全由領域轉換表推導（QUEUED 在合法目標中）。"""
        return JobStatus.QUEUED in _LEGAL_TRANSITIONS[self.status]

    @property
    def can_cancel(self) -> bool:
        """票 08：能否取消——由領域轉換表推導（CANCELLED 在合法目標中）。"""
        return JobStatus.CANCELLED in _LEGAL_TRANSITIONS[self.status]

    @property
    def can_delete(self) -> bool:
        """#74：能否刪除——非執行中（排隊/翻譯中不可刪，service.delete 的紅線）。

        執行中任務有 live worker 在寫檔，刪除會讓輸出目錄消失；終態
        （完成/失敗/取消）已無 worker → 可刪（清掉舊任務不堆積主頁）。
        """
        return self.status not in (JobStatus.QUEUED, JobStatus.TRANSLATING)
