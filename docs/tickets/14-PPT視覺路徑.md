# 14 — Phase 2：PPT 視覺路徑

**What to build:** 簡報翻譯：幻燈片→圖→gemma 眼睛（SiliconFlow 視覺）逐頁翻譯→雙語注記 PDF，設計版面 100% 保留；成本與用量照常記錄。

**Blocked by:** 04, 06

**Status:** ✅ done（2026-08-12，331 測試全綠，兩軸 review 全部套用）

- [x] PPT 上傳→拆圖→gemma 視覺翻譯→輸出（10 張 fixture 驗證）
- [x] 版面保留（設計不變）、譯文可讀
- [x] 成本記錄入歷史

## 實作

### 管線（Ports & Adapters，第三支引擎插頭）

1. **PptToImagePort（LibreOfficeConverter）**：`.pptx` → soffice headless 轉 PDF → pymupdf 逐頁 render PNG（zoom 2x ≈ 1920px）。soffice 是系統依賴（本機 winget 已裝）；缺 soffice 給友善 EngineError（含安裝指引）。WSL interop 事實：soffice.exe 是 Windows 程式收不到 `/mnt/c/...` → 命令組裝時 wslpath -w 轉 `C:\` 形式
2. **VisionTranslatorPort（SiliconFlowVisionTranslator）**：單頁圖 → 繁中譯文＋tokens。模型鏈照 paste-vision 立法（Vault CLAUDE.md §8 fallback）：`google/gemma-4-31B-it`（40s 逾時）→ `google/gemma-4-12B-it`（8s）備援；`max_tokens 2000, temperature 0.1`；401/無效 key → 友善錯誤「API key 無效或已過期」；usage 缺 tokens → 0（不炸成本）
3. **組裝（build_notes_pdf）**：新 PDF——每頁 = 原圖全幅（**設計 100% 保留，非 bbox 覆蓋**）＋下方 400px 譯文注記區。CJK 用 pymupdf 內建 `china-t` 子集字體（Helvetica 中文變 '?'，票 12 教訓）

### 設計決策

- **雙語注記（非覆蓋文字層）**：POC-4 通過標準「版面保留＋譯文可讀」的最務實達成——覆蓋需要 bbox 對位（圖上定位），注記零風險保證設計原樣
- **產出單一**：mono = 注記版 PDF、dual = None → UI dual 下載按鈕條件化（`if view.dual_url`）
- **registry-driven**：`"ppt-vision": EngineSpec(provider="ppt-vision", needs_key=True, sensitive_ok=False)` → UI 引擎下拉自動出現（票 13/14 AC2 模式）；build_engine 以 provider 分派
- **紅線 sensitive_ok=False**：視覺 = 圖片上雲端（票 10 紅線，同 paste-vision）→ registry/UI（`_start_job` 早攔含 retry）/JobService（fail-closed，None 也拒）三層攔截
- **缺 key 早期檢查**：`translate` 開頭 `if not self._config.api_key: raise EngineError(MISSING_API_KEY_MESSAGE)`（同 CliAdapterBase 模式，不白跑 soffice）
- **成本**：DEFAULT_PRICING 新增 ppt-vision（0.0012/0.0012/5000）；tokens 累加 → JobResult → CostService 既有路徑（JobService/StartTranslation 零改動，AC3 守證）
- **掃描件偵測相容**：`is_pdf_path` predicate 收攏（ocr.py 共用）；has_text_layer 對非 PDF 回 False——pptx 上傳不誤報、OCR 偵測不炸

### POC-4 驗證（2026-08-12）

真 10 頁 pptx（python-pptx 造）→ 真 soffice → 10 張 PNG（依頁序 slide-01..10）→ FakeVision 全鏈 → 10 頁注記 PDF（每頁有圖、譯文可提取）。slow 冒煙 2 passed（5.3s）。

## 兩軸 review 紀錄

**Standards 軸**（無硬違規；4 項判斷調全收）：
- `is_pdf_path` predicate 收攏（app.py endswith vs ocr.py suffix 兩處散落 → 共用）
- 「尚未設定 API key」訊息 3 處重複 → `MISSING_API_KEY_MESSAGE`（ports.py）共用
- test_ppt_converter 恆真斷言 `"\\" in cmd or "/" in cmd` → 收斂為有意義斷言
- 函式內 import 移頂部（對齊 repo 慣例）
- 接受現狀：模型鏈與 paste-vision hook 同形狀（跨 repo 共用反而 Speculative Generality）；測試測 `_config.api_key` 私有屬性（既有模式照抄）

**Spec 軸**（3 AC 全過＋2 核心 bug 修復）：
- AC1 10 張 fixture 存在且端到端（真 soffice，FakeVision 自選省錢——真實 API 無自動測試，屬已知取捨，記入）
- AC2 版面保留 ✓（原圖嵌入像素級）；**譯文可讀 bug 實測修復**：insert_textbox 溢位（>850 字/頁）回負值＝整段文字消失、任務仍 COMPLETED → build_notes_pdf 自動分頁（18px 固定字號可讀性優先，「（譯文續）」續頁），1400 字測試全文保留
- AC3 成本 ✓ JobService 零改動；sensitivive 紅線三層全攔 ✓
- **pptx＋勾 OCR bug 修復**：pypdf FileDataError 任務必敗 → ensure_text_layer 對非 PDF 安全跳過回 None（application 兜底）＋ _start_job 警告「僅適用 PDF——已忽略」（UI 雙保險）
- 次要已知取捨：soffice 轉換中 cancel 無法中止子程序（≤180s）；`ppt/` 工作目錄殘留（debug 用）；AC1 驗證在 slow 圈外（repo 無 CI）；uv.lock 補入 rapidocr 傳遞依賴（票 12 遺留）

## 測試

331 passed（329→331，+2 修復測試），24.10s；slow 3 passed（含真 soffice 冒煙 2）。新增：test_siliconflow_vision.py（7）、test_ppt_converter.py（6）、test_ppt_vision_adapter.py（8）、test_ppt_vision_smoke.py（2 slow）、ocr/settings/cost/engine_registry 各 1-3。

**commit:** `8246df0`（票 14 完成：PPT 視覺路徑（331 tests green），20 files，+1476/-15）
