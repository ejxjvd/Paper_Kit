"""引擎註冊表：spec → adapter 工廠。換引擎＝換插頭（票 04 核心）。

驗證：spec 完整性（免費引擎、機密紅線 flag）、build_engine 對映正確 provider、
未知引擎 KeyError、free 引擎的 CLI 旗標正確。
"""

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.pdf2zh_next_adapter import DEFAULT_BASE_URL
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS, EngineSpec, build_engine
from paper_kit.infrastructure.pdf2zh_next_adapter import (
    DEFAULT_BASE_URL,
    Pdf2zhNextAdapter,
    build_command,
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
