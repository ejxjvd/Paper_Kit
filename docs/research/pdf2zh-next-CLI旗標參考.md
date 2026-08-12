---
title: pdf2zh-next v2.9.0 CLI 旗標參考
date: 2026-08-12
tags: [paper_kit, research, pdf2zh, cli, reference]
---

# pdf2zh-next v2.9.0 CLI 旗標參考

> **一手來源**：2026-08-12 `uv tool run pdf2zh_next --help`（WSL 實跑，版本 `pdf2zh-next version: 2.9.0`）。33 段落、233 旗標。
> 用途：Paper_Kit `build_command` 對照表（見 [[PDFMathTranslate-next-架構研究]] 與 [[Paper_Kit-UI-差距分析]]）。
> ⚠️ 對照陷阱：pdf2zh.com 線上 GUI 標示 pdf2zh **1.9.6（舊版）**，其「Skip font subsetting」等選項在 2.9.0 **已不存在**——以本檔為準。

## 1. Basic（應用基本）

| 旗標 | 說明 |
|---|---|
| `input-files` | 輸入 PDF（位置參數） |
| `--debug` | 除錯模式 |
| `--gui` | 啟動 GUI 模式（pdf2zh-next 自帶 WebUI！） |
| `--warmup` | 只下載驗證必要資產後退出 |
| `--generate-offline-assets DIR` | 產生離線資產包到指定目錄 |
| `--restore-offline-assets FILE` | 從離線資產包還原 |
| `--version` | 顯示版本 |
| `--config-file FILE` | 設定檔路徑 |

## 2. Translation（翻譯核心）

| 旗標 | 說明 |
|---|---|
| `--min-text-length N` | 最小翻譯文字長度 |
| `--rpc-doclayout HOST` | 文件版面分析 RPC 服務 |
| `--lang-in CODE` | **來源語言**（Paper_Kit 目前未用） |
| `--lang-out CODE` | 目標語言（Paper_Kit 已用：zh-TW） |
| `--output DIR` | 輸出目錄 |
| `--qps N` | 翻譯服務 QPS 上限（並行控速） |
| `--ignore-cache` | **忽略翻譯快取**（強制重翻） |
| `--custom-system-prompt TEXT` | **自訂系統提示詞**（例：Qwen 3 加 `/no_think`；guide translation style） |
| `--glossaries LIST` | 術語表檔清單（逗號分隔） |
| `--save-auto-extracted-glossary` | 儲存自動提取的術語表 |
| `--pool-max-workers N` | **翻譯池最大 worker 數**（未設則用 qps；= pdf2zh.com GUI 的「number of threads」） |
| `--term-qps N` | 術語提取 QPS |
| `--term-pool-max-workers N` | 術語提取 worker 數 |
| `--no-auto-extract-glossary` | 關閉自動術語提取（Paper_Kit 已用） |
| `--primary-font-family F` | 翻譯字型家族覆寫（serif/sans-serif/script） |

## 3. PDF（PDF 處理）

| 旗標 | 說明 |
|---|---|
| `--pages PAGES` | 頁面範圍（`'1,2,1-,-3,3-5'`——注意**負數＝倒數頁**語法） |
| `--no-dual` / `--no-mono` | 不輸出雙語／單語 PDF |
| `--formular-font-pattern` / `--formular-char-pattern` | 公式識別的字型／字元模式 |
| `--split-short-lines` / `--short-line-split-factor` | 短行拆分 |
| `--skip-clean` | 跳過 PDF 清理步驟 |
| `--dual-translate-first` | 雙語 PDF 譯文在前 |
| `--disable-rich-text-translate` | 關閉富文字翻譯 |
| `--enhance-compatibility` | 開啟全部相容性強化 |
| `--use-alternating-pages-dual` | 雙語 PDF 交替頁模式 |
| `--watermark-output-mode MODE` | 浮水印模式（watermarked/no_watermark/both） |
| `--max-pages-per-part N` | 分段翻譯每段最大頁數 |
| `--translate-table-text` | 表格文字翻譯（實驗） |
| `--skip-scanned-detection` | 跳過掃描件偵測 |
| `--ocr-workaround` | 強制譯文黑色＋白色背景（掃描件相容） |
| `--auto-enable-ocr-workaround` | 偵測重度掃描件自動啟用 OCR 替代處理 |
| `--only-include-translated-page` | 只輸出有翻譯的頁（Paper_Kit 已用） |
| `--no-merge-alternating-line-numbers` | 行號文件處理選項 |
| `--no-remove-non-formula-lines` | 公式區域處理選項 |
| `--non-formula-line-iou-threshold` | 非公式行 IoU 閾值 |
| `--figure-table-protection-threshold` | 圖表保護閾值 |
| `--skip-formula-offset-calculation` | 跳過公式偏移計算 |

