"""任務建立：把使用者意圖變成一個已備妥的任務，或一個帶理由的拒絕
（架構深化候選 1，2026-08-19）。

**為什麼存在**：這些規則原本住在 `presentation/app.py:_start_job`——一百行 UI
函式裡塞著十條應用層規則（頁碼驗證、引擎與格式相容、機密紅線、OCR 適用性、
掃描件偵測、術語表掛載、估價），而且與 `ui.notify(...)` 逐行交錯。

後果不是「不好看」，是**規則無法在沒有 NiceGUI 的情況下被求值**：要驗
「機密文件不可用視覺引擎」就得渲染整頁（`test_index_page.py` 因此長到 1,675 行）。
機密紅線甚至在同一個函式裡被算了兩次（不同參數），service 內還有第三次兜底——
同一條規則散在三處，改一次要記得改三處。

**這個 module 的形狀**（grilling Q5／Q10／Q11 定案）：

- 拒絕是**回傳值**不是例外。使用者選錯引擎是預期中的正常結果，不是異常狀況；
  用例外會讓正常流程走 traceback。`EngineError` 留給真正的異常。
- 結果同時帶 `warnings`：有些判斷（這份 PDF 沒有文字層、OCR 旗標對非 PDF 無效）
  不阻止任務建立，但它們是**領域判斷**不是 UI 判斷，留在 UI 等於規則又散回去。
- **會產生副作用**：建任務、掛術語表、估價、啟動引擎。純決策版本聽起來乾淨，
  但會把「建任務→掛術語表→估價→啟動」這串順序留在 UI，也就是換個包裝的同一個問題。
  「任務建立」是一件完整的事，不是一個計算。

**引擎能力當資料收下**：application 層不查 `ENGINE_SPECS`（票 10 既有慣例——
相容性由持有 registry 的呼叫端聲明）。引擎解析本身留在 UI，因為錯誤訊息是
registry-bound；解析完把 `EngineChoice` 交進來。
"""

from dataclasses import dataclass, field
from pathlib import Path

from paper_kit.application.cost_service import CostEstimate, CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.ocr import has_text_layer, is_pdf_path
from paper_kit.application.pages import parse_pages
from paper_kit.application.ports import TranslationEnginePort
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.translation_job import TranslationJob


@dataclass(frozen=True)
class IntakeRequest:
    """使用者的意圖。file_path/file_name 必填；其餘皆有預設。

    （原 `presentation.handlers.StartJobParams`，隨規則一起搬進 application——
    handlers 保留 `StartJobParams` 別名以維持既有 import。）
    """

    file_path: str | Path
    file_name: str
    pages_text: str = ""
    total_pages: int | None = None  # #27：翻譯頁數（進度框「N/M 頁」的 N）
    pdf_pages: int | None = None    # #27：PDF 總頁數（歷史頁「N/M 頁」的 M）
    sensitive: bool = False
    ocr: bool = False
    engine_id: str | None = None    # 票 19：引擎卡點選（None=設定頁 global）
    target_lang: str | None = None  # 票 19：語言下拉就地選（None=設定頁值）
    only_selected_pages: bool = True  # #85：僅翻譯選中頁面 toggle
    # #85 切片C：babeldoc 進階選項（僅 babeldoc 引擎消費；其他引擎忽略）
    enhance_compatibility: bool = False
    merge_alternating_line_numbers: bool = True
    remove_non_formula_lines: bool = False
    font_family: str = "serif"


@dataclass(frozen=True)
class EngineChoice:
    """已解析好的引擎，以及它的能力宣告（由持有 registry 的呼叫端提供）。"""

    engine_id: str
    engine: TranslationEnginePort
    allows_sensitive: bool  # 票 10 紅線：能否處理機密文件（fail-closed，未知＝False）
    tex_only: bool = False  # 票 27：僅適用 .tex 源碼（latex 引擎）


@dataclass(frozen=True)
class IntakeResult:
    """建立結果：接受（帶任務、可能帶警告）或拒絕（帶理由）。

    刻意不是 `(job | None, error | None)` tuple——那種形狀允許呼叫端忘記檢查。
    """

    job: TranslationJob | None = None
    rejection: str | None = None
    warnings: tuple[str, ...] = ()
    estimate: CostEstimate | None = None  # 票 06：UI 顯示估算明細用

    @property
    def accepted(self) -> bool:
        return self.job is not None


