---
title: PDFMathTranslate／pdf2zh 知識庫總索引
date: 2026-08-12
tags: [paper_kit, research, index]
---

# PDFMathTranslate／pdf2zh 知識庫總索引

> 使用者指令（2026-08-12）：「你必須全部統整成MD檔案，不限制你創立幾個，我要求你把全部知識都補上」＋「你的介面為什麼這麼簡陋，對比PDFMathTranslate也差太多了」。
> 第二波指令（同日）：沉浸式翻譯（immersivetranslate.com）10 頁逐字轉錄＋桌機三份 HTML「通通給我參考並將資料存放於MD檔案（資料要完整）」。
> 本知識庫 = 全部一手來源研究（含桌機保存頁、CLI 實跑驗證）＋兩份 UI 差距分析。

## 研究範圍（覆蓋的全部來源）

| # | 來源 | 覆蓋檔 |
|---|---|---|
| 1 | https://docs.siliconflow.cn/en/usercases/use-siliconcloud-in-pdfmathtranslate-next | [[pdf2zh-next-官方文件統整]] §2 |
| 2 | https://github.com/PDFMathTranslate/PDFMathTranslate-next | [[PDFMathTranslate-next-架構研究]] |
| 3 | https://pdf2zh.com/ ＋ 桌機保存 HTML（PDFMathTranslate - PDF Translation with preserved formats.html） | [[pdf2zh.com-線上GUI-盤點]] |
| 4 | https://pdf2zh-next.com/zh/index.html | [[pdf2zh-next-官方文件統整]] §3 |
| 5 | https://pdf2zh-next.com/zh/getting-started/USAGE_webui.html | [[pdf2zh-next-官方文件統整]] §4 |
| 6 | **一手 CLI 實跑**：`uv tool run pdf2zh_next --help`（v2.9.0，233 旗標） | [[pdf2zh-next-CLI旗標參考]] |
| 7 | 補充一手：官方文件站 7 頁＋GitHub 源碼（pyproject/高階 API/引擎 metadata/快取實作） | [[PDFMathTranslate-next-架構研究]] |

## 知識庫檔案地圖

1. **[[PDFMathTranslate-next-架構研究]]**（601 行）——專案定位、架構、引擎 metadata、執行模型、SQLite 快取、進度事件流、與 1.x 差異、Paper_Kit 可借鏡 11 項
2. **[[pdf2zh-next-官方文件統整]]**（275 行）——SiliconCloud 整合、首頁、WebUI 使用、TOML 設定檔、環境變數映射、進階參數表
3. **[[pdf2zh-next-CLI旗標參考]]**（131 行）——v2.9.0 全旗標整理（33 段落/233 旗標），build_command 對照表
4. **[[pdf2zh.com-線上GUI-盤點]]**（111 行）——線上 GUI 全元素盤點＋對照總表
5. **[[Paper_Kit-UI-差距分析]]**（85 行）——簡陋感來源分析、三批改善計畫（版面／實驗選項／輸入模式）
6. **[[沉浸式翻譯-網頁UI盤點]]**——10 頁逐字轉錄全保留（文件/圖片/PDF Pro/PDF/ePub/字幕/Zotero/Google Workspace/Mega Menu/下載）
7. **[[沉浸式翻譯-產品結構與BabelDOC]]**——BabelDOC 四賣點、引擎清單、FAQ 標題、全產品線、下載平台、公司資訊
8. **[[沉浸式翻譯-翻譯記錄表格]]**——歷史表格欄位＋10 筆實際資料＋批量操作知識點
9. **[[沉浸式翻譯-與Paper_Kit-差距分析]]**——批 0（歷史表格化）＋批 A/B/C 合併計畫

## 統整結論（跨檔知識）