## 4. GUI（WebUI）

| 旗標 | 說明 |
|---|---|
| `--share` | Gradio share 分享模式 |
| `--auth-file FILE` | 認證檔 |
| `--welcome-page HTML` | 歡迎頁 |
| `--enabled-services LIST` | 啟用服務清單 |
| `--disable-gui-sensitive-input` | 停用敏感輸入 |
| `--disable-config-auto-save` | 停用設定自動儲存 |
| `--server-port N` | WebUI 埠口 |
| `--ui-lang CODE` | UI 語言 |

## 5. 翻譯服務（每服務：model / base-url / api-key / timeout / temperature / json-mode 家族）

**供應商列表（22 個）**：`--siliconflowfree`（預設！未選引擎時自動用 SiliconFlow Free）、`--openai`、`--aliyundashscope`、`--google`、`--bing`、`--deepl`、`--deepseek`、`--ollama`、`--xinference`、`--azureopenai`、`--modelscope`、`--zhipu`、`--siliconflow`、`--tencentmechinetranslation`、`--gemini`、`--azure`、`--anythingllm`、`--dify`、`--grok`、`--groq`、`--qwenmt`、`--openaicompatible`、`--claudecode`、`--clitranslator`。

### SiliconFlow（Paper_Kit 主力）
| 旗標 | 說明 |
|---|---|
| `--siliconflow-base-url` | Base URL（Paper_Kit 用 `https://api.siliconflow.com/v1`） |
| `--siliconflow-model` | 模型（Paper_Kit 用 `google/gemma-4-31B-it`） |
| `--siliconflow-api-key` | API key |
| `--siliconflow-enable-thinking` | 開啟思考 |
| `--siliconflow-send-enable-thinking-param` | 送出 thinking 參數 |
| `--siliconflow-enable-json-mode` | JSON 模式 |

### SiliconFlow Free（免費額度服務）
- `--siliconflow-free-enable-json-mode`（唯一旗標——免費版設定極簡）

### DeepSeek
| 旗標 | 說明 |
|---|---|
| `--deepseek-model` | 模型 |
| `--deepseek-api-key` | API key |
| `--deepseek-enable-json-mode` | JSON 模式 |
| `--deepseek-thinking-mode` | **v4 思考模式（enabled/disabled）** |
| `--deepseek-reasoning-effort` | 推理努力（high/max） |

### 其他服務共通形狀（不逐一列）
`--<svc>-model / --<svc>-base-url / --<svc>-api-key / --<svc>-timeout / --<svc>-temperature / --<svc>-enable-json-mode`（依服務略有增減）。少數例外：DeepL 只有 `--deepl-auth-key`；Google/Bing 無 key。

## 6. Term 術語提取服務（22 組，`--term-<svc>-*` 家族）

每個翻譯服務都有對應的術語提取設定（獨立模型/key/QPS），例：
- `--term-siliconflow-model / -api-key / -enable-thinking / -send-enable-thinking-param / -enable-json-mode`
- `--term-deepseek-*`、`--term-openai-*`、`--term-gemini-*`、`--term-openai-compatible-*` 等
- Paper_Kit 已用：`--term-siliconflow`（票 05 自動術語提取，Kimi 角色原生版）

## 7. 對 Paper_Kit build_command 的缺口對照

Paper_Kit 目前已送（見 `pdf2zh_next_adapter.py`）：`--siliconflow/-deepseek`、`--*-api-key`、`--*-base-url`、`--*-model`、`--lang-out`、`--pages`、`--glossaries`、`--no-auto-extract-glossary`、`--term-siliconflow`、`--only-include-translated-page`。

**未用但值得納入的旗標**（見 [[Paper_Kit-UI-差距分析]] 批 B）：
- `--lang-in`（來源語言）
- `--ignore-cache`（重翻）
- `--pool-max-workers`（threads）
- `--custom-system-prompt`（自訂提示詞）
- `--no-dual`/`--no-mono`（單語/雙語開關）
- `--translate-table-text`、`--auto-enable-ocr-workaround`（實驗/掃描件）