def _rejected(reason: str) -> IntakeResult:
    return IntakeResult(rejection=reason)


def _is_tex(name: str | Path) -> bool:
    return Path(name).suffix.lower() == ".tex"


class JobIntake:
    """任務建立的單一真相。不知道 `ui` 的存在，因此可以直接以值測試。"""

    def __init__(
        self,
        service: JobService,
        settings: SettingsService,
        cost: CostService,
        glossaries: GlossaryService,
    ):
        self._service = service
        self._settings = settings
        self._cost = cost
        self._glossaries = glossaries

    def submit(self, request: IntakeRequest, choice: EngineChoice) -> IntakeResult:
        """驗證 → 建立 → 啟動。回傳拒絕理由，或已備妥並已啟動的任務。"""
        # 票 07：頁面範圍驗證先於建任務（非法格式不留下半途任務）
        try:
            pages = parse_pages(request.pages_text)
        except ValueError as exc:
            return _rejected(str(exc))

        # 票 27：LaTeX 引擎僅適用 .tex 源碼——前置擋下，不悄悄 fallback 到別支
        # 引擎（#83 靜默誤動作教訓：使用者以為在用 A，實際被換成 B）
        if choice.tex_only and not _is_tex(request.file_name):
            return _rejected("LaTeX 引擎僅適用 .tex 源碼——PDF 請選上方三引擎")

        # 票 10 紅線：機密文件只准純文字引擎。fail-closed 由呼叫端的 allows_sensitive
        # 承擔（未知引擎聲明為 False）。這裡只算一次——原本 UI 內算了兩次、
        # service.start 再算第三次。
        if request.sensitive and not choice.allows_sensitive:
            return _rejected("機密文件只可使用 DeepSeek 純文字引擎（先到設定切換引擎）")

        warnings: list[str] = []
        ocr = request.ocr
        # 票 14：OCR 只適用 PDF——勾了但上傳非 PDF → 警告並忽略旗標（不阻止建立）
        if ocr and not is_pdf_path(request.file_name):
            warnings.append("🔍 掃描件 OCR 僅適用 PDF——已忽略（PPT 走視覺翻譯）")
            ocr = False

        job = self._service.create_job(
            request.file_path,
            target_lang=request.target_lang or self._settings.target_lang(),
            pages=pages,
            total_pages=request.total_pages,
            pdf_pages=request.pdf_pages,
            output_dir=self._settings.output_dir(),
            sensitive=request.sensitive,
            ocr=ocr,
            only_selected_pages=request.only_selected_pages,
            enhance_compatibility=request.enhance_compatibility,
            merge_alternating_line_numbers=request.merge_alternating_line_numbers,
            remove_non_formula_lines=request.remove_non_formula_lines,
            font_family=request.font_family,
        )

        # 票 12 AC1：無文字層且未勾 OCR → 提示（照常建立，使用者可重試）。
        # 票 14：只對 PDF 偵測（pptx 不誤報掃描件）
        if (
            not ocr
            and job.source_path
            and is_pdf_path(job.source_path)
            and not has_text_layer(job.source_path)
        ):
            warnings.append(
                "⚠️ 偵測為掃描件（無文字層）——翻譯可能產出空白；建議勾選 🔍 OCR 重試"
            )

        # 票 05：術語表組合與自動提取開關隨任務凍結（之後改設定不影響舊任務）
        names = self._settings.selected_glossary_names(self._glossaries.list_glossaries())
        job.glossary_files = self._glossaries.paths_for(names)
        job.auto_extract = self._settings.auto_extract()

        # 票 07：指定頁面範圍時估價按範圍縮放；術語表 → tokens 依實測倍率上調
        estimate = self._cost.estimate_for_pdf(
            choice.engine_id, request.file_path, pages=pages,
            glossary=bool(job.glossary_files),
        )
        if estimate is not None:
            # 存下前置估算：完成後要比對的是「使用者當初看到的」那個數字
            job.estimated_cost = estimate.cost
            job.estimated_tokens = estimate.total_tokens

        self._service.start(
            job.job_id,
            choice.engine,
            engine_id=choice.engine_id,
            engine_allows_sensitive=choice.allows_sensitive,
        )
        return IntakeResult(job=job, warnings=tuple(warnings), estimate=estimate)
