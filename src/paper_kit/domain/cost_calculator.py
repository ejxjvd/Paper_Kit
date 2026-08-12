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
    # 術語表倍率：BabelDOC 官方統計關術語 4,703 tokens/頁 vs 開術語 7,382/頁
    # → 7,382/4,703 ≈ 1.57（術語注入增加 input tokens；research 實測值）
    GLOSSARY_TOKEN_MULTIPLIER = Decimal("1.57")

    def estimate(
        self, pages: int, pricing: PricingConfig, glossary: bool = False
    ) -> CostEstimate:
        if pages < 0:
            raise ValueError(f"頁數不可為負: {pages}")
        per_page = pricing.per_page_tokens
        if glossary:
            per_page = int(Decimal(per_page) * self.GLOSSARY_TOKEN_MULTIPLIER)
        total = pages * per_page
        input_tokens = int(Decimal(total) * pricing.input_ratio)
        output_tokens = total - input_tokens
        return CostEstimate(
            pages=pages,
            total_tokens=total,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=self.cost_for_tokens(input_tokens, output_tokens, pricing),
        )

    def cost_for_tokens(
        self, input_tokens: int, output_tokens: int, pricing: PricingConfig
    ) -> Decimal:
        """實際用量計費（與 estimate 同一公式——單一真相，application 不可複製）。"""
        return (
            Decimal(input_tokens) / 1000 * pricing.input_per_1k
            + Decimal(output_tokens) / 1000 * pricing.output_per_1k
        )
