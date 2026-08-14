"""handlers（presentation 薄層 viewmodel）：純函式可測，不 import nicegui。

驗證：狀態→徽章/進度/下載與預覽 URL 對映；URL 以引擎實際產出路徑為準
（靜態檔伺服基準 /files/<job_id>/<檔名>）。
"""

import zipfile

import pytest

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.presentation.handlers import (
    STATUS_LABELS,
    JobCardView,
    build_job_card,
    progress_label,  # #15：進度框文字（「完成 100% · 10/10 頁」）
)


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


def test_translating_job_passes_engine_progress_through():
    """#72：引擎有顆粒度進度時，翻譯中任務顯示確定進度（非 indeterminate）。"""
    job = TranslationJob(job_id="t2", source_path="/outputs/t2/a.pdf")
    job.transition(JobStatus.TRANSLATING)
    job.progress = 0.4
    view = build_job_card(job)
    assert view.progress == 0.4
    assert view.is_running


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


def test_latex_warning_flag_passthrough():
    """v0.1.9.5：LaTeX 密集偵測結果透傳到 viewmodel（UI 顯示 ⚠️ 標注）。"""
    assert not build_job_card(completed_job()).latex_warning  # 預設不標注
    view = build_job_card(completed_job(), latex_warning=True)
    assert view.latex_warning


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


def test_estimated_label_passes_through_to_view():
    """2026-08-13：預估標籤由 app 層算好傳入（handlers 純函式不碰 CostService）。"""
    job = TranslationJob(job_id="e1", source_path="/outputs/e1/a.pdf")
    view = build_job_card(
        job, estimated_label="估算 ≈ 50,000 tokens ≈ US$0.1690（≈NT$5.41）"
    )
    assert view.estimated_label == "估算 ≈ 50,000 tokens ≈ US$0.1690（≈NT$5.41）"
    # 未傳入（舊呼叫端／歷史頁）→ None，不再內部組字
    assert build_job_card(job).estimated_label is None


# ── 票 10：機密標記顯示 ──────────────────────────────────


def test_sensitive_job_carries_flag_to_card():
    job = TranslationJob(job_id="s1", source_path="/outputs/s1/a.pdf", sensitive=True)
    view = build_job_card(job)
    assert view.sensitive is True


def test_plain_job_card_not_sensitive():
    view = build_job_card(TranslationJob(job_id="p1", source_path="/outputs/p1/a.pdf"))
    assert view.sensitive is False


def test_ocr_job_carries_flag_to_card():
    job = TranslationJob(job_id="o1", source_path="/outputs/o1/a.pdf", ocr=True)
    view = build_job_card(job, files_base="/files")
    assert view.ocr is True


# ── 票 26：命中快取標記顯示 ────────────────────────────────


def test_cache_hit_job_marks_from_cache():
    job = completed_job()
    job.result = JobResult(
        mono_path="/outputs/abc123/paper.zh.mono.pdf",
        dual_path="/outputs/abc123/paper.zh.dual.pdf",
        from_cache=True,  # 票 24：快取命中（引擎未呼叫）
    )
    view = build_job_card(job)
    assert view.from_cache is True


def test_completed_job_defaults_not_from_cache():
    view = build_job_card(completed_job())
    assert view.from_cache is False


def test_no_result_job_not_from_cache():
    view = build_job_card(TranslationJob(job_id="n1", source_path="/outputs/n1/a.pdf"))
    assert view.from_cache is False


def test_plain_job_card_not_ocr():
    job = TranslationJob(job_id="p1", source_path="/outputs/p1/a.pdf")
    view = build_job_card(job, files_base="/files")
    assert view.ocr is False


# ── 票 18：批量下載 zip 打包（純函式，路由只是薄殼） ──────────────────

def _completed_with_files(tmp_path, job_id: str, file_name: str) -> TranslationJob:
    job = completed_job(job_id)
    out = tmp_path / job_id
    out.mkdir()
    mono = out / f"{file_name}.zh.mono.pdf"
    dual = out / f"{file_name}.zh.dual.pdf"
    mono.write_bytes(b"mono-content")
    dual.write_bytes(b"dual-content")
    job.result = JobResult(
        mono_path=str(mono), dual_path=str(dual), input_tokens=0, output_tokens=0
    )
    return job


def test_batch_zip_mono_contains_each_selected_job_mono(tmp_path):
    """批量下載僅譯文：zip 內含勾選任務的 mono 檔（arcname 帶 job_id 前綴防同名衝突）。"""
    from paper_kit.presentation.handlers import build_batch_zip

    jobs = [
        _completed_with_files(tmp_path, "a1b2c3d4", "paper"),
        _completed_with_files(tmp_path, "e5f6g7h8", "paper"),  # 同名不同任務
    ]
    dest = tmp_path / "zip"
    dest.mkdir()

    zip_path = build_batch_zip(jobs, "mono", dest)

    assert zip_path is not None and zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
        assert names == ["a1b2c3d4-paper.zh.mono.pdf", "e5f6g7h8-paper.zh.mono.pdf"]
        assert zf.read("a1b2c3d4-paper.zh.mono.pdf") == b"mono-content"


