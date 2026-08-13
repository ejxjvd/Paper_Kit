"""引擎註冊表：spec → adapter 工廠。換引擎＝換插頭（票 04/13 核心）。

驗證：spec 完整性（免費引擎、機密紅線 flag）、build_engine 對映正確 provider、
未知引擎 KeyError、free 引擎的 CLI 旗標正確、票 13 第二支插頭（BabelDoc）。
"""

import pytest
from decimal import Decimal

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
    spec = EngineSpec(
        id="x", label="X", provider="x", model="", needs_key=False, sensitive_ok=True,
        pricing=(Decimal("0"), Decimal("0"), 5000),  # 架構健檢 #3：定價必填
    )
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
    翻譯數據免費群最佳）＞ 智譜（無 token 上限）＞ 阿里雲 Model Studio（Qwen 官方，
    1M tokens 一次性）＞ Gemini（T2 但免費層資料訓練，殿後）。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_KEY_ENGINE_IDS

    assert UI_FREE_KEY_ENGINE_IDS == (
        "nvidia", "modelscope", "groq", "openrouter", "bigmodel", "dashscope", "gemini",
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


def test_all_openai_provider_specs_covered_by_ui_tuples():
    """不變式：所有 provider=openai 的引擎必須上卡（UI_FREE_KEY_ENGINE_IDS 免費 LLM
    ∪ UI_ENGINE_IDS 付費 OpenAI 相容）——2026-08-13 加入付費 openai/gemini-pro 後，
    免費區守衛改為全覆蓋守衛（漏登記任何 OpenAI 相容引擎即紅）。"""
    from paper_kit.infrastructure.engine_registry import (
        UI_ENGINE_IDS,
        UI_FREE_KEY_ENGINE_IDS,
    )

    openai_prov = {eid for eid, spec in ENGINE_SPECS.items() if spec.provider == "openai"}
    covered = set(UI_FREE_KEY_ENGINE_IDS) | set(UI_ENGINE_IDS)
    assert openai_prov <= covered, f"未上任何卡：{openai_prov - covered}"


# ── 付費 OpenAI 相容引擎（2026-08-13 使用者要求：OpenAI／Gemini 付費 API）──


def test_registry_has_openai_and_gemini_pro_paid_specs():
    """使用者要求（2026-08-13）：新增 OpenAI（Codex API 同 key）與 Gemini 付費引擎。"""
    from paper_kit.infrastructure.engine_registry import UI_FREE_KEY_ENGINE_IDS

    for eid in ("openai", "gemini-pro"):
        spec = ENGINE_SPECS[eid]
        assert spec.needs_key is True, f"{eid} 為付費引擎（需自備 key）"
        assert spec.sensitive_ok is True, (
            f"{eid} 付費 API 層不用資料訓練——機密文件可用（票 10 紅線合規）"
        )
        assert spec.provider == "openai", f"{eid} 走 pdf2zh --openai 三旗標"
        assert spec.base_url.startswith("https://"), f"{eid} base_url 異常"
        assert spec.model and spec.card_desc and spec.info, f"{eid} 缺 model/card_desc/info"
        assert eid not in UI_FREE_KEY_ENGINE_IDS, f"{eid} 是付費引擎不該在免費 LLM 區"


def test_ui_engine_ids_include_new_paid_engines():
    """付費卡集合含新增兩引擎（順序＝既有四卡後尾加）。"""
    from paper_kit.infrastructure.engine_registry import UI_ENGINE_IDS

    assert UI_ENGINE_IDS == (
        "siliconflow", "deepseek", "babeldoc", "latex", "openai", "gemini-pro",
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


# ── 架構健檢 #3（2026-08-13）：定價收進 EngineSpec 單一真相 ──
# 動機：DEFAULT_PRICING（cost_service）與 ENGINE_SPECS 平行演化失同步——
# 新增 10 支引擎沒進 DEFAULT_PRICING → 付費引擎估價落 (0,0,5000) fallback，
# 顯示「免費引擎無費用」。定價與引擎規格同處後，加引擎＝改 registry 單點。


def test_all_specs_carry_pricing():
    """不變式：18 支引擎全部有定價（非 None、非負、per_page>0）——防「加引擎忘定價」。"""
    from paper_kit.infrastructure.engine_registry import ENGINE_SPECS

    for eid, spec in ENGINE_SPECS.items():
        assert spec.pricing is not None, f"{eid} 缺 pricing"
        input_1k, output_1k, per_page = spec.pricing
        assert input_1k >= 0 and output_1k >= 0, f"{eid} 單價異常"
        assert per_page > 0, f"{eid} per_page_tokens 異常"


def test_free_engines_pricing_is_zero():
    """免費引擎（免 key 三支＋免費 LLM 七支）定價全零——免費額度不該顯示費用。"""
    from paper_kit.infrastructure.engine_registry import (
        ENGINE_SPECS,
        UI_FREE_KEY_ENGINE_IDS,
    )

    for eid, spec in ENGINE_SPECS.items():
        if not spec.needs_key or eid in UI_FREE_KEY_ENGINE_IDS:
            assert spec.pricing == (Decimal("0"), Decimal("0"), 5000), f"{eid} 免費引擎應零價"


def test_paid_engines_carry_official_pricing():
    """OpenAI gpt-5-mini／Gemini 3 Pro 官方價（2026-08-13 WebSearch 查證官方價格頁）。"""
    from paper_kit.infrastructure.engine_registry import ENGINE_SPECS

    assert ENGINE_SPECS["openai"].pricing == (
        Decimal("0.00025"), Decimal("0.002"), 5000,
    ), "gpt-5-mini：$0.25/M in、$2.00/M out"
    assert ENGINE_SPECS["gemini-pro"].pricing == (
        Decimal("0.002"), Decimal("0.012"), 5000,
    ), "Gemini 3 Pro：$2.00/M in、$12.00/M out"


# ── 架構健檢 #1+2+8（2026-08-13）：引擎挑選規則收斂 registry ──
# 動機：機密紅線（sensitive_ok×5）與 key 存在判定（needs_key×4＋latex 槽位沿用）
# 散落 presentation——app.py 五處各自重算，新增引擎要同步改五處；規則單點化後
# 加引擎＝改 registry（規格＋規則同處），UI 只呼叫。
# 四純函式：sensitive_blocked（機密紅線）、resolve_key（有效 key 值——latex
# 槽位沿用單點）、spec_has_key（判存在）、can_select（灰化組合）。


def test_sensitive_blocked_redline():
    """機密紅線（票 10）：sensitive 且引擎不支援機密 → 不可選。"""
    from paper_kit.infrastructure.engine_registry import sensitive_blocked

    assert sensitive_blocked("siliconflow", True) is True    # 視覺引擎：機密不可用
    assert sensitive_blocked("deepseek", True) is False      # 純文字：機密可用
    assert sensitive_blocked("openai", True) is False        # 付費不訓練：機密可用
    assert sensitive_blocked("siliconflow", False) is False  # 非機密：不擋


def test_sensitive_blocked_unknown_engine_raises():
    """未知引擎 fail-fast（與 presentation 舊行為一致——UI 只從 registry 選）。"""
    from paper_kit.infrastructure.engine_registry import sensitive_blocked

    with pytest.raises(KeyError):
        sensitive_blocked("nope", True)


def test_resolve_key_latex_prefers_own_slot():
    """票 27：latex 獨立填 key 時優先自己的槽位。"""
    from paper_kit.infrastructure.engine_registry import resolve_key

    keys = {"latex": "L-KEY", "deepseek": "DS-KEY"}
    assert resolve_key("latex", keys.get) == "L-KEY"


def test_resolve_key_latex_falls_back_to_deepseek_slot():
    """票 27：latex 未獨立填時沿用 deepseek 槽位（同後端同 key）。"""
    from paper_kit.infrastructure.engine_registry import resolve_key

    keys = {"deepseek": "DS-KEY"}
    assert resolve_key("latex", keys.get) == "DS-KEY"
    assert resolve_key("latex", {}.get) == ""  # 兩槽皆空


def test_resolve_key_unknown_engine_raises():
    from paper_kit.infrastructure.engine_registry import resolve_key

    with pytest.raises(KeyError):
        resolve_key("nope", {}.get)


def test_spec_has_key_keyless_engines_always_true():
    """免 key 引擎（google/bing/siliconflowfree）：不查 key 永遠有 key。"""
    from paper_kit.infrastructure.engine_registry import spec_has_key

    for eid in ("google", "bing", "siliconflowfree"):
        assert spec_has_key(eid, {}.get) is True, f"{eid} 免 key 引擎不該擋"


def test_spec_has_key_needs_key_engine_checks_own_slot():
    from paper_kit.infrastructure.engine_registry import spec_has_key

    assert spec_has_key("siliconflow", {"siliconflow": "SF-KEY"}.get) is True
    assert spec_has_key("siliconflow", {}.get) is False


def test_spec_has_key_latex_uses_resolve_key():
    """latex 判存在＝resolve_key（槽位沿用單點）——特例字串不在 UI 重複。"""
    from paper_kit.infrastructure.engine_registry import spec_has_key

    assert spec_has_key("latex", {"deepseek": "DS-KEY"}.get) is True
    assert spec_has_key("latex", {}.get) is False


def test_spec_has_key_unknown_engine_raises():
    from paper_kit.infrastructure.engine_registry import spec_has_key

    with pytest.raises(KeyError):
        spec_has_key("nope", {}.get)


def test_can_select_combines_sensitive_and_key():
    """灰化判定＝機密紅線先、key 後（與 _pick_engine 守衛同源，象限全驗）。"""
    from paper_kit.infrastructure.engine_registry import can_select

    keys = {"siliconflow": "SF-KEY", "deepseek": "DS-KEY"}
    # 機密檔：視覺引擎有 key 也擋；deepseek 有 key 可選
    assert can_select("siliconflow", True, keys.get) is False
    assert can_select("deepseek", True, keys.get) is True
    # 一般檔：siliconflow 有 key 可選、無 key 不可選
    assert can_select("siliconflow", False, keys.get) is True
    assert can_select("siliconflow", False, {}.get) is False
