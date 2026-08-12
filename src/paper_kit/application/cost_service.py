"""CostService（application）：成本估算＋實際費用（包裝領域 CostCalculator）。

- 估算：委派領域 CostCalculator.estimate（純規則、單一真相——不在此複製數學）
- 實際：引擎回報的 token × 單價（領域 cost_for_tokens 同一公式）
- 單價存在 SQLite（USD/1K tokens；漲價只需改設定——2026-08-06 DeepSeek 漲價教訓）
- 免費引擎（google／bing／siliconflowfree）價格為零
"""

from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

from paper_kit.application.pages import page_count_in_range
from paper_kit.domain.cost_calculator import CostCalculator, CostEstimate, PricingConfig
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository

# 預設單價（USD/1K tokens；官方價格頁為準，設定頁可改）。免費引擎為零。
DEFAULT_PRICING: dict[str, tuple[Decimal, Decimal, int]] = {
    "deepseek": (Decimal("0.00027"), Decimal("0.0011"), 5000),  # 2026-08-06 漲價後
    "siliconflow": (Decimal("0.0012"), Decimal("0.0012"), 5000),
    "siliconflowfree": (Decimal("0"), Decimal("0"), 5000),
    "google": (Decimal("0"), Decimal("0"), 5000),
    "bing": (Decimal("0"), Decimal("0"), 5000),
}
DEFAULT_PER_PAGE_TOKENS = 5000


class CostService:
    """包裝領域 CostCalculator：從設定取單價 → 領域算 → 顯示用標籤。"""

    def __init__(self, repo: SqliteSettingsRepository):
        self._repo = repo
        self._calculator = CostCalculator()

    def pricing_for(self, engine_id: str) -> PricingConfig:
        row = self._repo.get_pricing(engine_id)
        if row is not None:
            return PricingConfig(Decimal(row[0]), Decimal(row[1]), row[2])
        input_per_1k, output_per_1k, per_page = DEFAULT_PRICING.get(
            engine_id, (Decimal("0"), Decimal("0"), DEFAULT_PER_PAGE_TOKENS)
        )
        return PricingConfig(input_per_1k, output_per_1k, per_page)

    def set_pricing(
        self,
        engine_id: str,
        input_per_1k: str | Decimal,
        output_per_1k: str | Decimal,
        per_page_tokens: int,
    ) -> None:
        self._repo.set_pricing(
            engine_id, str(input_per_1k), str(output_per_1k), int(per_page_tokens)
        )

    def estimate(self, engine_id: str, pages: int) -> CostEstimate:
        """翻譯前估算：委派領域 CostCalculator（負頁數 ValueError 由領域把關）。"""
        return self._calculator.estimate(pages, self.pricing_for(engine_id))

    def actual(self, job: TranslationJob, engine_id: str) -> CostEstimate:
        """翻譯後實際費用：引擎回報的用量 × 單價（領域公式，不在此複製）。"""
        result = job.result or JobResult()
        cost = self._calculator.cost_for_tokens(
            result.input_tokens, result.output_tokens, self.pricing_for(engine_id)
        )
        return CostEstimate(
            pages=0,
            total_tokens=result.input_tokens + result.output_tokens,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=cost,
        )

    def diff(self, est: CostEstimate, actual: CostEstimate) -> Decimal:
        return est.cost - actual.cost

    def diff_label(self, est: CostEstimate, actual: CostEstimate) -> str:
        return self._diff_text(est.cost, actual)

    def _diff_text(self, est_cost: Decimal, actual: CostEstimate) -> str:
        return f"估 ${est_cost} → 實際 ${actual.cost}（差 {est_cost - actual.cost}）"

    def pdf_pages(self, pdf_path: str | Path) -> int:
        """估算前拿 PDF 真實頁數（pypdf）。"""
        with PdfReader(str(pdf_path)) as reader:
            return len(reader.pages)

    def estimate_for_pdf(
        self, engine_id: str, pdf_path: str | Path, pages: str | None = None
    ) -> CostEstimate | None:
        """翻譯前估算；pypdf 解析失敗回 None（UI 靜默跳過，不外洩 IO 錯誤）。

        pages 指定（票 07）→ 按範圍頁數縮放（規格書 story 4「只為需要的部分付費」），
        不再需要讀 PDF。
        """
        try:
            if pages:
                return self.estimate(engine_id, pages=page_count_in_range(pages))
            return self.estimate(engine_id, pages=self.pdf_pages(pdf_path))
        except Exception:
            return None

    def usage_label(self, job: TranslationJob) -> str | None:
        """票 06：完成任務的成本標籤（估算 vs 實際）；不可算時只顯示用量。

        優先用上傳時存的 estimated_cost——完成後比對的是「使用者看到的」數字，
        不是重算的幽靈值（spec review 修正）；無則回退到即時重估。
        單一 application 呼叫——UI 薄層不需自己編排 estimate/actual/pdf_pages。
        """
        result = job.result
        if not result or not (result.input_tokens or result.output_tokens):
            return None
        tokens = f"{result.input_tokens:,} in / {result.output_tokens:,} out"
        try:
            actual = self.actual(job, job.engine_id) if job.engine_id else None
        except Exception:
            actual = None
        if actual is None:
            return f"實際用量 {tokens}"
        if job.estimated_cost is not None:
            return f"成本：{self._diff_text(job.estimated_cost, actual)}（{tokens}）"
        est = self.estimate_for_pdf(job.engine_id, job.source_path)
        if est is None:
            return f"實際成本 ${actual.cost}（{tokens}）"
        return f"成本：{self.diff_label(est, actual)}（{tokens}）"
