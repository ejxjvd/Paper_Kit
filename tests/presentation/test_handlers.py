"""handlers（presentation 薄層 viewmodel）：純函式可測，不 import nicegui。

驗證：狀態→徽章/進度/下載與預覽 URL 對映；URL 以引擎實際產出路徑為準
（靜態檔伺服基準 /files/<job_id>/<檔名>）。
"""

import pytest

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.presentation.handlers import STATUS_LABELS, JobCardView, build_job_card


def completed_job(job_id: str = "abc123") -> TranslationJob:
    job = TranslationJob(
        job_id=job_id,
        source_path="/outputs/abc123/paper.pdf",
        status=JobStatus.COMPLETED,
    )
    job.result = JobResult(
        mono_path="/outputs/abc123/paper.zh.mono.pdf",
        dual_path="/outputs/abc123/paper.zh.dual.pdf",
        input_tokens=7127,
        output_tokens=2219,
    )
    return job


# ── 各狀態對映 ───────────────────────────────────────────────────────


def test_queued_job_shows_waiting_and_indeterminate():
    job = TranslationJob(job_id="q1", source_path="/outputs/q1/a.pdf")
    view = build_job_card(job)
    assert view.status_label == "排隊中"
    assert view.is_running
    assert view.progress is None
    assert view.mono_url is None and view.dual_url is None and view.preview_url is None


def test_translating_job_shows_in_progress():
    job = TranslationJob(job_id="t1", source_path="/outputs/t1/a.pdf")
    job.transition(JobStatus.TRANSLATING)
    view = build_job_card(job)
    assert view.status_label == "翻譯中"
    assert view.is_running
    assert view.progress is None  # 引擎尚無顆粒度進度 → 不確定進度


def test_completed_job_links_to_outputs():
    view = build_job_card(completed_job())
    assert view.status_label == "完成"
    assert not view.is_running
    assert view.progress == 1.0
    assert view.mono_url == "/files/abc123/paper.zh.mono.pdf"
    assert view.dual_url == "/files/abc123/paper.zh.dual.pdf"
    assert view.preview_url == view.mono_url  # 預覽開 mono


def test_completed_job_respects_custom_files_base():
    view = build_job_card(completed_job(), files_base="/outputs-served")
    assert view.mono_url.startswith("/outputs-served/abc123/")


def test_failed_job_shows_error():
    job = TranslationJob(job_id="f1", source_path="/outputs/f1/a.pdf")
    job.transition(JobStatus.TRANSLATING)
    job.transition(JobStatus.FAILED)
    job.error = "翻譯逾時（超過 600 秒無回應）"
    view = build_job_card(job)
    assert view.status_label == "失敗"
    assert not view.is_running
    assert view.error == "翻譯逾時（超過 600 秒無回應）"


def test_cancelled_job_label():
    job = TranslationJob(job_id="c1", source_path="/outputs/c1/a.pdf")
    job.transition(JobStatus.TRANSLATING)
    job.transition(JobStatus.CANCELLED)
    assert build_job_card(job).status_label == "已取消"


def test_all_statuses_have_traditional_chinese_label():
    for status in JobStatus:
        assert STATUS_LABELS[status], f"{status} 缺少中文標籤"


def test_file_name_comes_from_source():
    view = build_job_card(completed_job())
    assert view.file_name == "paper.pdf"


def test_usage_label_passes_through_to_view():
    """票 06：成本標籤由 app.py 用 CostService 算好後傳入（handlers 保持純函式）。"""
    view = build_job_card(completed_job(), usage_label="成本：估 ¥0.169 → 實際 ¥0.032")
    assert view.usage_label == "成本：估 ¥0.169 → 實際 ¥0.032"
