"""引擎註冊表：EngineSpec → adapter 工廠。換引擎＝換插頭（票 04/13）。

- sensitive_ok：機密模式紅線（票 10）——視覺/雲端影像引擎不可用，純文字引擎可用
- needs_key：free 引擎（google/bing/siliconflowfree）不需 key
- 票 13：BabelDocAdapter（OpenAI 相容雲端）第二支插頭——spec 分派不同 adapter 類
- P3（2026-08-13 架構重構）：顯示知識收斂——card_desc/info（主頁卡副標題＋ⓘ tooltip）
  併入 spec；UI_ENGINE_IDS 定義主頁卡集合與順序。加引擎＝改此檔單點。
"""

from dataclasses import dataclass

from paper_kit.infrastructure.babeldoc_adapter import (
    BabelDocAdapter,
    BabelDocConfig,
    DEFAULT_BABELDOC_BASE_URL,
    DEFAULT_BABELDOC_MODEL,
)
from paper_kit.infrastructure.latex_adapter import (
    DEFAULT_LATEX_BASE_URL,
    DEFAULT_LATEX_MODEL,
    LatexAdapter,
    LatexConfig,
)
from paper_kit.infrastructure.pdf2zh_next_adapter import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    EngineConfig,
    Pdf2zhNextAdapter,
)
from paper_kit.infrastructure.ppt_vision_adapter import (
    PptVisionAdapter,
    PptVisionConfig,
)
from paper_kit.infrastructure.siliconflow_vision import (
    DEFAULT_VISION_BASE_URL,
    DEFAULT_VISION_MODEL,
)


@dataclass(frozen=True)
class EngineSpec:
    id: str
    label: str
    provider: str
    model: str
    needs_key: bool
    sensitive_ok: bool
    base_url: str = DEFAULT_BASE_URL
    card_desc: str = ""   # P3：主頁卡副標題（僅 UI_ENGINE_IDS 內引擎填）
    info: str = ""        # P3：主頁卡 ⓘ tooltip 長敘述（hover 顯示引擎差異）


