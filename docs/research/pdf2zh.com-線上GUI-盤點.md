---
title: pdf2zh.com 線上 GUI 盤點
date: 2026-08-12
tags: [paper_kit, research, pdf2zh, gui]
---

# pdf2zh.com 線上 GUI 盤點

> 來源：使用者桌機保存頁面 `PDFMathTranslate - PDF Translation with preserved formats.html`（128KB，pdf2zh.com 線上 GUI 快照）＋ `/tmp/pdf2zh_gui.txt`（47 行結構擷取）。
> 用途：Paper_Kit UI 對照標竿（使用者回饋「你的介面為什麼這麼簡陋」的直接參考物件）。

## 1. 頁面整體結構

線上 GUI 是 **Gradio 建構的單頁應用**（頁尾自述「使用Gradio構建」），由上而下：

```
PDFMathTranslate - PDF Translation with preserved formats
├─ 頁首：標題 + PDFMathTranslate @ GitHub 連結
├─ 輸入區
│   ├─ Type：File / Link（radio 切換輸入模式）
│   ├─ 上傳槽：拖放檔案至此處 - 或 - 點擊上傳（File | < 5 MB 限制）
│   └─ Link 文字框（URL 輸入）
├─ Option 區（可展開）
│   ├─ Service 下拉（預設 Google）
│   ├─ Translate from / Translate to 下拉
│   └─ Pages：First / First 20 pages / Page range
├─ 「Open for More Experimental Options!」展開
│   └─ Experimental 區
│       ├─ number of threads
│       ├─ Skip font subsetting
│       ├─ Ignore cache
│       ├─ Custom Prompt for llm
│       └─ Use BabelDOC
├─ Translated 區：Download Translation (Mono) / (Dual)
├─ reCAPTCHA Response（人機驗證）
├─ Translate / Cancel 按鈕
├─ Technical details
│   ├─ GitHub: Byaidu/PDFMathTranslate
│   ├─ BabelDOC: funstory-ai/BabelDOC
│   ├─ GUI by: Rongxin
│   ├─ pdf2zh Version: 1.9.6
│   └─ BabelDOC Version: 0.2.4
├─ Preview / Document Preview（文件預覽）
└─ 頁尾：Use via API · 使用Gradio構建 · Settings
```

## 2. 各區功能細節

### 2.1 輸入模式（Type: File / Link）
- **File**：拖放或點擊上傳，限制 **< 5 MB**、單檔。
- **Link**：改貼 URL（遠端 PDF）。
- 對 Paper_Kit 啟示：**URL 輸入模式**目前沒有（Paper_Kit 只收本機檔）。

### 2.2 翻譯選項（Option）
- **Service 下拉**：選擇翻譯後端（Google／DeepL／ChatGPT／Gemini 等——pdf2zh 家族服務清單，見 [[PDFMathTranslate-next-架構研究]]）。
- **Translate from / to**：來源語言／目標語言兩個獨立下拉。
- **Pages** 三選一：
  - `First`（只翻第一頁）
  - `First 20 pages`（前 20 頁）
  - `Page range`（自訂範圍輸入）
- 對 Paper_Kit 啟示：Paper_Kit 已有頁面範圍（`--pages`），但沒有「只翻第一頁／前 N 頁」的快捷選項。

### 2.3 實驗選項（Experimental）
- **number of threads**：並行執行緒數（速度／成本槓桿）。
- **Skip font subsetting**：跳過字型子集化（產出較大、速度較快）。
- **Ignore cache**：忽略翻譯快取（強制重翻）。
- **Custom Prompt for llm**：**自訂 LLM 提示詞**——使用者可直接給翻譯引擎下指令。
- **Use BabelDOC**：切換到 BabelDOC 引擎（[[2026-08-12-Paper_Kit-研究-BabelDOC]]）。
- 對 Paper_Kit 啟示：**五項目前全無**——threads、skip font subsetting、ignore cache、custom prompt、BabelDOC 切換。後三者是低成本高價值（Paper_Kit 已有 BabelDOC adapter，只差 UI 切換）。

