"""引擎註冊表：spec → adapter 工廠。換引擎＝換插頭（票 04/13 核心）。

驗證：spec 完整性（免費引擎、機密紅線 flag）、build_engine 對映正確 provider、
未知引擎 KeyError、free 引擎的 CLI 旗標正確、票 13 第二支插頭（BabelDoc）。
"""

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS, EngineSpec, build_engine
from paper_kit.infrastructure.babeldoc_adapter import (
    BabelDocAdapter,
    DEFAULT_BABELDOC_BASE_URL,
    DEFAULT_BABELDOC_MODEL,
)
from paper_kit.infrastructure.pdf2zh_next_adapter import (
    DEFAULT_BASE_URL,
    Pdf2zhNextAdapter,
    build_command,
)
from paper_kit.infrastructure.latex_adapter import LatexAdapter
from paper_kit.infrastructure.latex_translator import (
    DEFAULT_LATEX_BASE_URL,
    DEFAULT_LATEX_MODEL,
)
from paper_kit.infrastructure.ppt_vision_adapter import PptVisionAdapter
from paper_kit.infrastructure.siliconflow_vision import (
    DEFAULT_VISION_BASE_URL,
    DEFAULT_VISION_MODEL,
)
from paper_kit.domain.translation_job import TranslationJob


def test_registry_has_siliconflow_deepseek_and_free_engines():
    assert "siliconflow" in ENGINE_SPECS
    assert "deepseek" in ENGINE_SPECS
    assert "siliconflowfree" in ENGINE_SPECS
    assert "google" in ENGINE_SPECS
    assert "bing" in ENGINE_SPECS


def test_sensitive_redline_flags():
    """機密模式紅線：視覺/雲端引擎不可用，純文字 DeepSeek 可用（票 10）。"""
    assert ENGINE_SPECS["siliconflow"].sensitive_ok is False
    assert ENGINE_SPECS["deepseek"].sensitive_ok is True
    assert ENGINE_SPECS["siliconflowfree"].sensitive_ok is False


def test_siliconflow_spec_defaults():
    spec = ENGINE_SPECS["siliconflow"]
    assert spec.label
    assert spec.model.startswith("google/gemma")
    assert spec.needs_key is True
    assert spec.base_url == DEFAULT_BASE_URL  # 國際站 .com


def test_build_engine_returns_adapter_with_matching_provider():
    adapter = build_engine(ENGINE_SPECS["deepseek"], api_key="DS-KEY")
    assert isinstance(adapter, Pdf2zhNextAdapter)
    assert adapter._config.provider == "deepseek"
    assert adapter._config.api_key == "DS-KEY"


def test_build_engine_free_engine_needs_no_key():
    adapter = build_engine(ENGINE_SPECS["bing"])
    assert adapter._config.api_key == ""


def test_build_engine_passes_term_api_key_through():
    """#84：術語提取 key 獨立化——build_engine 把 term_api_key 帶入 EngineConfig；
    未傳時預設空（build_command 沿用主 key）。"""
    adapter = build_engine(
        ENGINE_SPECS["siliconflow"], api_key="MAIN-KEY", term_api_key="TERM-KEY"
    )
    assert adapter._config.api_key == "MAIN-KEY"
    assert adapter._config.term_api_key == "TERM-KEY"
    plain = build_engine(ENGINE_SPECS["siliconflow"], api_key="MAIN-KEY")
    assert plain._config.term_api_key == ""


def test_engine_spec_construction_defaults_base_url():
    spec = EngineSpec(id="x", label="X", provider="x", model="", needs_key=False, sensitive_ok=True)
    assert spec.base_url == DEFAULT_BASE_URL  # 未指定就用國際站 .com


def test_free_engine_cli_flags():
    """免費引擎直接對映 CLI 旗標（--google／--bing／--siliconflowfree）。"""
    job = TranslationJob(job_id="j", source_path="/in/a.pdf")
    for provider in ("google", "bing", "siliconflowfree"):
        cfg = build_engine(ENGINE_SPECS[provider])._config
        cmd = build_command(job, cfg)
        assert f"--{provider}" in cmd
        assert "--siliconflow" not in cmd and "--deepseek" not in cmd


