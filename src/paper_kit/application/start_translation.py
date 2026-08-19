"""StartTranslation 指令：把 queued 任務送進引擎，結果/錯誤存回 repo。"""

from __future__ import annotations

from paper_kit.application.job_state import JobStateGate
from paper_kit.application.ports import EngineError, TranslationEnginePort
from paper_kit.domain.translation_job import JobStatus, TranslationJob


class StartTranslation:
    """只描述翻譯流程本身：進行中 → 引擎 → 完成或失敗。

    架構深化（2026-08-19，候選 4）：先前這個 class 收下 JobService 借來的鎖，
    自己負責終態轉換的原子性——於是「狀態何時被安全寫回」要讀兩個 module 才
    看得完整，而缺口就出現在中間（transition(TRANSLATING) 後忘了 save，UI 整段
    翻譯期間顯示「排隊中」）。現在狀態寫入一律經 JobStateGate，鎖不在這裡。
    """

    def __init__(self, engine: TranslationEnginePort, gate: JobStateGate):
        self._engine = engine
        self._gate = gate

    def run(self, job: TranslationJob) -> TranslationJob:
        # 轉換與持久化是同一個動作——UI 從 repo 輪詢，不持久化等於沒發生。
        self._gate.to(job, JobStatus.TRANSLATING)  # 非法起點（如已完成）在此被拒
        try:
            result = self._engine.translate(job)
        except EngineError as e:
            # 票 08：取消後引擎才失敗 → 維持 cancelled（守門人內部原子判定）
            self._gate.to_unless_cancelled(job, JobStatus.FAILED, error=str(e))
            return job
        # 票 08：取消後引擎才完成 → 產出拋棄，維持 cancelled
        self._gate.to_unless_cancelled(job, JobStatus.COMPLETED, result=result)
        return job