### 1. 兩代關係（關鍵脈絡）
- **pdf2zh 1.x**（線上 GUI 用的 1.9.6）→ **pdf2zh-next 2.x**（後繼，PyPI `pdf2zh-next`；GitHub main 分支 pyproject 2.8.2，`uv tool run` 實裝 **2.9.0**——官方文件/源碼略舊於實際發布，一律以實跑 `--help` 為準）。
- next 基於 **BabelDOC 後端**（`babeldoc>=0.5.20,<0.6.0`）、**AGPL-3.0**。
- **1.x 旗標在 next 已消失**：`--threads`、`--jora`、`--scihub`、`--llm`、`--webui`、`--skip-font-subsetting`。並行改 `--qps`/`--pool-max-workers` 速率模型（官方調校公式 pool = qps×10）；Bing/Google 標記棄用；免費方案 = `--siliconflowfree`（GLM-4-9B，經維護者 awwaawwa 伺服器代理）。

### 2. 核心架構（next）
- **metadata 驅動 25 引擎**：`--siliconflow`、`--openai`、`--deepseek`、`--openaicompatible`（自訂入口）等 22+ 服務，各帶 model/base-url/api-key/timeout/temperature/json-mode 家族＋`--term-<svc>-*` 術語提取對應。
- **SQLite 翻譯快取**：key = 引擎＋參數＋原文 → `--ignore-cache` 強制重翻。**Paper_Kit 目前完全沒有快取——最大可借鏡項**。
- **分片翻譯**（`--max-pages-per-part`）；**高階 API** `do_translate_async_stream` 事件流（stage/overall progress、finish 含 token 用量）——Paper_Kit 若未來直連 Python API 可改輪詢為事件驅動。
- **設定檔 TOML**（`~/.config/pdf2zh/config.toml`），優先序 cli/gui > env > user > default；環境變數映射 `--foo-bar` → `PDF2ZH_FOO_BAR=TRUE`。

### 3. UI 差距（使用者「簡陋」回饋）
- 核心流程（上傳→選項→翻譯→mono/dual 下載）**Paper_Kit 已全數具備**；差距＝①選項分散在 /settings ②實驗選項缺失 ③版面精緻度。改善計畫見 [[Paper_Kit-UI-差距分析]]（批 A 版面／批 B 實驗選項／批 C URL 輸入）。
- **陷阱已排除**：skip font subsetting 等 1.9.6 選項在 2.9.0 不存在，不照抄；threads 的 2.9.0 名字 = `--pool-max-workers`。

### 4. Paper_Kit 可借鏡清單（合併兩份研究的「關聯」章節）
1. **翻譯快取**（SQLite，最省錢項——重翻同一檔免費）
2. **並行調參**（`--pool-max-workers`/`--qps`）
3. **custom system prompt**（`--custom-system-prompt`）
4. **來源語言**（`--lang-in`，目前只送 lang-out）
5. **進度事件契約**（stream 事件流 vs 輪詢）
6. **單/雙語輸出開關**（`--no-dual`/`--no-mono`）
7. **OCR workaround 自動偵測**（`--auto-enable-ocr-workaround`）
8. **表格文字翻譯**（`--translate-table-text`，實驗）
9. **頁面進階語法**（`--pages '1,2,1-,-3,3-5'`，負數＝倒數頁）
10. **engine Port 設計對照**（metadata 驅動 vs Paper_Kit Ports&Adapters——方向一致，Paper_Kit 的 retry/逾時/遮罩反而更強）

### 5. 授權提醒
- pdf2zh-next/BabelDOC 皆 **AGPL-3.0**——Paper_Kit 透過 CLI 子程序呼叫（非連結/修改其程式碼），風險可控；若未來改 import 其 Python 模組，須重新評估授權衝擊。

## 後續建議（新票候選，見 [[2026-08-12-Paper_Kit-計畫]] 票制）

- 票 A：**翻譯快取**（SQLite 存 job 的輸入指紋→輸出，重翻同檔直接回）
- 票 B：UI 批 B 實驗選項（ignore cache / threads / custom prompt / lang-in）
- 票 C：UI 批 A 版面精緻化（就地選項＋雙欄＋狀態 badges）