ENGINE_SPECS: dict[str, EngineSpec] = {
    "siliconflow": EngineSpec(
        id="siliconflow",
        label="SiliconFlow gemma-4-31B-it",
        provider="siliconflow",
        model=DEFAULT_MODEL,
        needs_key=True,
        sensitive_ok=False,
        card_desc="gemma 視覺模型（圖表精準；預設引擎）",
        info="gemma 視覺模型：圖表／公式版面精準，預設引擎。需 SiliconFlow API key。",
    ),
    "deepseek": EngineSpec(
        id="deepseek",
        label="DeepSeek（純文字，機密模式可用）",
        provider="deepseek",
        model="",
        needs_key=True,
        sensitive_ok=True,
        # 2026-08-13（測試 API 按鈕）：pdf2zh deepseek 分支固定 api.deepseek.com
        # （build_command 不送 base-url 旗標）——spec 補上供「測試 API」探測用
        base_url="https://api.deepseek.com/v1",
        card_desc="純文字模型（機密文件唯一可用）",
        info="純文字模型：機密文件唯一可用（不上視覺模型）；成本最省。",
    ),
    "siliconflowfree": EngineSpec(
        id="siliconflowfree",
        label="SiliconFlowFree（零成本）",
        provider="siliconflowfree",
        model="",
        needs_key=False,
        sensitive_ok=False,
        # 免費翻譯入口（2026-08-13）：上游預設、活躍；額度由 SiliconFlow 官方
        # 提供（gui.py「Free translation service provided by SiliconFlow」）
        card_desc="GLM-4-9B 免費模型（上游預設；免 key 推薦）",
        info="免 API key 的免費引擎：pdf2zh-next 上游預設方案，模型 THUDM/GLM-4-9B-0414，"
        "額度由 SiliconFlow 官方提供、經上游代理伺服器轉發（共享資源、有 QPS 節流）。"
        "檔案會上第三方伺服器——機密文件禁用；品質低於付費引擎（見 docs/research 品質比較）。",
    ),
    "google": EngineSpec(
        id="google",
        label="Google 免費引擎",
        provider="google",
        model="",
        needs_key=False,
        sensitive_ok=False,
        # 免費翻譯入口（2026-08-13）：上游已棄用——保留但不推薦
        card_desc="Google 網頁翻譯（上游已棄用）",
        info="Google 網頁翻譯接口、不需 key；上游 pdf2zh-next 已標記棄用，"
        "旗標仍在但可能隨時失效——不建議依賴。品質低於付費引擎。",
    ),
    "bing": EngineSpec(
        id="bing",
        label="Bing 免費引擎",
        provider="bing",
        model="",
        needs_key=False,
        sensitive_ok=False,
        card_desc="Bing 網頁翻譯（上游已棄用）",
        info="Bing 網頁翻譯接口、不需 key；上游 pdf2zh-next 已標記棄用，"
        "旗標仍在但可能隨時失效——不建議依賴。品質低於付費引擎。",
    ),
    "babeldoc": EngineSpec(
        id="babeldoc",
        label="BabelDOC（OpenAI 相容雲端，DeepSeek 後端）",
        provider="babeldoc",
        model=DEFAULT_BABELDOC_MODEL,
        needs_key=True,
        sensitive_ok=False,  # 送雲端 LLM：機密模式不可用（票 10 紅線）
        base_url=DEFAULT_BABELDOC_BASE_URL,
        card_desc="OpenAI 相容雲端（DeepSeek 後端）",
        info="OpenAI 相容雲端（DeepSeek 後端）：版面重排能力強；"
        "下方的「BabelDOC 進階選項」（僅翻譯選中頁面／相容模式等）僅此引擎顯示。",
    ),
    "ppt-vision": EngineSpec(
        id="ppt-vision",
        label="PPT 視覺（gemma 眼睛逐頁翻譯，SiliconFlow）",
        provider="ppt-vision",
        model=DEFAULT_VISION_MODEL,
        needs_key=True,
        sensitive_ok=False,  # 視覺 = 圖片上雲端（票 10 紅線，同 paste-vision）
        base_url=DEFAULT_VISION_BASE_URL,
    ),
    "latex": EngineSpec(
        id="latex",
        label="LaTeX 源碼（xelatex 編譯，DeepSeek 純文字）",
        provider="latex",
        model=DEFAULT_LATEX_MODEL,
        needs_key=True,
        sensitive_ok=True,  # 純文字源碼：機密模式可用（票 10 紅線合規）
        base_url=DEFAULT_LATEX_BASE_URL,
        # 票 27：成本 4.7× 差距的理由（公式指令原封、token 最省）
        card_desc="DeepSeek 純文字（xelatex 編譯；僅 .tex 源碼適用）",
        info="LaTeX 源碼：公式指令原封保留、xelatex 編譯重排，token 最省"
        "（整本 NT$0.3 級，票 15 實測 NT$0.34）。僅適用 .tex 源碼上傳；PDF 請選上方三引擎。",
    ),
    # ── 免費 LLM（2026-08-13，Free-LLM-Collection 查證後加入）──
    # 全 provider=openai（pdf2zh --openai 三旗標共用）、BYOK 免費 key（各自申請）、
    # sensitive_ok=False（免費層無 SLA／第三方雲端——機密文件不可用，票 10 紅線）。
    # 優先序依據 docs/research/2026-08-13-Free-LLM-Collection-查證與品質優先序.md。
    # 端點活性：25 提供者假 key 探測全測（2026-08-13 scripts/free_llm_probe.py）——
    # 本區 6 家全部存活（401/400 認證流程正常）。
    "nvidia": EngineSpec(
        id="nvidia",
        label="NVIDIA NIM（免費旗艦）",
        provider="openai",
        model="deepseek-ai/deepseek-v4-flash",
        needs_key=True,
        sensitive_ok=False,
        base_url="https://integrate.api.nvidia.com/v1",
        card_desc="DeepSeek-V4-Flash 免費（T1/T2；40 RPM、無日總量）",
        info="NVIDIA 官方免費端（build.nvidia.com，nvapi- key）：DeepSeek-V4-Flash/GLM-5.2/"
        "Kimi-K2.6 等旗艦模型免費、無日總量、免綁卡。無 SLA——429 會退避重試；"
        "檔案上 NVIDIA 雲端——機密文件不可用。",
    ),
    "modelscope": EngineSpec(
        id="modelscope",
        label="ModelScope 魔搭（免費品質天花板）",
        provider="openai",
        model="deepseek-ai/DeepSeek-V4-Pro",
        needs_key=True,
        sensitive_ok=False,
        base_url="https://api-inference.modelscope.cn/v1",
        card_desc="DeepSeek-V4-Pro/GLM-5.1 免費（T1；2,000 RPD）",
        info="阿里雲 ModelScope 免費端（ms- key，須阿里雲實名）：DeepSeek-V4-Pro/GLM-5.1/"
        "Qwen3-235B 免費——T1 品質、中文最強。額度動態分配（熱門模型實測 ~500 RPD、"
        "可能 insufficient_quota）——失敗請稍後重試。檔案上阿里雲——機密文件不可用。",
    ),
    "groq": EngineSpec(
        id="groq",
        label="Groq（高速推理）",
        provider="openai",
        model="openai/gpt-oss-120b",
        needs_key=True,
        sensitive_ok=False,
        base_url="https://api.groq.com/openai/v1",
        card_desc="gpt-oss-120b 免費（T2；30 RPM、14,400 RPD）",
        info="Groq 免費端（免綁卡）：gpt-oss-120b 免費、日額度 14,400 次充裕。"
        "瓶頸＝6,000 TPM——長文分塊翻譯容易撞限流 429，請開「重試」並縮小分塊。"
        "檔案上 Groq 雲端——機密文件不可用。",
    ),
    "openrouter": EngineSpec(
        id="openrouter",
        label="OpenRouter :free（翻譯最佳）",
        provider="openai",
        model="nvidia/nemotron-3-super-120b-a12b:free",
        needs_key=True,
        sensitive_ok=False,
        base_url="https://openrouter.ai/api/v1",
        card_desc="nemotron-3-super:free（T2；翻譯 86.7% WMT24++）",
        info="OpenRouter 免費端（免綁卡）：nemotron-3-super-120b 翻譯評測免費群最佳"
        "（WMT24++ 86.7%）；gemma-4-31b:free 長文友好。限流 20 RPM／50 RPD（充值 $10"
        " 終身升 1,000 RPD）——單日翻譯量大請升級。檔案上 OpenRouter 雲端——機密文件不可用。",
    ),
    "bigmodel": EngineSpec(
        id="bigmodel",
        label="智譜 BigModel（GLM 免費跑量）",
        provider="openai",
        model="glm-4.7-flash",
        needs_key=True,
        sensitive_ok=False,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        card_desc="GLM-4.7-Flash 免費（無 token 上限）",
        info="智譜官方免費端（實名後建 key）：GLM-4.7-Flash/GLM-4-Flash 永久免費、無 token"
        " 上限（併發 2——批次翻譯是天然限流）。品質存疑（第三方實測大幅退步）——"
        "請先試譯一段再決定。檔案上智譜雲端——機密文件不可用。",
    ),
    "gemini": EngineSpec(
        id="gemini",
        label="Google Gemini（gemma 長文）",
        provider="openai",
        model="gemma-4-31b-it",
        needs_key=True,
        sensitive_ok=False,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        card_desc="gemma-4-31b 免費（T2；15 RPM、1,500 RPD）",
        info="Google Gemini OpenAI 相容端點（ai.google.dev 免費層，免綁卡）：gemma-4-31b-it"
        " 免費、262K 長文、日額度 1,500 次（候選單模型最高）。⚠️ 免費層資料會用於"
        "「改進產品」＝資料訓練——未發表論文禁用（紅線）；額度政策近年頻繁緊縮。"
        "檔案上 Google 雲端——機密文件不可用。",
    ),
}