### 2.4 輸出（Translated）
- 翻譯後提供 **Download (Mono)** 與 **Download (Dual)** 兩個下載按鈕——單語版／雙語對照版。
- 對 Paper_Kit 啟示：**完全一致**（Paper_Kit 完成卡片已有「下載 mono / 下載 dual」，見票 03）。

### 2.5 其他
- **reCAPTCHA Response**：人機驗證（防濫用——線上免費服務的必要之惡；自架/本機工具不需要）。
- **Technical details**：版本資訊公開（pdf2zh 1.9.6、BabelDOC 0.2.4、GUI 作者）。
- **Preview / Document Preview**：翻譯前後的文件預覽。
- **Use via API**：附 API 使用指引（對接 PDFMathTranslate 後端）。
- **Settings**：設定入口。

## 3. 與 Paper_Kit 現況對照總表

| 功能 | pdf2zh.com | Paper_Kit（2026-08-12） | 差距 |
|---|---|---|---|
| 檔案上傳（拖放/點擊） | ✅（<5MB 限制） | ✅ 拖放＋點擊（卡片化） | 一致 |
| 開始翻譯主按鈕 | ✅ Translate | ✅ 📂 開始翻譯（新增） | 一致 |
| 任務取消 | ✅ Cancel | ✅ 任務卡片 ✕ 取消 | 一致 |
| 下載 mono / dual | ✅ | ✅ | 一致 |
| 瀏覽器預覽 | ✅ Preview | ✅ 瀏覽器內預覽（dialog 90vw×90vh） | 一致 |
| Service 選擇 | ✅ 下拉 | ✅ 引擎選擇頁（SiliconFlow/DeepSeek/BabelDOC） | 一致（多了 API key 管理） |
| 語言對 | ✅ from/to 下拉 | ✅ 目標語言（defaults） | 部分（Paper_Kit 無來源語言選項） |
| 頁面範圍 | ✅ First/20/range | ✅ 頁面範圍輸入 | 部分（缺快捷選項） |
| URL 輸入 | ✅ Link | ❌ | **缺** |
| threads 數 | ✅ | ❌ | **缺**（低成本，旗標 `--pool-max-workers` 已驗證） |
| skip font subsetting | ✅ | ❌ | **不需要**——舊版 1.9.6 選項，pdf2zh-next 2.9.0 CLI 已無此旗標 |
| ignore cache | ✅ | ❌ | **缺**（低成本，`--ignore-cache` 已驗證） |
| Custom Prompt for llm | ✅ | ❌ | **缺**（中成本——`--custom-system-prompt` 已驗證） |
| Use BabelDOC 切換 | ✅ | ⚠️ 引擎選擇頁可選 BabelDOC | 部分（入口在設定頁非翻譯頁） |
| 人機驗證 | ✅ reCAPTCHA | ❌（本機工具不需要） | 不需要 |
| 版本資訊公開 | ✅ | ⚠️ Debug 頁有 | 部分 |
| 深色模式 | ❌（Gradio 無） | ✅ 主題美化（票 11） | Paper_Kit 領先 |

## 4. 結論（供 [[Paper_Kit-UI-差距分析]] 使用）

pdf2zh.com 的 **核心流程（上傳 → 選項 → 翻譯 → mono/dual 下載）Paper_Kit 已全數具備**；差距集中在三塊：
1. **翻譯頁就地選項**（pdf2zh 全在一個頁面完成；Paper_Kit 引擎/語言在 /settings）——體驗流暢度差距。
2. **實驗選項**（threads / ignore cache / custom prompt / BabelDOC 切換）——功能面差距。
3. **URL 輸入、快捷頁數**——小功能差距。

> 附註：pdf2zh.com 是 Gradio 單頁 demo；Paper_Kit 是 NiceGUI 多頁（/、/settings、/debug）。「簡陋感」部分來自版面而非功能缺失——見差距分析的版面建議。
