"""TranslationJob 狀態機：合法／非法轉換表（domain 純單元，無 IO）。

轉換表（規格書定案）：
  queued → translating → completed
                    ↘ failed → queued（retry）
                    ↘ cancelled
"""

import pytest

from paper_kit.domain.translation_job import JobStatus, TranslationJob, InvalidTransition


def make_job(status: JobStatus) -> TranslationJob:
    job = TranslationJob(job_id="job-1")
    # 從 queued 走到指定狀態
    order = {
        JobStatus.QUEUED: (),
        JobStatus.TRANSLATING: (JobStatus.TRANSLATING,),
        JobStatus.COMPLETED: (JobStatus.TRANSLATING, JobStatus.COMPLETED),
        JobStatus.FAILED: (JobStatus.TRANSLATING, JobStatus.FAILED),
        JobStatus.CANCELLED: (JobStatus.TRANSLATING, JobStatus.CANCELLED),
    }
    for s in order[status]:
        job.transition(s)
    return job


@pytest.mark.parametrize(
    "src,dst",
    [
        (JobStatus.QUEUED, JobStatus.TRANSLATING),
        (JobStatus.TRANSLATING, JobStatus.COMPLETED),
        (JobStatus.TRANSLATING, JobStatus.FAILED),
        (JobStatus.TRANSLATING, JobStatus.CANCELLED),
        (JobStatus.FAILED, JobStatus.QUEUED),  # retry 回 queued
    ],
)
def test_legal_transitions(src, dst):
    job = make_job(src)
    job.transition(dst)
    assert job.status == dst


@pytest.mark.parametrize(
    "src,dst",
    [
        # 從 queued 直接跳到終態（必須經過 translating；FAILED 例外＝系統中斷合法，票 08 review）
        (JobStatus.QUEUED, JobStatus.COMPLETED),
        (JobStatus.QUEUED, JobStatus.CANCELLED),
        # 終態不可再動
        (JobStatus.COMPLETED, JobStatus.QUEUED),
        (JobStatus.COMPLETED, JobStatus.TRANSLATING),
        (JobStatus.COMPLETED, JobStatus.FAILED),
        (JobStatus.COMPLETED, JobStatus.CANCELLED),
        (JobStatus.CANCELLED, JobStatus.QUEUED),
        (JobStatus.CANCELLED, JobStatus.TRANSLATING),
        (JobStatus.CANCELLED, JobStatus.COMPLETED),
        # failed 只能 retry 回 queued
        (JobStatus.FAILED, JobStatus.TRANSLATING),
        (JobStatus.FAILED, JobStatus.COMPLETED),
        (JobStatus.FAILED, JobStatus.CANCELLED),
        # 重複同態（translating→translating 非法）
        (JobStatus.TRANSLATING, JobStatus.TRANSLATING),
    ],
)
def test_illegal_transitions_rejected(src, dst):
    job = make_job(src)
    with pytest.raises(InvalidTransition):
        job.transition(dst)
    assert job.status == src  # 拒絕後狀態不變


def test_new_job_starts_queued():
    job = TranslationJob(job_id="job-1")
    assert job.status == JobStatus.QUEUED


def test_illegal_transition_message_mentions_both_states():
    job = make_job(JobStatus.COMPLETED)
    with pytest.raises(InvalidTransition, match=r"COMPLETED.*QUEUED"):
        job.transition(JobStatus.QUEUED)


# ── 票 10：機密標記 ──────────────────────────────────────


def test_sensitive_defaults_false():
    assert TranslationJob(job_id="j").sensitive is False


# ── #15：總頁數（進度框「N/M 頁」的 M） ──────────────────────


def test_total_pages_defaults_none():
    job = TranslationJob(job_id="tp1")
    assert job.total_pages is None


def test_total_pages_can_be_set():
    job = TranslationJob(job_id="tp2", total_pages=10)
    assert job.total_pages == 10
