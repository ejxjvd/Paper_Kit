"""票 24 整合：JobService._run 快取攔截（翻譯前查、完成後寫）。

紅→綠 slice 3+4：引擎呼叫數（fake 側信道）＋狀態轉換＋輸出檔存在＋from_cache。
"""

import time
from pathlib import Path

from paper_kit.application.job_service import JobService
from paper_kit.application.ocr import OcrService
from paper_kit.application.ports import EngineError
from paper_kit.application.translation_cache import TranslationCache
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository


class CountingEngine:
    """側信道：呼叫次數＋呼叫收到的任務（不 import 測試間 FakeEngine）。"""

    def __init__(self, mono: Path, dual: Path | None = None, error: str | None = None,
                 delay: float = 0.0, honor_cancel: bool = True):
        self._mono, self._dual, self._error, self._delay = mono, dual, error, delay
        self._honor_cancel = honor_cancel
        self.calls = 0
        self.received: list[TranslationJob] = []
        self.cancelled = False

    def translate(self, job: TranslationJob) -> JobResult:
        self.calls += 1
        self.received.append(job)
        time.sleep(self._delay)
        if self.cancelled and self._honor_cancel:
            raise EngineError("已取消")
        if self._error:
            raise EngineError(self._error)
        return JobResult(
            mono_path=str(self._mono), dual_path=str(self._dual) if self._dual else None
        )

    def cancel(self) -> None:
        self.cancelled = True


def make_service(tmp_path: Path, engine) -> tuple[JobService, TranslationCache]:
    repo = InMemoryJobRepository()
    cache = TranslationCache(cache_dir=tmp_path / "cache")
    service = JobService(jobs=repo, outputs_dir=tmp_path / "outputs", cache=cache)
    return service, cache


def upload_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4 shared fingerprint content")
    return p


def run_job(service: JobService, engine, tmp_path: Path, **create_kwargs):
    """create→start→wait→回傳任務（每任務引擎實例共用計數）。"""
    upload = upload_pdf(tmp_path)
    job = service.create_job(upload_path=upload, **create_kwargs)
    service.start(job.job_id, engine, engine_id="deepseek", engine_allows_sensitive=True)
    service.wait(job.job_id)
    return job


def test_second_same_input_hits_cache_no_engine_call(tmp_path: Path):
    engine = CountingEngine(mono=tmp_path / "paper.zh-TW.mono.pdf", dual=tmp_path / "paper.zh-TW.dual.pdf")
    engine._mono.write_bytes(b"MONO"); engine._dual.write_bytes(b"DUAL")
    service, _ = make_service(tmp_path, engine)

    job1 = run_job(service, engine, tmp_path)
    job2 = run_job(service, engine, tmp_path)

    assert job1.status is JobStatus.COMPLETED and job1.result.from_cache is False
    assert job2.status is JobStatus.COMPLETED
    assert engine.calls == 1, "同指紋第二次任務引擎不得被呼叫"
    assert job2.result.from_cache is True
    # 快取檔複製進第二次任務目錄、可用既有機制下載
    assert Path(job2.result.mono_path).exists()
    assert Path(job2.result.mono_path).parent.parent == tmp_path / "outputs"


def test_parameter_change_misses_cache(tmp_path: Path):
    engine = CountingEngine(mono=tmp_path / "m.pdf")
    engine._mono.write_bytes(b"MONO")
    service, _ = make_service(tmp_path, engine)

    run_job(service, engine, tmp_path)
    run_job(service, engine, tmp_path, target_lang="en")  # 改語言

    assert engine.calls == 2
    assert service.list_jobs()[1].result.from_cache is False


def test_glossary_content_change_misses_cache(tmp_path: Path):
    engine = CountingEngine(mono=tmp_path / "m.pdf")
    engine._mono.write_bytes(b"MONO")
    service, _ = make_service(tmp_path, engine)
    g1 = tmp_path / "g1.txt"; g1.write_text("LLM=大語言模型", encoding="utf-8")

    job1 = service.create_job(upload_path=upload_pdf(tmp_path))
    job1.glossary_files = [str(g1)]
    service.start(job1.job_id, engine, engine_id="deepseek", engine_allows_sensitive=True)
    service.wait(job1.job_id)

    g2 = tmp_path / "g2.txt"; g2.write_text("LLM=大型語言模型", encoding="utf-8")
    job2 = service.create_job(upload_path=upload_pdf(tmp_path))
    job2.glossary_files = [str(g2)]
    service.start(job2.job_id, engine, engine_id="deepseek", engine_allows_sensitive=True)
    service.wait(job2.job_id)

    assert engine.calls == 2, "術語表內容不同 → 不命中"


