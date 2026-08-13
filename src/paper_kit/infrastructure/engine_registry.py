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
    ),
    "google": EngineSpec(
        id="google",
        label="Google 免費引擎",
        provider="google",
        model="",
        needs_key=False,
        sensitive_ok=False,
    ),
    "bing": EngineSpec(
        id="bing",
        label="Bing 免費引擎",
        provider="bing",
        model="",
        needs_key=False,
        sensitive_ok=False,
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
}

# P3：主頁引擎卡集合與顯示順序（票 19 明定三支 PDF 主引擎；latex 票 27 第 4 卡；
# ppt-vision 走特化路線、free 引擎不設卡）。app.py 只迭代此 tuple——加引擎單點。
UI_ENGINE_IDS: tuple[str, ...] = ("siliconflow", "deepseek", "babeldoc", "latex")


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