def test_key_required_at_resolve_time_not_registry():
    """spec 宣告 needs_key；實際缺 key 的錯誤在 resolve/translate 時給（友善訊息）。"""
    spec = ENGINE_SPECS["siliconflow"]
    assert spec.needs_key is True
    adapter = build_engine(spec, api_key="")
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(TranslationJob(job_id="j", source_path="/in/a.pdf"))


# ── 票 13：BabelDOC 第二支插頭 ─────────────────────────────


def test_registry_has_babeldoc_spec():
    """AC2：引擎註冊表新增 → UI 下拉（registry-driven）立即可選。"""
    spec = ENGINE_SPECS["babeldoc"]
    assert spec.label
    assert spec.needs_key is True
    assert spec.sensitive_ok is False  # 送雲端 LLM：機密模式不可用（紅線）
    assert spec.model == DEFAULT_BABELDOC_MODEL
    assert spec.base_url == DEFAULT_BABELDOC_BASE_URL


def test_build_engine_babeldoc_returns_babeldoc_adapter():
    adapter = build_engine(ENGINE_SPECS["babeldoc"], api_key="BK")
    assert isinstance(adapter, BabelDocAdapter)
    assert adapter._config.api_key == "BK"
    assert adapter._config.model == DEFAULT_BABELDOC_MODEL


def test_build_engine_babeldoc_missing_key_fails_at_translate():
    """換插頭不破壞：缺 key 的錯誤時點/訊息與既有引擎一致（基底共用）。"""
    adapter = build_engine(ENGINE_SPECS["babeldoc"], api_key="")
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(TranslationJob(job_id="j", source_path="/in/a.pdf"))


# ── 票 14：PPT 視覺路徑第三支插頭 ──────────────────────────


def test_registry_has_ppt_vision_spec():
    """AC2：引擎註冊表新增 → UI 下拉（registry-driven）立即可選（同票 13 模式）。"""
    spec = ENGINE_SPECS["ppt-vision"]
    assert spec.label
    assert spec.needs_key is True
    assert spec.sensitive_ok is False  # 視覺 = 圖片上雲端（票 10 紅線）
    assert spec.model == DEFAULT_VISION_MODEL
    assert spec.base_url == DEFAULT_VISION_BASE_URL


def test_build_engine_ppt_vision_returns_adapter_with_config():
    adapter = build_engine(ENGINE_SPECS["ppt-vision"], api_key="SF-KEY")
    assert isinstance(adapter, PptVisionAdapter)
    assert adapter._config.api_key == "SF-KEY"
    assert adapter._config.model == DEFAULT_VISION_MODEL


def test_build_engine_ppt_vision_missing_key_fails_at_translate():
    """缺 key 的錯誤時點/訊息與既有引擎一致（翻譯時友善錯誤）。"""
    adapter = build_engine(ENGINE_SPECS["ppt-vision"], api_key="")
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(TranslationJob(job_id="j", source_path="/in/a.pptx"))


# ── 票 15：LaTeX 源碼路線第四支插頭 ────────────────────────


def test_registry_has_latex_spec():
    """AC1：引擎註冊表新增 → UI 下拉（registry-driven）立即可選（同票 13/14 模式）。"""
    spec = ENGINE_SPECS["latex"]
    assert spec.label
    assert spec.needs_key is True
    assert spec.sensitive_ok is True  # 純文字引擎：機密模式可用（票 10 紅線合規）
    assert spec.model == DEFAULT_LATEX_MODEL
    assert spec.base_url == DEFAULT_LATEX_BASE_URL


def test_build_engine_latex_returns_latex_adapter():
    adapter = build_engine(ENGINE_SPECS["latex"], api_key="DS-KEY")
    assert isinstance(adapter, LatexAdapter)
    assert adapter._config.api_key == "DS-KEY"
    assert adapter._config.model == DEFAULT_LATEX_MODEL


def test_build_engine_latex_missing_key_fails_at_translate():
    """缺 key 的錯誤時點/訊息與既有引擎一致（翻譯時友善錯誤）。"""
    adapter = build_engine(ENGINE_SPECS["latex"], api_key="")
    with pytest.raises(EngineError, match="API key"):
        adapter.translate(TranslationJob(job_id="j", source_path="/in/a.tex"))
