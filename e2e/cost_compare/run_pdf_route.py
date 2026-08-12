"""e2e 成本比較（票 15）：PDF 路線（pdf2zh_next + DeepSeek）真實 API 翻譯。

對照對象：e2e/attention/run_real_api.py 的 LaTeX 路線（同一篇論文、
同一 DeepSeek 端點）——驗證「源碼路線 3-5× 省」的成本論證。

用法（WSL）：
    cd /mnt/c/Users/qaref/Code/Paper_Kit
    .venv/bin/python e2e/cost_compare/run_pdf_route.py

產出：e2e/cost_compare/PDF_ROUTE.json（tokens、耗時、成本）＋
    translation/ 下的 mono/dual PDF（pdf2zh 產物）。失敗 exit 非 0。
"""

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))

from paper_kit.application.settings_service import SettingsService  # noqa: E402
from paper_kit.domain.translation_job import TranslationJob  # noqa: E402
from paper_kit.infrastructure.pdf2zh_next_adapter import (  # noqa: E402
    EngineConfig,
    Pdf2zhNextAdapter,
)
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository  # noqa: E402

PDF_SOURCE = HERE.parent / "attention" / "original.pdf"  # arXiv 原論文（8 頁）


def main() -> int:
    repo = SqliteSettingsRepository(Path.home() / ".paper_kit" / "paper_kit.db")
    service = SettingsService(repo)
    api_key = service.api_key("deepseek")
    if not api_key:
        print("❌ 缺 deepseek API key（SQLite 無值）")
        return 1
    print(f"✅ key 已讀取（{len(api_key)} 字元，回讀不顯示內容）")

    work = HERE / "translation"
    work.mkdir(parents=True, exist_ok=True)

    adapter = Pdf2zhNextAdapter(
        EngineConfig(provider="deepseek", api_key=api_key, timeout_seconds=1800)
    )
    job = TranslationJob(
        job_id="cost-pdf",
        source_path=str(PDF_SOURCE),
        target_lang="zh-TW",
        engine_id="pdf",
    )

    started = time.monotonic()
    try:
        result = adapter.translate(job)
    except Exception as exc:  # noqa: BLE001——harness 回報引擎失敗
        print(f"❌ PDF 路線翻譯失敗：{exc}")
        return 1
    elapsed = time.monotonic() - started

    # 成本（同 LaTeX 路線計價：deepseek-chat）
    from decimal import Decimal

    in_cost = Decimal(result.input_tokens) * Decimal("0.00027") / 1000
    out_cost = Decimal(result.output_tokens) * Decimal("0.0011") / 1000
    usd = in_cost + out_cost
    ntd = usd * Decimal("32")

    report = {
        "route": "pdf（pdf2zh_next + DeepSeek）",
        "source": str(PDF_SOURCE.relative_to(REPO)),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "elapsed_s": round(elapsed, 1),
        "cost_usd": str(usd),
        "cost_ntd_at_32": str(ntd),
        "mono": result.mono_path,
        "dual": result.dual_path,
    }
    (HERE / "PDF_ROUTE.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print("═══ PDF 路線報告（cost_compare/PDF_ROUTE.json）═══")
    print(f"  tokens：{result.input_tokens} in / {result.output_tokens} out")
    print(f"  成本：${usd:.4f} ≈ NT${ntd:.2f}（匯率 32）")
    print(f"  耗時：{elapsed:.1f}s")
    print(f"  mono：{result.mono_path}")
    print(f"  dual：{result.dual_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
