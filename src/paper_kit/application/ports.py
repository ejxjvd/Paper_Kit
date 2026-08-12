"""Ports（埠）：application 依賴的介面，實作在 infrastructure/presentation。

Ports & Adapters 架構保證：換引擎＝換插頭，UI 與業務邏輯零改動。
"""

from typing import Protocol

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob


class EngineError(Exception):
    """引擎失敗（adapter 包裝真實錯誤後丟出）。"""


class TranslationEnginePort(Protocol):
    """翻譯引擎埠：translate(job) → JobResult。實作：Pdf2zhNextAdapter 等。"""

    def translate(self, job: TranslationJob) -> JobResult:
        """翻譯任務；失敗丟 EngineError（job 狀態由 application 處理）。"""
        ...

    def cancel(self) -> None:
        """票 08：中止進行中的翻譯（殺子程序；之後的 translate 應拋 EngineError）。"""
        ...


class JobRepository(Protocol):
    """任務儲存埠。實作：InMemoryJobRepository（測試）、SQLite repository（正式）。"""

    def add(self, job: TranslationJob) -> None: ...

    def get(self, job_id: str) -> TranslationJob | None: ...

    def save(self, job: TranslationJob) -> None: ...

    def list(self) -> list[TranslationJob]:
        """票 08：全部任務（建立順序）——重啟後 JobService 由此載入歷史。"""
        ...
