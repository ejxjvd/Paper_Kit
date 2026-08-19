"""JobIntake：任務建立的規則（架構深化候選 1，2026-08-19）。

這個檔案是重構的收益本身。下面每一條規則，過去都只能靠**渲染整頁 NiceGUI**
來驗證——因為它們住在 `app.py:_start_job` 裡，與 `ui.notify(...)` 逐行交錯
（`test_index_page.py` 因此長到 1,675 行）。規則搬進 application 之後，
它們變成一組純粹的輸入／輸出斷言。

機密紅線那一條尤其值得看：它原本在同一個 UI 函式裡被算了兩次（不同參數），
`service.start` 內還有第三次兜底。現在只有一處。
"""

import pytest

from paper_kit.application.job_intake import EngineChoice, IntakeRequest, JobIntake
from paper_kit.domain.translation_job import TranslationJob


class FakeService:
    def __init__(self):
        self.created: list[dict] = []
        self.started: list[dict] = []

    def create_job(self, file_path, **kw):
        self.created.append({"file_path": file_path, **kw})
        job = TranslationJob(job_id=f"job-{len(self.created)}", source_path=str(file_path))
        job.ocr = kw.get("ocr", False)
        return job

    def start(self, job_id, engine, engine_id=None, *, engine_allows_sensitive=None):
        self.started.append(
            {"job_id": job_id, "engine_id": engine_id, "sensitive_ok": engine_allows_sensitive}
        )


class FakeSettings:
    def target_lang(self):
        return "zh-TW"

    def output_dir(self):
        return "/out"

    def selected_glossary_names(self, names):
        return list(names)

    def auto_extract(self):
        return False


class FakeCost:
    def __init__(self, estimate=None):
        self._estimate = estimate

    def estimate_for_pdf(self, engine_id, path, pages=None, glossary=False):
        return self._estimate


class FakeGlossaries:
    def list_glossaries(self):
        return []

    def paths_for(self, names):
        return []


@pytest.fixture(autouse=True)
def _text_layer(monkeypatch):
    """預設「有文字層」——掃描件警告單獨在它自己的測試裡開啟。"""
    monkeypatch.setattr("paper_kit.application.job_intake.has_text_layer", lambda p: True)


def _intake(service=None, cost=None):
    return JobIntake(service or FakeService(), FakeSettings(), cost or FakeCost(), FakeGlossaries())


def _choice(**kw):
    defaults = dict(engine_id="deepseek", engine=object(), allows_sensitive=True, tex_only=False)
    return EngineChoice(**{**defaults, **kw})


def _request(**kw):
    defaults = dict(file_path="/in/paper.pdf", file_name="paper.pdf")
    return IntakeRequest(**{**defaults, **kw})


def test_sensitive_job_rejected_by_incompatible_engine():
    """票 10 紅線：機密文件只准純文字引擎。

    這條規則原本要渲染整頁才驗得到，且在 UI 內被算了兩次。
    """
    service = FakeService()
    result = _intake(service).submit(
        _request(sensitive=True), _choice(engine_id="ppt_vision", allows_sensitive=False)
    )
    assert not result.accepted
    assert "機密" in result.rejection
    assert service.created == [], "被拒的請求不得留下任務"
    assert service.started == [], "被拒的請求不得啟動引擎"


def test_sensitive_job_accepted_by_compatible_engine():
    service = FakeService()
    result = _intake(service).submit(_request(sensitive=True), _choice(allows_sensitive=True))
    assert result.accepted
    assert service.started[0]["sensitive_ok"] is True, "能力宣告要透傳給 service 兜底"


def test_latex_engine_rejects_pdf():
    """票 27：LaTeX 引擎僅適用 .tex——前置擋下，不悄悄換成別支引擎。"""
    service = FakeService()
    result = _intake(service).submit(
        _request(file_name="paper.pdf"), _choice(engine_id="latex", tex_only=True)
    )
    assert not result.accepted
    assert "LaTeX" in result.rejection
    assert service.created == []


def test_latex_engine_accepts_tex():
    result = _intake().submit(
        _request(file_path="/in/paper.tex", file_name="paper.tex"),
        _choice(engine_id="latex", tex_only=True),
    )
    assert result.accepted


def test_invalid_page_range_rejected_before_creating_job():
    """票 07：非法頁碼不得留下半途任務。"""
    service = FakeService()
    result = _intake(service).submit(_request(pages_text="abc"), _choice())
    assert not result.accepted
    assert "頁面範圍" in result.rejection
    assert service.created == []


def test_ocr_on_non_pdf_warns_and_is_ignored():
    """票 14：OCR 只適用 PDF——警告並忽略旗標，但**不阻止**任務建立。

    這是「警告但繼續」的形狀（grilling Q10）：領域判斷，不是 UI 判斷。
    """
    service = FakeService()
    result = _intake(service).submit(
        _request(file_path="/in/deck.pptx", file_name="deck.pptx", ocr=True), _choice()
    )
    assert result.accepted
    assert any("OCR" in w for w in result.warnings)
    assert service.created[0]["ocr"] is False, "旗標必須真的被忽略，不只是警告"


def test_scanned_pdf_warns_but_still_creates(monkeypatch):
    """票 12：無文字層且未勾 OCR → 提示，照常建立（使用者可重試）。"""
    monkeypatch.setattr("paper_kit.application.job_intake.has_text_layer", lambda p: False)
    result = _intake().submit(_request(), _choice())
    assert result.accepted
    assert any("掃描件" in w for w in result.warnings)


def test_estimate_is_frozen_onto_the_job():
    """票 06：估價隨任務凍結——完成後要比對的是「使用者當初看到的」那個數字。"""
    from decimal import Decimal

    from paper_kit.domain.cost_calculator import CostEstimate

    estimate = CostEstimate(
        pages=2, total_tokens=1234, input_tokens=1000, output_tokens=234, cost=Decimal("0.05")
    )
    result = _intake(cost=FakeCost(estimate)).submit(_request(), _choice())
    assert result.job.estimated_tokens == 1234
    assert result.job.estimated_cost == Decimal("0.05")
    assert result.estimate is estimate, "UI 要拿它顯示明細"


def test_accepted_request_starts_the_engine():
    """『任務建立』是一件完整的事，不是一個計算（grilling Q11）。"""
    service = FakeService()
    result = _intake(service).submit(_request(), _choice(engine_id="babeldoc"))
    assert result.accepted
    assert service.started == [
        {"job_id": result.job.job_id, "engine_id": "babeldoc", "sensitive_ok": True}
    ]