def test_failed_job_not_written_to_cache(tmp_path: Path):
    good = CountingEngine(mono=tmp_path / "m.pdf"); good._mono.write_bytes(b"MONO")
    failing = CountingEngine(mono=tmp_path / "m.pdf", error="translate blew up")
    service, _ = make_service(tmp_path, failing)

    job1 = run_job(service, failing, tmp_path)
    assert job1.status is JobStatus.FAILED

    # 同輸入改好引擎重跑 → 必須真呼叫（失敗結果不得進快取）
    job2 = run_job(service, good, tmp_path)
    assert job2.status is JobStatus.COMPLETED
    assert good.calls == 1 and job2.result.from_cache is False


def test_cancelled_job_not_written_to_cache(tmp_path: Path):
    engine = CountingEngine(mono=tmp_path / "m.pdf", delay=0.3)
    engine._mono.write_bytes(b"MONO")
    service, _ = make_service(tmp_path, engine)

    job1 = service.create_job(upload_path=upload_pdf(tmp_path))
    service.start(job1.job_id, engine, engine_id="deepseek", engine_allows_sensitive=True)
    # 等 worker 進入 TRANSLATING（QUEUED 直接 cancel 是非法轉換——領域狀態機）
    for _ in range(200):
        if service.list_jobs()[0].status is JobStatus.TRANSLATING:
            break
        time.sleep(0.01)
    service.cancel(job1.job_id)
    service.wait(job1.job_id)
    assert job1.status is JobStatus.CANCELLED

    # 獨立引擎實例重跑（同實例的 cancelled 旗標會讓 job2 直接失敗——測試污染）
    job2_engine = CountingEngine(mono=tmp_path / "m.pdf")
    job2_engine._mono.write_bytes(b"MONO")
    job2 = run_job(service, job2_engine, tmp_path)  # 同輸入重跑
    assert engine.calls + job2_engine.calls == 2, "取消結果不得進快取（重跑要真呼叫）"
    assert job2.status is JobStatus.COMPLETED


def test_clear_cache_then_rerun_calls_engine(tmp_path: Path):
    engine = CountingEngine(mono=tmp_path / "m.pdf")
    engine._mono.write_bytes(b"MONO")
    service, cache = make_service(tmp_path, engine)

    run_job(service, engine, tmp_path)
    cache.clear()
    job2 = run_job(service, engine, tmp_path)

    assert engine.calls == 2 and job2.result.from_cache is False


def test_enabled_false_skips_cache_entirely(tmp_path: Path):
    engine = CountingEngine(mono=tmp_path / "m.pdf")
    engine._mono.write_bytes(b"MONO")
    service, cache = make_service(tmp_path, engine)
    cache.enabled = False  # 設定頁關閉開關（票 25 會持久化）

    run_job(service, engine, tmp_path)
    run_job(service, engine, tmp_path)

    assert engine.calls == 2, "快取關閉：不查不寫"


def test_sensitive_job_cached_locally(tmp_path: Path):
    """敏感文件照常快取（本地；紅線只限制上雲）。"""
    engine = CountingEngine(mono=tmp_path / "m.pdf")
    engine._mono.write_bytes(b"MONO")
    service, _ = make_service(tmp_path, engine)

    job1 = run_job(service, engine, tmp_path, sensitive=True)
    job2 = run_job(service, engine, tmp_path, sensitive=True)

    assert job1.status is JobStatus.COMPLETED
    assert job2.status is JobStatus.COMPLETED
    assert engine.calls == 1 and job2.result.from_cache is True


def test_ocr_job_hits_cache_when_ocr_passthrough(tmp_path: Path):
    """掃描件：OCR 前置回 None（有文字層）→ 指紋相同 → 重翻命中（user story 9）。"""
    class PassthroughOcr(OcrService):
        def __init__(self):
            pass  # 不接 OcrPort——測試 stub（只覆蓋 ensure_text_layer）

        def ensure_text_layer(self, pdf: Path) -> None:
            return None  # 已有文字層，不動

    engine = CountingEngine(mono=tmp_path / "m.pdf")
    engine._mono.write_bytes(b"MONO")
    repo = InMemoryJobRepository()
    cache = TranslationCache(cache_dir=tmp_path / "cache")
    service = JobService(
        jobs=repo, outputs_dir=tmp_path / "outputs", ocr=PassthroughOcr(), cache=cache
    )

    run_job(service, engine, tmp_path, ocr=True)
    job2 = run_job(service, engine, tmp_path, ocr=True)

    assert engine.calls == 1 and job2.result.from_cache is True
