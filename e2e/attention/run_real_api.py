"""e2e 真論文實測 Level 2：真實 DeepSeek API 全鏈翻譯 + 編譯 + 驗證 + 成本記錄。

用法（WSL）：
    cd /mnt/c/Users/qaref/Code/Paper_Kit
    .venv/bin/python e2e/attention/run_real_api.py

管線：ms_single.tex（已合併）→ LatexAdapter（真實 deepseek-chat，key 讀自
本機 SQLite ~/.paper_kit/paper_kit.db，不印出）→ xelatex 編譯 → pymupdf
驗證（頁數／中文渲染／公式樣本／無 \\PKP 殘留）→ 成本計算 → REPORT.md。

失敗時 exit code 非 0，最後一則驗證失敗訊息為根因（診斷回饋迴路）。
"""

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "src"))

from paper_kit.application.settings_service import SettingsService  # noqa: E402
from paper_kit.infrastructure.latex_adapter import LatexAdapter, LatexConfig  # noqa: E402
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository  # noqa: E402
from paper_kit.infrastructure.tex_compiler import TeXCompiler  # noqa: E402
from paper_kit.domain.translation_job import TranslationJob  # noqa: E402


def main() -> int:
    failures: list[str] = []
    started = time.monotonic()

    # 1. key（不印出值）；latex 槽位為準，缺則共用 deepseek 槽位（同端點）
    repo = SqliteSettingsRepository(Path.home() / ".paper_kit" / "paper_kit.db")
    service = SettingsService(repo)
    api_key = service.api_key("latex") or service.api_key("deepseek")
    if not api_key:
        print("❌ 缺 latex API key（SQLite 無值）")
        return 1
    print(f"✅ key 已讀取（{len(api_key)} 字元，回讀不顯示內容）")

    # 2. 翻譯
    adapter = LatexAdapter(LatexConfig(api_key=api_key))
    job = TranslationJob(
        job_id="e2e-real",
        source_path=str(HERE / "ms_single.tex"),
        target_lang="zh-TW",
        engine_id="latex",
    )
    try:
        result = adapter.translate(job)
    except Exception as e:
        print(f"❌ 翻譯失敗：{e}")
        return 1
    elapsed_translate = time.monotonic() - started
    print(f"✅ 翻譯完成：{result.input_tokens} in / {result.output_tokens} out tokens（{elapsed_translate:.1f}s）")

    # 3. 編譯（mono_path = 編譯 PDF——tex 檔是同名 .tex，別拿 PDF 當輸入）
    pdf_out = Path(result.mono_path)
    tex_out = pdf_out.with_suffix(".tex")
    try:
        # 源碼目錄（sty/Figures 附屬檔）→ include_dirs（同 adapter 內部編譯）
        compiled = TeXCompiler().compile(tex_out, tex_out.parent, include_dirs=[HERE])
    except Exception as e:
        print(f"❌ 編譯失敗：{e}")
        return 1
    print(f"✅ 編譯成功：{compiled}")

    # 4. 驗證譯文 tex
    rendered = tex_out.read_text(encoding="utf-8")
    if "\\PKP{" in rendered:
        failures.append(f"譯文 tex 殘留 \\PKP 佔位符 {rendered.count('\\PKP{')} 處")
    # 公式簽名：原文實際形式（\mathrm{Attention}(Q, K, V)——AC2 公式原樣驗證）
    sigs = ("\\mathrm{Attention}(Q, K, V)", "softmax", "QK^T", "\\sqrt{d_k}")
    sig_ok = 0
    for sig in sigs:
        if sig in rendered:
            sig_ok += 1
        else:
            failures.append(f"公式樣本遺失：{sig}")
    print(f"✅ 譯文 tex 驗證：\\PKP 殘留={rendered.count('\\PKP{')}，公式樣本 {sig_ok}/{len(sigs)}")

    # 5. 驗證 PDF（pymupdf）
    import fitz

    doc = fitz.open(str(compiled))
    page_count = len(doc)
    full_text = "".join(doc[i].get_text() for i in range(page_count))
    zh_hits = sum(1 for ch in "注意力機制神經網絡訓練" if ch in full_text)
    if page_count < 10:
        failures.append(f"PDF 頁數過少：{page_count}")
    if zh_hits < 6:
        failures.append(f"中文渲染不足（命中 {zh_hits}/7）")
    if "\\PKP" in full_text:
        failures.append("PDF 文字層殘留 \\PKP")
    print(f"✅ PDF 驗證：{page_count} 頁，中文命中 {zh_hits}/7")
    doc.close()

    # 6. 成本（DEFAULT_PRICING latex 同 deepseek-chat）
    from decimal import Decimal

    in_cost = Decimal(result.input_tokens) * Decimal("0.00027") / 1000
    out_cost = Decimal(result.output_tokens) * Decimal("0.0011") / 1000
    usd = in_cost + out_cost
    ntd = usd * Decimal("32")
    elapsed_total = time.monotonic() - started

    report = {
        "paper": "Attention Is All You Need (arXiv:1706.03762)",
        "source": "ms_single.tex（7 個 \\input 展開合併，73,907 字元）",
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "elapsed_total_s": round(elapsed_total, 1),
        "elapsed_translate_s": round(elapsed_translate, 1),
        "cost_usd": str(usd),
        "cost_ntd_at_32": str(ntd),
        "pdf_pages": page_count,
        "verify_ok": not failures,
        "failures": failures,
    }
    (HERE / "REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print(f"═══ 報告（{HERE.name}/REPORT.json）═══")
    print(f"  tokens：{result.input_tokens} in / {result.output_tokens} out")
    print(f"  成本：${usd:.4f} ≈ NT${ntd:.2f}（匯率 32）")
    print(f"  總耗時：{elapsed_total:.1f}s（翻譯 {elapsed_translate:.1f}s）")
    print(f"  PDF：{compiled.name}（{page_count} 頁）")
    if failures:
        print("  ❌ 驗證失敗：")
        for f in failures:
            print(f"    - {f}")
        return 1
    print("  ✅ 全部驗證通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
