"""CostCalculator 領域服務（純規則，無 IO）。

成本模型（規格書定案）：
- 每頁 token 統計：官方 4,703–7,382/頁，POC 實測 gemma ≈5,198、DeepSeek ≈4,673
- 引擎單價參數化：DeepSeek 漲價教訓 → 單價是設定不是寫死
- input/output 佔比參數化（POC 實測 ≈ 77/23）
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PricingConfig:
    input_per_1k: Decimal    # USD，每 1K input tokens
    output_per_1k: Decimal   # USD，每 1K output tokens
    per_page_tokens: int = 5000
    input_ratio: Decimal = Decimal("0.77")


@dataclass(frozen=True)
class CostEstimate:
    pages: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cost: Decimal  # USD


class CostCalculator:
    def estimate(self, pages: int, pricing: PricingConfig) -> CostEstimate:
        if pages < 0:
            raise ValueError(f"頁數不可為負: {pages}")
        total = pages * pricing.per_page_tokens
        input_tokens = int(Decimal(total) * pricing.input_ratio)
        output_tokens = total - input_tokens
        cost = (
            Decimal(input_tokens) / 1000 * pricing.input_per_1k
            + Decimal(output_tokens) / 1000 * pricing.output_per_1k
        )
        return CostEstimate(
            pages=pages,
            total_tokens=total,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )
