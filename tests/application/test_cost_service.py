"""CostService（application）：成本估算＋實際費用，單價參數化自設定。

期望值獨立來源：手算 literal（頁數×每頁 token、0.77 input ratio、單價）。
"""

import pytest
from decimal import Decimal

from paper_kit.application.cost_service import CostService
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository


def make_service(tmp_path) -> CostService:
    return CostService(SqliteSettingsRepository(tmp_path / "pk.db"))


def test_default_pricing_is_parameterized_per_engine(tmp_path):
    svc = make_service(tmp_path)
    p = svc.pricing_for("deepseek")
    assert p.input_per_1k == Decimal("0.00027")   # USD，2026-08-06 漲價後
    assert p.output_per_1k == Decimal("0.0011")
    assert p.per_page_tokens == 5000


def test_babeldoc_default_pricing_follows_deepseek_backend(tmp_path):
    """票 13：BabelDoc 預設後端＝deepseek-chat → 預設單價比照 DeepSeek（設定頁可改）。"""
    svc = make_service(tmp_path)
    p = svc.pricing_for("babeldoc")
    assert p.input_per_1k == Decimal("0.00027")
    assert p.output_per_1k == Decimal("0.0011")
    assert p.per_page_tokens == 5000


def test_ppt_vision_default_pricing_matches_siliconflow(tmp_path):
    """票 14：PPT 視覺＝SiliconFlow gemma 眼睛 → 預設單價比照 SiliconFlow 視覺。"""
    svc = make_service(tmp_path)
    p = svc.pricing_for("ppt-vision")
    assert p.input_per_1k == Decimal("0.0012")
    assert p.output_per_1k == Decimal("0.0012")
    assert p.per_page_tokens == 5000


def test_pricing_can_be_updated_for_price_raises(tmp_path):
    """DeepSeek 漲價只需改設定（2026-08-06 漲價公告教訓）。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", input_per_1k="0.003", output_per_1k="0.012", per_page_tokens=5000)
    assert svc.pricing_for("deepseek").input_per_1k == Decimal("0.003")


def test_estimate_hand_computed(tmp_path):
    """10 頁 × 5000 = 50,000；in=0.77→38,500；成本 = 38.5×0.002 + 11.5×0.008 = 0.169。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", "0.002", "0.008", 5000)
    est = svc.estimate("deepseek", pages=10)
    assert est.total_tokens == 50_000
    assert est.input_tokens == 38_500
    assert est.output_tokens == 11_500
    assert est.cost == Decimal("0.169")


def test_actual_cost_from_engine_usage(tmp_path):
    """實際用量：in 7127 ×0.002 + out 2219 ×0.008 = 0.014254+0.017752 = 0.032006。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", "0.002", "0.008", 5000)
    job = TranslationJob(job_id="j1", source_path="/in/a.pdf")
    job.result = JobResult(mono_path="/o/a.pdf", input_tokens=7127, output_tokens=2219)
    actual = svc.actual(job, "deepseek")
    assert actual.input_tokens == 7127
    assert actual.output_tokens == 2219
    assert actual.cost == Decimal("0.032006")


def test_estimate_vs_actual_diff(tmp_path):
    """估算與實際差異的顯示（票 06 最後一項 acceptance）。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", "0.002", "0.008", 5000)
    est = svc.estimate("deepseek", pages=10)      # 0.169
    job = TranslationJob(job_id="j1", source_path="/in/a.pdf")
    job.result = JobResult(mono_path="/o/a.pdf", input_tokens=7127, output_tokens=2219)
    actual = svc.actual(job, "deepseek")          # 0.032006
    diff = svc.diff(est, actual)
    assert diff == est.cost - actual.cost
    assert svc.diff_label(est, actual)  # 差異可顯示


def test_free_engine_estimate_is_zero(tmp_path):
    svc = make_service(tmp_path)
    est = svc.estimate("bing", pages=10)
    assert est.cost == Decimal("0")


def test_estimate_negative_pages_rejected(tmp_path):
    """領域的負頁數 guard 穿過 application 包裝仍然有效（spec review 修正）。"""
    svc = make_service(tmp_path)
    with pytest.raises(ValueError):
        svc.estimate("deepseek", pages=-1)


