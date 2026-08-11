"""CostCalculator 領域服務（純規則，無 IO）。

成本模型（規格書定案）：每頁 token（官方 4,703–7,382，POC 實測 ≈5,000）＋
引擎單價參數化（DeepSeek 漲價教訓：單價是設定不是寫死）。
POC 實測 input/output 比 ≈ 77/23。
"""

import pytest
from decimal import Decimal

from paper_kit.domain.cost_calculator import CostCalculator, CostEstimate, PricingConfig

DEFAULT = PricingConfig(
    input_per_1k=Decimal("0.14"),   # USD，近似 DeepSeek 單價
    output_per_1k=Decimal("0.28"),
    per_page_tokens=5000,
    input_ratio=Decimal("0.77"),
)
CALC = CostCalculator()


def test_zero_pages_cost_nothing():
    est = CALC.estimate(0, DEFAULT)
    assert est.total_tokens == 0
    assert est.cost == 0


def test_one_page_uses_per_page_tokens():
    est = CALC.estimate(1, DEFAULT)
    assert est.total_tokens == 5000


def test_known_worked_example():
    """獨立手算基準：2 頁 × 5000 tokens、input 80%、input $0.5/K、output $1.0/K。
    input = 8000 → 8 × 0.5 = $4.0；output = 2000 → 2 × 1.0 = $2.0 → 總計 $6.0"""
    pricing = PricingConfig(
        input_per_1k=Decimal("0.5"),
        output_per_1k=Decimal("1.0"),
        per_page_tokens=5000,
        input_ratio=Decimal("0.8"),
    )
    est = CALC.estimate(2, pricing)
    assert est.total_tokens == 10000
    assert est.cost == Decimal("6.0")


def test_huge_page_count_scales_linearly():
    est = CALC.estimate(10_000, DEFAULT)
    assert est.total_tokens == 50_000_000
    assert est.cost == pytest.approx(float(Decimal("0.77") * 50_000_000 / 1000 * Decimal("0.14")
                                         + Decimal("0.23") * 50_000_000 / 1000 * Decimal("0.28")))


def test_pricing_is_parameterized_not_hardcoded():
    cheap = PricingConfig(
        input_per_1k=Decimal("0.01"),
        output_per_1k=Decimal("0.02"),
        per_page_tokens=5000,
        input_ratio=Decimal("0.77"),
    )
    est = CALC.estimate(10, cheap)
    assert est.cost < CALC.estimate(10, DEFAULT).cost


def test_negative_pages_rejected():
    with pytest.raises(ValueError):
        CALC.estimate(-1, DEFAULT)


def test_estimate_reports_input_output_split():
    est = CALC.estimate(1, DEFAULT)
    assert est.input_tokens + est.output_tokens == est.total_tokens
