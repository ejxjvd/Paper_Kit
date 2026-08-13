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


# ── 免費翻譯入口（2026-08-13 使用者要求：交付他人免費翻譯、不動個人 API）──


def test_ui_free_engine_ids_defined():
    """主頁免費卡集合：免 key 三支，順序＝品質/活躍度（siliconflowfree 上游預設排首）。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_ENGINE_IDS

    assert UI_FREE_ENGINE_IDS == ("siliconflowfree", "google", "bing")


def test_free_specs_have_card_desc_and_info():
    """免費卡顯示知識收斂 registry（P3 模式）：三支 free spec 的卡副標題與 ⓘ tooltip 齊備。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_ENGINE_IDS

    for eid in UI_FREE_ENGINE_IDS:
        spec = ENGINE_SPECS[eid]
        assert spec.card_desc, f"{eid} 缺 card_desc"
        assert spec.info, f"{eid} 缺 info"
        assert spec.needs_key is False, f"{eid} 應為免 key 引擎"


def test_all_keyless_specs_in_ui_free_ids():
    """不變式：所有 needs_key=False 的引擎必須在 UI_FREE_ENGINE_IDS——未來加
    keyless 引擎不上免費卡即紅（P3 單點模式的自動守衛）。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_ENGINE_IDS

    keyless = {eid for eid, spec in ENGINE_SPECS.items() if not spec.needs_key}
    assert keyless <= set(UI_FREE_ENGINE_IDS), f"未上免費卡：{keyless - set(UI_FREE_ENGINE_IDS)}"


# ── 免費 LLM key 引擎（2026-08-13，Free-LLM-Collection 查證後加入）──
# 語意分層：UI_FREE_ENGINE_IDS＝零 key 引擎（免填 key）；UI_FREE_KEY_ENGINE_IDS＝
# 免費 LLM 提供者（BYOK——自申請免費 key 填入，品質依優先序排列）。
# 查證依據：docs/research/2026-08-13-Free-LLM-Collection-查證與品質優先序.md
# （端點活性探測 25 提供者全測；優先序＝品質×額度×門檻綜合評分）


def test_ui_free_key_engine_ids_priority_order():
    """免費 LLM 卡集合與順序＝研究報告優先序：NVIDIA NIM（T1/T2、40RPM、無日總量）
    ＞ ModelScope（T1 品質天花板）＞ Groq（T2、RPD 充裕）＞ OpenRouter（nemotron
    翻譯數據免費群最佳）＞ 智譜（無 token 上限）＞ Gemini（T2 但免費層資料訓練）。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_KEY_ENGINE_IDS

    assert UI_FREE_KEY_ENGINE_IDS == (
        "nvidia", "modelscope", "groq", "openrouter", "bigmodel", "gemini",
    )


def test_free_key_specs_openai_provider():
    """不變式：免費 LLM 全走 provider=openai（pdf2zh --openai 三旗標，不需新 adapter）。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_KEY_ENGINE_IDS

    for eid in UI_FREE_KEY_ENGINE_IDS:
        spec = ENGINE_SPECS[eid]
        assert spec.provider == "openai", f"{eid} 應為 openai provider"
        assert spec.needs_key is True, f"{eid} 為 BYOK 免費 key 引擎（需填入 key）"
        assert spec.sensitive_ok is False, (
            f"{eid} 免費層無 SLA／第三方雲端——機密文件不可用（票 10 紅線）"
        )
        assert spec.base_url.startswith("https://"), f"{eid} base_url 異常：{spec.base_url}"
        assert spec.model, f"{eid} 缺預設模型"
        assert spec.card_desc, f"{eid} 缺 card_desc"
        assert spec.info, f"{eid} 缺 info（含隱私警語）"


def test_all_openai_provider_specs_in_free_key_ids():
    """不變式：所有 provider=openai 的引擎必須在 UI_FREE_KEY_ENGINE_IDS——
    未來加 OpenAI 相容免費端點不上免費 LLM 卡即紅。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_KEY_ENGINE_IDS

    openai_prov = {eid for eid, spec in ENGINE_SPECS.items() if spec.provider == "openai"}
    assert openai_prov <= set(UI_FREE_KEY_ENGINE_IDS), (
        f"未上免費 LLM 卡：{openai_prov - set(UI_FREE_KEY_ENGINE_IDS)}"
    )


def test_free_key_specs_distinct_from_keyless_free():
    """不變式：兩免費區不得重疊（零 key 區與 BYOK 免費 LLM 區語意不同）。"""
    from paper_kit.infrastructure.engine_registry import (
        UI_FREE_ENGINE_IDS,
        UI_FREE_KEY_ENGINE_IDS,
    )

    assert not set(UI_FREE_ENGINE_IDS) & set(UI_FREE_KEY_ENGINE_IDS)


def test_gemini_spec_carries_data_training_warning():
    """Gemini 免費層資料訓練條款＝未發表論文紅線（#28）——info 必須含警語。"""
    from paper_kit.infrastructure.engine_registry import ENGINE_SPECS

    info = ENGINE_SPECS["gemini"].info
    assert "資料訓練" in info or "訓練" in info, "Gemini info 缺資料訓練警語"