def test_pdf_page_count(tmp_path):
    """估算前拿 PDF 真實頁數（pypdf）。"""
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=612, height=792)
    pdf = tmp_path / "three.pdf"
    with open(pdf, "wb") as f:
        writer.write(f)
    svc = make_service(tmp_path)
    assert svc.pdf_pages(pdf) == 3


def test_estimate_for_pdf_returns_none_on_unparseable(tmp_path):
    """壞檔（非 PDF）→ None，UI 才能靜默跳過。"""
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    assert make_service(tmp_path).estimate_for_pdf("deepseek", bad) is None


def test_estimate_for_pdf_scales_with_pages_range(tmp_path):
    """票 07 review：指定頁面範圍時估價按範圍頁數縮放（規格書 story 4「只為需要的部分付費」）。

    手算（deepseek 預設 0.00027/0.0011、5000/頁、77/23）：
    2 頁 → total 10000, input 7700, output 2300
      cost = 7.7×0.00027 + 2.3×0.0011 = 0.002079 + 0.002530 = 0.004609
    5 頁 → total 25000, input 19250, output 5750
      cost = 19.25×0.00027 + 5.75×0.0011 = 0.0051975 + 0.006325 = 0.0115225
    """
    svc = make_service(tmp_path)
    est = svc.estimate_for_pdf("deepseek", tmp_path / "missing.pdf", pages="1-2")
    assert est is not None
    assert est.pages == 2 and est.total_tokens == 10000
    assert est.input_tokens == 7700 and est.output_tokens == 2300
    assert est.cost == Decimal("0.004609")

    five = svc.estimate_for_pdf("deepseek", tmp_path / "missing.pdf", pages="1-2,4-6")
    assert five.total_tokens == 25000
    assert five.cost == Decimal("0.0115225")


def test_usage_label_shows_estimate_vs_actual(tmp_path):
    """完成任務的成本標籤：估算 vs 實際＋用量（用上傳時存的估算——非幽靈重算）。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", "0.002", "0.008", 5000)
    job = TranslationJob(job_id="j1", source_path="/in/a.pdf", engine_id="deepseek")
    job.estimated_cost = Decimal("0.169")  # _start_job 在上傳時存的
    job.result = JobResult(mono_path="/o/a.pdf", input_tokens=7127, output_tokens=2219)
    label = svc.usage_label(job)
    assert "估 $0.169" in label and "實際" in label
    assert "7,127 in / 2,219 out" in label


def test_usage_label_recomputes_when_no_stored_estimate(tmp_path):
    """無 stored 估算（舊任務）→ 回退即時重估（真實 PDF）。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", "0.002", "0.008", 5000)
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    pdf = tmp_path / "one.pdf"
    with open(pdf, "wb") as f:
        writer.write(f)
    job = TranslationJob(job_id="j1", source_path=str(pdf), engine_id="deepseek")
    job.result = JobResult(mono_path="/o/a.pdf", input_tokens=7127, output_tokens=2219)
    label = svc.usage_label(job)
    assert "估" in label and "實際" in label


def test_usage_label_unreadable_actual_falls_back_to_usage(tmp_path):
    """malformed pricing row 讓 actual() 失敗 → 只顯示用量（spec review 修正）。"""
    svc = make_service(tmp_path)
    svc.set_pricing("deepseek", "not-a-number", "0.008", 5000)
    job = TranslationJob(job_id="j1", source_path="/in/a.pdf", engine_id="deepseek")
    job.result = JobResult(mono_path="/o/a.pdf", input_tokens=7127, output_tokens=2219)
    assert svc.usage_label(job).startswith("實際用量")


def test_usage_label_without_engine_only_shows_usage(tmp_path):
    svc = make_service(tmp_path)
    job = TranslationJob(job_id="j1", source_path="/in/a.pdf")
    job.result = JobResult(mono_path="/o/a.pdf", input_tokens=7127, output_tokens=2219)
    assert svc.usage_label(job).startswith("實際用量")


def test_usage_label_without_result_is_none(tmp_path):
    job = TranslationJob(job_id="j1", source_path="/in/a.pdf")
    assert make_service(tmp_path).usage_label(job) is None
