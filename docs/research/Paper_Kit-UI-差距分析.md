---
title: Paper_Kit UI 差距分析（對照 pdf2zh.com）
date: 2026-08-12
tags: [paper_kit, research, ui, 差距分析]
---

# Paper_Kit UI 差距分析（對照 pdf2zh.com）

> 使用者回饋（2026-08-12）：「你的介面為什麼這麼簡陋，對比 PDFMathTranslate 也差太多了」。
> 本分析回答：差在哪、哪些值得補、哪些不值得。對照標竿詳見 [[pdf2zh.com-線上GUI-盤點]]。

## 1. 現況盤點（Paper_Kit，commit `2b14eda`）

- **技術**：NiceGUI 3.15（WebSocket 推送、無整頁重載）＋ 三個路由（`/`、`/settings`、`/debug`）。
- **主頁 `/`**（`_index_page`，票 03 改良版）：
  - 上傳卡片：`ui.upload`（拖放或點選）＋「📂 開始翻譯」主按鈕（pickFiles）
  - 機密文件 checkbox＋掃描件 OCR checkbox＋頁面範圍輸入（+ 目標語言/術語表/成本估算在 /settings）
  - 任務卡片（`ui.timer(1.0)` 輪詢刷新）：狀態標籤、下載 mono/dual、瀏覽器內預覽（dialog）、↻ 重試、✕ 取消
  - 頁首導覽：設定 / Debug 連結
- **`/settings`**：引擎選擇＋API key 槽位、目標語言、預設頁數、輸出目錄、術語表管理（多份＋挑選＋編輯）、主題（深色）、成本估算顯示。
- **`/debug`**：log 檢視、過濾、重新整理。

## 2. 差距維度

### 2.1 版面／視覺（「簡陋感」的主要來源）

| 面向 | pdf2zh.com | Paper_Kit | 差距嚴重度 |
|---|---|---|---|
| 版面 | Gradio 單頁大卡片，選項全在同一視窗 | 多頁（/、/settings 分離） | 中——翻譯前要跳去 /settings 調參，來回切換 |
| 元件 | 專業 Gradio 控件 | NiceGUI 基礎控件 | 低——控件本身不差 |
| 文案 | 英文、簡潔 | 中文、功能性 | 低 |
| 品牌 | 無 | 標題「Paper_Kit 論文翻譯器」 | 低 |
| 排版 | 密集但有序 | 稀疏（每個卡片間距大） | 中——卡片之間沒有精緻的格線/分組 |

### 2.2 功能差距（詳見 [[pdf2zh.com-線上GUI-盤點]] 對照總表）

> **2026-08-12 一手驗證（`uv tool run pdf2zh_next --help`，v2.9.0）**：pdf2zh.com 線上 GUI 標示 **pdf2zh Version: 1.9.6 = 舊版**！其部分選項（如 Skip font subsetting）在 pdf2zh-next 2.9.0 CLI **已不存在**。照抄舊版 GUI 選項是陷阱——旗標一律以 v2.9.0 `--help` 為準。

**缺失（低成本、建議補）——已驗證旗標存在**：
1. **ignore cache 開關** → `--ignore-cache` ✅（help 確認：「Ignore translation cache」）
2. **threads 數輸入** → `--pool-max-workers` ✅（**不是** `--threads`，pdf2zh.com 舊 GUI 名）＋術語提取 `--term-pool-max-workers`
3. **Custom Prompt for llm** → `--custom-system-prompt` ✅（「Custom system prompt for translation… to guide translation style」）＋`--lang-in`（來源語言）
4. **快捷頁數**：First / First 20 pages / 自訂範圍（現只有自訂輸入）→ 皆映射 `--pages`
5. **skip font subsetting** → ❌ **v2.9.0 無此旗標**（舊版 1.9.6 才有）——不做
6. **URL 輸入模式**（貼遠端 PDF 連結）

**缺失（中成本、值得補）**：
7. **翻譯頁就地語言對選擇**（來源/目標語言下拉搬到主頁翻譯卡，不必跳 /settings）——`--lang-in`/`--lang-out` 都有旗標 ✅

**額外發現（help 中值得考慮的新功能）**：
- `--no-dual` / `--no-mono`：可關閉單/雙語輸出（省時間）
- `--dual-translate-first` / `--use-alternating-pages-dual`：雙語 PDF 版面模式
- `--translate-table-text`：表格文字翻譯（實驗）
- `--ocr-workaround` / `--auto-enable-ocr-workaround`：掃描件自動偵測＋OCR 替代處理
- `--figure-table-protection-threshold`：圖表保護閾值

**不需要**：
- reCAPTCHA（本機自用工具無防濫用需求）
- Gradio 本身（NiceGUI 是優選，見 [[2026-08-12-Paper_Kit-計畫]]）

## 3. 建議改善計畫（分三批，每批可獨立交付）

### 批 A：版面精緻化（0 新功能，立即可做）
- 主頁改兩欄佈局：左 = 翻譯卡（上傳＋選項），右 = 任務清單
- 翻譯卡內收斂選項：語言對、頁數、機密/OCR 開關**就地呈現**（不再全藏 /settings）
- 卡片加一致的邊框/陰影/圓角樣式類（`pk-card` 統一）
- 狀態標籤彩色化（轉錄中=藍、完成=綠、失敗=紅——使用者先前截圖要求的 badges）

### 批 B：實驗選項（對齊 pdf2zh.com Experimental 區，旗標已 v2.9.0 驗證）
- 設定頁新增「進階」區塊：ignore cache（`--ignore-cache`）、threads（`--pool-max-workers`）、custom prompt（`--custom-system-prompt`）、來源語言（`--lang-in`）
- TranslationJob/EngineConfig 加欄位 → `build_command` 對應旗標
- 每旗標都要 adapter 測試（TDD，沿用 [[2026-08-12-Paper_Kit-Daily-Note]] 測試慣例）
- ❌ skip font subsetting 不做了（v2.9.0 無此旗標，舊版 1.9.6 才有）

### 批 C：輸入模式擴充
- URL 輸入（link 模式）：下載 → 暫存 → 走同一條 create_job 路徑
- 快捷頁數三選（First / First 20 / range）

## 4. 優先序建議

1. **批 A 就地選項 + 版面**——直接回應「簡陋」回饋，零引擎風險
2. **批 B ignore cache + threads**——使用者重翻同一檔案時最有感（省錢＋省時）
3. **批 C**——有餘力再做

> 關聯：規格書 user stories 目前未含「翻譯頁就地選項」與「實驗選項」——補做時需先入規格（[[2026-08-12-Paper_Kit-計畫]] 票制）。本分析暫列研究層，待使用者決定是否開新票。
