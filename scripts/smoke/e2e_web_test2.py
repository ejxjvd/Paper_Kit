"""WEB 端實機跑測 v2：真實主頁＋真實引擎＋真實 API＋真實 DB key。

v1（e2e_web_test.py）480s 逾時但翻譯產物已產出——本版把觀察做進測試：
1) 狀態變化才印（不洗版）2) 每 15s 印子程序樹（確認產檔後子程序是否還在）
3) 逾時 dump job 全欄位＋proc 樹 4) 逾時 360s。輸出由 bash 重導存檔。

跑：pytest scripts/smoke/e2e_web_test2.py -s 2>&1 | tee /tmp/paperkit-e2e/e2e-run2.log
（需先跑 e2e-download.sh 準備 PDF；REAL_DB/PDF/OUT 依環境調整）
"""
import asyncio
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pytest
from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.translation_job import JobStatus
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _index_page

PDF = Path("/tmp/paperkit-e2e/bose-hubbard.pdf")
OUT = Path("/tmp/paperkit-e2e/outputs")
REAL_DB = Path("/home/qaref/.paper_kit/paper_kit.db")


def proc_tree() -> str:
    """子程序樹快照（引擎 hang 判定用）。"""
    ps = subprocess.run(
        ["ps", "-eo", "pid,ppid,etime,cmd"], capture_output=True, text=True
    )
    lines = [
        l for l in ps.stdout.splitlines()
        if any(k in l for k in ("pdf2zh", "babeldoc", "uv", "python"))
        and "grep" not in l and "claude" not in l
    ]
    return "\n".join(lines) if lines else "(無翻譯相關程序)"


@pytest.mark.asyncio
async def test_real_engine_web_e2e():
    settings = SettingsService(SqliteSettingsRepository(REAL_DB))
    service = JobService(jobs=InMemoryJobRepository(), outputs_dir=OUT)
    cost = CostService(SqliteSettingsRepository(REAL_DB))
    glossaries = GlossaryService(GlossaryRepository(Path("/tmp/paperkit-e2e/glossaries")))

    print(f"\nengine_id={settings.engine_id()} target_lang={settings.target_lang()}", flush=True)
    print(f"api_key 長度={len(settings.api_key('siliconflow') or '')}", flush=True)
    assert settings.engine_id() == "siliconflow", "設定頁引擎不是 siliconflow"

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        upload_el = next(iter(user.find(ui.upload).elements))
        print(f"== 上傳 {PDF.name}（{PDF.stat().st_size} bytes）==", flush=True)
        await upload_el.handle_uploads([
            SmallFileUpload(
                name=PDF.name,
                content_type="application/pdf",
                _data=PDF.read_bytes(),
            ),
        ])

        t0 = asyncio.get_event_loop().time()
        deadline = t0 + 240
        job = None
        last_status = None
        last_proc_at = 0.0
        while True:
            jobs = service.list_jobs()
            if jobs:
                job = jobs[0]
                if job.status != last_status:
                    print(
                        f"[{int(asyncio.get_event_loop().time()-t0):>3}s] status={job.status}",
                        flush=True,
                    )
                    last_status = job.status
                    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                        print(f"== 終態：{job.status}", flush=True)
                        if job.status is JobStatus.FAILED:
                            print(f"error={job.error}", flush=True)
                        break
            now = asyncio.get_event_loop().time()
            if now - last_proc_at >= 15:
                print(
                    f"[{int(now-t0):>3}s] procs: {proc_tree()}",
                    flush=True,
                )
                last_proc_at = now
            if now > deadline:
                print("== TIMEOUT dump ==", flush=True)
                print(f"job={job}", flush=True)
                print(f"status={job.status if job else None} error={job.error if job else None}", flush=True)
                print(f"engine_id={job.engine_id if job else None} result={job.result if job else None}", flush=True)
                print(f"threads={list(service._threads.keys())} engines={list(service._engines.keys())}", flush=True)
                print(f"procs: {proc_tree()}", flush=True)
                raise AssertionError("逾時 360s")
            await asyncio.sleep(1)

        assert job is not None, "沒有任務被建立"
        assert job.status is JobStatus.COMPLETED, f"任務失敗：{job.error}"

        pdfs = sorted(OUT.rglob("*.pdf"))
        print(f"== 輸出 PDF：{len(pdfs)} 個 ==", flush=True)
        for p in pdfs:
            print("  ", p.relative_to(OUT), p.stat().st_size, "bytes", flush=True)
        mono = next((p for p in pdfs if ".mono.pdf" in p.name), None)
        assert mono is not None, "缺 mono PDF"
        print(f"== 實機成功：{mono.name} ==", flush=True)