# P3：主頁引擎卡集合與顯示順序（票 19 明定三支 PDF 主引擎；latex 票 27 第 4 卡；
# ppt-vision 走特化路線）。app.py 只迭代此 tuple——加引擎單點。
UI_ENGINE_IDS: tuple[str, ...] = ("siliconflow", "deepseek", "babeldoc", "latex")

# 免費翻譯入口（2026-08-13）：主頁「免費翻譯（不需 API key）」區的卡集合與順序——
# 三支 needs_key=False 引擎（不變式測試把關：未來 keyless 引擎必須登記於此）。
# siliconflowfree 排首（上游預設、活躍）；google/bing 上游已棄用。app.py 只迭代此 tuple。
UI_FREE_ENGINE_IDS: tuple[str, ...] = ("siliconflowfree", "google", "bing")

# 免費 LLM key 引擎（2026-08-13，Free-LLM-Collection 查證後加入）：主頁「免費 LLM
# （自備免費 key）」區的卡集合與順序＝品質優先序（docs/research/2026-08-13-
# Free-LLM-Collection-查證與品質優先序.md §3）——NVIDIA NIM 居首（T1/T2 品質＋
# 40RPM＋無日總量）、Gemini 殿後（免費層資料訓練紅線，非敏感才可用）。
# 全走 provider=openai（pdf2zh --openai 三旗標）、BYOK（自申請免費 key 填入）。
# app.py 只迭代此 tuple——加引擎單點。
UI_FREE_KEY_ENGINE_IDS: tuple[str, ...] = (
    "nvidia", "modelscope", "groq", "openrouter", "bigmodel", "gemini",
)


def build_engine(
    spec: EngineSpec, api_key: str = "", term_api_key: str = ""
) -> Pdf2zhNextAdapter | BabelDocAdapter | PptVisionAdapter:
    """spec → adapter（引擎旗標對映在 adapter 內部，UI 不知情）。票 13/14：換插頭＝分派。

    #84：term_api_key＝術語提取引擎（SiliconFlow）獨立 key——只對
    Pdf2zhNextAdapter 有意義（term 旗標僅 siliconflow provider 發送，#83）。"""
    if spec.provider == "babeldoc":
        cfg = BabelDocConfig(
            model=spec.model,
            api_key=api_key,
            base_url=spec.base_url,
        )
        return BabelDocAdapter(cfg)
    if spec.provider == "ppt-vision":
        cfg = PptVisionConfig(
            api_key=api_key,
            model=spec.model,
            base_url=spec.base_url,
        )
        return PptVisionAdapter(cfg)
    if spec.provider == "latex":
        cfg = LatexConfig(
            api_key=api_key,
            model=spec.model,
            base_url=spec.base_url,
        )
        return LatexAdapter(cfg)
    cfg = EngineConfig(
        provider=spec.provider,
        model=spec.model,
        api_key=api_key,
        term_api_key=term_api_key,  # #84：術語提取獨立 key（空＝build_command 沿用主 key）
        base_url=spec.base_url,
    )
    return Pdf2zhNextAdapter(cfg)