def test_batch_zip_dual_contains_each_selected_job_dual(tmp_path):
    """批量下載雙語（dual 不可退化——兩鍵獨立、都要有）。"""
    from paper_kit.presentation.handlers import build_batch_zip

    jobs = [_completed_with_files(tmp_path, "a1b2c3d4", "paper")]
    dest = tmp_path / "zip"
    dest.mkdir()

    zip_path = build_batch_zip(jobs, "dual", dest)

    assert zip_path is not None
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["a1b2c3d4-paper.zh.dual.pdf"]
        assert zf.read("a1b2c3d4-paper.zh.dual.pdf") == b"dual-content"


def test_batch_zip_skips_jobs_without_result(tmp_path):
    """未完成/無產出任務跳過；全無可打包 → 回傳 None（UI 提示）。"""
    from paper_kit.presentation.handlers import build_batch_zip

    done = _completed_with_files(tmp_path, "a1b2c3d4", "paper")
    queued = TranslationJob(job_id="q0q0q0q0", source_path="/x.pdf", status=JobStatus.QUEUED)
    dest = tmp_path / "zip"
    dest.mkdir()

    zip_path = build_batch_zip([done, queued], "mono", dest)
    assert zip_path is not None
    with zipfile.ZipFile(zip_path) as zf:
        assert zf.namelist() == ["a1b2c3d4-paper.zh.mono.pdf"]

    assert build_batch_zip([queued], "mono", dest) is None


# ── #15：進度框顯示 N/M 頁＋百分比（total_pages 透傳＋純函式組字） ────


def test_total_pages_flows_to_view():
    job = TranslationJob(job_id="tp1", source_path="/out/tp1/a.pdf", total_pages=10)
    assert build_job_card(job).total_pages == 10


def test_total_pages_defaults_none_in_view():
    view = build_job_card(TranslationJob(job_id="tp2", source_path="/out/tp2/a.pdf"))
    assert view.total_pages is None


def test_progress_label_completed_with_pages():
    job = completed_job()
    job.total_pages = 10  # JobCardView 是 frozen dataclass——由 job 端透傳
    assert progress_label(build_job_card(job)) == "完成 100% · 10/10 頁"


def test_progress_label_completed_without_pages():
    assert progress_label(build_job_card(completed_job())) == "完成 100%"


def test_progress_label_translating_determinate():
    job = TranslationJob(job_id="tp3", source_path="/out/tp3/a.pdf", total_pages=10)
    job.transition(JobStatus.TRANSLATING)
    job.progress = 0.4
    assert progress_label(build_job_card(job)) == "翻譯中 40% · 4/10 頁"


def test_progress_label_translating_indeterminate():
    job = TranslationJob(job_id="tp4", source_path="/out/tp4/a.pdf", total_pages=10)
    job.transition(JobStatus.TRANSLATING)
    assert progress_label(build_job_card(job)) == "翻譯中… · 共 10 頁"


def test_progress_label_translating_no_pages_fallback():
    """舊任務（無 total_pages）→ 百分比照顯示、頁數省略。"""
    job = TranslationJob(job_id="tp5", source_path="/out/tp5/a.pdf")
    job.transition(JobStatus.TRANSLATING)
    job.progress = 0.25
    assert progress_label(build_job_card(job)) == "翻譯中 25%"


def test_progress_label_queued_none():
    job = TranslationJob(job_id="tp6", source_path="/out/tp6/a.pdf", total_pages=10)
    assert progress_label(build_job_card(job)) is None


# ── #27：頁數欄「N/M 頁」（翻譯頁數／PDF 總頁數） ─────────────


def test_pages_label_selected_pages_summary():
    """#27：挑 2 頁（29,30／PDF 58 頁）→ 歷史頁顯示「2/58 頁」（先前錯顯示「29,30」）。"""
    job = TranslationJob(
        job_id="p1", source_path="/out/p1/a.pdf",
        pages="29,30", total_pages=2, pdf_pages=58,
    )
    assert build_job_card(job).pages_label == "2/58 頁"


def test_pages_label_full_document_summary():
    """全文翻譯 → 「58/58 頁」（翻譯頁數＝PDF 總頁數）。"""
    job = TranslationJob(
        job_id="p2", source_path="/out/p2/a.pdf", total_pages=58, pdf_pages=58,
    )
    assert build_job_card(job).pages_label == "58/58 頁"


def test_pages_label_legacy_job_falls_back():
    """舊任務（無 total_pages/pdf_pages）→ 維持既有「全文」／選取頁碼。"""
    assert (
        build_job_card(TranslationJob(job_id="p3", source_path="/out/p3/a.pdf")).pages_label
        == "全文"
    )
    job = TranslationJob(job_id="p4", source_path="/out/p4/a.pdf", pages="1-2")
    assert build_job_card(job).pages_label == "1-2"


def test_pages_label_translated_only():
    """有翻譯頁數無 PDF 總頁數 → 「2 頁」。"""
    job = TranslationJob(job_id="p5", source_path="/out/p5/a.pdf", pages="1,2", total_pages=2)
    assert build_job_card(job).pages_label == "2 頁"
