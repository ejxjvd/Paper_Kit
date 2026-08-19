"""JobStateGate：任務狀態的單一守門人（架構深化候選 4，2026-08-19）。

這個 module 存在的理由是一個真實 bug：`StartTranslation.run()` 把狀態轉成
TRANSLATING 後**忘了 save**，而 UI 從 repo 輪詢——於是整段翻譯期間顯示
「排隊中」，翻完才直接跳「完成」（2026-08-19 使用者回報）。

原因不是誰粗心，而是 interface 允許把「轉換」與「持久化」拆成兩步。守門人
把它們合成一個動作後，那個 bug 在型別上就寫不出來了。
"""

import pytest

from paper_kit.application.job_state import JobStateGate
from paper_kit.domain.translation_job import InvalidTransition, JobStatus, TranslationJob


class RecordingRepo:
    """記錄每次 save 當下的狀態——UI 從 repo 讀，「存了什麼」才是使用者看到的。"""

    def __init__(self):
        self._jobs = {}
        self.saved: list[JobStatus] = []
        self.removed: list[str] = []

    def add(self, job):
        self._jobs[job.job_id] = job

    def get(self, job_id):
        return self._jobs.get(job_id)

    def save(self, job):
        self.saved.append(job.status)
        self._jobs[job.job_id] = job

    def remove(self, job_id):
        self.removed.append(job_id)
        self._jobs.pop(job_id, None)

    def list(self):
        return list(self._jobs.values())


def _gate():
    repo = RecordingRepo()
    job = TranslationJob(job_id="job-1")
    repo.add(job)
    return JobStateGate(repo), repo, job


def test_transition_always_persists():
    """核心不變式：轉換必然伴隨持久化。沒有「只轉換不存」這個選項。"""
    gate, repo, job = _gate()
    gate.to(job, JobStatus.TRANSLATING)
    assert repo.saved == [JobStatus.TRANSLATING], "轉換未持久化＝UI 看不到（原 bug）"


def test_fields_land_with_the_status():
    """隨轉換寫入的欄位必須和狀態同時落地——否則 UI 會讀到「已失敗但沒有錯誤訊息」。"""
    gate, repo, job = _gate()
    gate.to(job, JobStatus.TRANSLATING)
    gate.to(job, JobStatus.FAILED, error="引擎爆了")
    assert job.status is JobStatus.FAILED
    assert job.error == "引擎爆了"
    assert repo.saved[-1] is JobStatus.FAILED


def test_illegal_transition_is_refused_and_nothing_saved():
    """非法轉換由領域狀態機擋下，且不得留下半套寫入。"""
    gate, repo, job = _gate()
    with pytest.raises(InvalidTransition):
        gate.to(job, JobStatus.COMPLETED)  # QUEUED→COMPLETED 非法
    assert repo.saved == []
    assert job.status is JobStatus.QUEUED


def test_cancelled_job_is_not_overwritten_by_late_engine_result():
    """票 08：取消後引擎才回報完成 → 產出拋棄、維持 cancelled。

    檢查與轉換必須原子，否則就是 check-then-act race。
    """
    gate, repo, job = _gate()
    gate.to(job, JobStatus.TRANSLATING)
    gate.cancel(job)
    changed = gate.to_unless_cancelled(job, JobStatus.COMPLETED, result="遲到的產出")
    assert changed is False
    assert job.status is JobStatus.CANCELLED
    assert getattr(job, "result", None) != "遲到的產出", "已取消的任務不得被寫入產出"


def test_active_job_cannot_be_removed():
    """票 18：有 live worker 的任務不可刪——即使狀態還是排隊中。

    start() 在 QUEUED 就 spawn thread，那個窗口內任務也是動不得的。
    """
    gate, repo, job = _gate()
    gate.mark_active("job-1")
    with pytest.raises(ValueError):
        gate.remove("job-1", job)
    assert repo.removed == []


def test_removable_once_worker_finished_and_settled():
    """worker 結束且進入終態後才可刪。"""
    gate, repo, job = _gate()
    gate.mark_active("job-1")
    gate.to(job, JobStatus.TRANSLATING)
    gate.to(job, JobStatus.COMPLETED)
    gate.mark_done("job-1")
    gate.remove("job-1", job)
    assert repo.removed == ["job-1"]


def test_progress_writer_throttles():
    """進度回調每行輸出都會觸發；逐行寫 SQLite 太重，小幅跳動要被節流掉。"""
    gate, repo, job = _gate()
    write = gate.progress_writer(job)
    write(0.10)
    write(0.11)  # 變動 <0.02 且時間未到 → 應被丟棄
    write(0.50)
    assert repo.saved.count(JobStatus.QUEUED) == 2, "只有 0.10 與 0.50 該落地"
    assert job.progress == 0.50
