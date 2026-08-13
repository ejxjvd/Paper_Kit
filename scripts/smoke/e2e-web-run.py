"""WEB 端實機跑測（使用者要求）：真實主頁 handler 路徑＋真實引擎＋真實 API＋真實 DB key。

流程：user_simulation 開真實主頁 → handle_uploads 上傳真 PDF（走真實
on_upload → _start_job）→ 不 monkeypatch resolve_engine（真實
Pdf2zhNextAdapter → 真實 pdf2zh_next → 真實 SiliconFlow API）→
等任務 COMPLETED → 驗證輸出 PDF。
（需先跑 e2e-download.sh 準備 PDF；REAL_DB/PDF/OUT 依環境調整）
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from nicegui import ui
from nicegui.elements.upload_files import SmallFileUpload
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _index_page

PDF = Path("/tmp/paperkit-e2e/bose-hubbard.pdf")
OUT = Path("/tmp/paperkit-e2e/outputs")
REAL_DB = Path("/home/qaref/.paper_kit/paper_kit.db")


async def main() -> int:
    settings = SettingsService(SqliteSettingsRepository(REAL_DB))
    service = JobService(jobs=InMemoryJobRepository(), outputs_dir=OUT)
    cost = CostService(SqliteSettingsRepository(REAL_DB))
    glossaries = GlossaryService(GlossaryRepository(Path("/tmp/paperkit-e2e/glossaries")))

    print(f"engine_id={settings.engine_id()} target_lang={settings.target_lang()}")
    assert settings.engine_id() == "siliconflow", "設定頁引擎不是 siliconflow"

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        upload_el = next(iter(user.find(ui.upload).elements))
        print(f"== 上傳 {PDF.name}（{PDF.stat().st_size} bytes）==")
        await upload_el.handle_uploads([
            SmallFileUpload(
                name=PDF.name,
                content_type="application/pdf",
                _data=PDF.read_bytes(),
            ),
        ])

        deadline = asyncio.get_event_loop().time() + 480
        job = None
        while True:
            jobs = service.list_jobs()
            if jobs:
                job = jobs[0]
                print(f"status={job.status}", flush=True)
                if job.status in ("COMPLETED", "FAILED", "CANCELLED"):
                    break
            if asyncio.get_event_loop().time() > deadline:
                print("TIMEOUT 480s")
                return 2
            await asyncio.sleep(3)

        if job is None:
            print("沒有任務被建立")
            return 1
        if job.status != "COMPLETED":
            print(f"失敗：{job.error}")
            return 1

        pdfs = sorted(OUT.rglob("*.pdf"))
        print(f"== 輸出 PDF：{len(pdfs)} 個 ==")
        for p in pdfs:
            print("  ", p.relative_to(OUT), p.stat().st_size, "bytes")
        mono = next((p for p in pdfs if ".zh.mono" in p.name), None)
        if mono is None:
            print("缺 mono PDF！")
            return 1
        print(f"== 成功：{mono.name} ==")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
