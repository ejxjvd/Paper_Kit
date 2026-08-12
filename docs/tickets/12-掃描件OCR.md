# 12 — Phase 2：掃描件 OCR

**What to build:** 沒有文字層的 PDF（整頁圖片）也能翻：RapidOCR 選項讓掃描件走 OCR→翻譯流程。

**Blocked by:** 03

**Status:** ✅ done（2026-08-12，280 測試全綠）

- [x] 掃描件偵測（無文字層提示）
- [x] OCR 流程（RapidOCR）→ 翻譯 → 產出（以 fixture 掃描件驗證）

**實作**：垂直切片——OCR 產出「有文字層的 PDF」，既有 pdf2zh 翻譯管線零改動（ocrmypdf 同款做法，排版由 pdf2zh 版面分析接手，不需精確 bbox 對位）。`application/ocr.py`（新）——`has_text_layer` 偵測（pypdf 逐頁提取，AC1）＋`OcrService.ensure_text_layer`（偵測→OCR→overlay，回 OCR 版或 None＝原檔不動；**空 OCR 結果拒絕產出空白文字層**——spec review）；`infrastructure/rapidocr_adapter.py`（新）——RapidOCR 本機 onnxruntime，**不上雲端視覺 API＝機密文件相容**（lazy import＋engine 注入：render 管線可測、不載真實模型）；`infrastructure/pdf_overlay.py`（新）——pymupdf 隱形文字層（alpha=0），**fontname="china-t"**（內建 CJK 子集字體——Helvetica 無 CJK glyph、中文會變 `?`，spec review 實測抓出）；`JobService`——`ocr` flag 隨任務記錄（SQLite `_COLUMNS` 遷移自動涵蓋）、`_prepare_ocr` 執行前預處理、未注入 OCR 服務（無頭模式）→ 明確失敗不靜默（spec review）；UI——🔍 OCR checkbox＋上傳時無文字層 toast 提示（AC1）＋任務卡片 🔍 徽章。**AC2 驗證**：掃描件 fixture（圖像頁）實測 5.0s：偵測→RapidOCR（模型自動下載）→內嵌→pypdf 可提取 OCR 文字，slow 冒煙測試留檔（inline 造圖——PDF fixture 被 .gitignore 排除的既有慣例）。依賴：pymupdf＋rapidocr_onnxruntime。兩軸 review（spec 3 項：CJK 字體硬問題、空 OCR 守護、未注入明確失敗；standards 3 項：conftest 抽共用 make_blank_pdf fixture、lazy import 註解校正、import 順序）全部套用。
