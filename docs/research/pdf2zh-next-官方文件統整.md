---
title: pdf2zh-next 官方文件統整
date: 2026-08-12
tags: [paper-kit, pdf2zh-next, research, 官方文件, 知識庫]
---

# pdf2zh-next（PDFMathTranslate-next）官方文件統整

> 目的：作為 Paper_Kit 開發可直接引用的知識庫。所有知識點均來自官方文件一手來源，並標注來源 URL。文件部分內容為 GPT 機器翻譯（官方頁尾自承「本页面的部分内容由 GPT 翻译，可能包含错误」），引用時留意。

## 1. 來源與抓取狀態

| 代號 | URL | 狀態 |
|---|---|---|
| S1 | https://docs.siliconflow.cn/en/usercases/use-siliconcloud-in-pdfmathtranslate-next | 已完整擷取 |
| S2 | https://pdf2zh-next.com/zh/index.html | 已完整擷取 |
| S3 | https://pdf2zh-next.com/zh/getting-started/USAGE_webui.html | 已完整擷取（頁面本身內容精簡） |
| S4 | https://pdf2zh-next.com/advanced/TranslationServices/SiliconFlow.html | 已擷取（S1 內文直接連結之官方進階頁） |
| S5 | https://pdf2zh-next.com/zh/getting-started/USAGE_commandline.html | 已擷取（S2/S3 內文直接連結之 CLI 頁） |
| S6 | https://pdf2zh-next.com/advanced/advanced.html | 已擷取（S5 內文指向的參數權威頁） |

- 未擷取（不在本次任務範圍，僅記錄）：`advanced/Documentation-of-Translation-Services.html`（翻譯服務完整清單）、`advanced/API/python.html`（Python API）、`FAQ.html`、`getting-started/INSTALLATION_{winexe,docker,uv}.html`、`advanced/Language-Codes.html`、`supported_languages.html`（S2 均連結之，見 S2）。
- 抓取失敗：無。三個指定來源全部成功。

## 2. 專案定位與版本脈絡（S2）

- 專案名 **PDFMathTranslate-next**，PyPI 套件名 **`pdf2zh-next`**；首頁標題「PDF 科学论文翻译与双语对照」。
- 官方自我定位：「PDF 科学论文翻译与双语对照。基于 BabelDOC。此外，本项目也是调用 BabelDOC 执行 PDF 翻译的官方参考实现。」（S2）
- 是 1.x 版 [Byaidu/PDFMathTranslate](https://github.com/Byaidu/PDFMathTranslate) 的後繼版本；**2.x 起改用 [BabelDOC](https://github.com/funstory-ai/BabelDOC) 作為後端**。（S2）
- 頁面語言版本：English、简体中文、繁體中文、日本語、한국어、Français、Deutsch、Español、Русский、Italiano、Português（共 11 版）。（S2）
- 線上試用：Immersive Translate - BabelDOC（https://app.immersivetranslate.com/babel-doc/），提供免費使用額度。（S2）
- 維護狀態：基於 AGPL v3「按原樣」提供，不作任何保證；「由于维护者精力有限，我们不提供任何形式的使用协助或问题解答。相关问题将被直接关闭！」（歡迎 PR 改進文件；遵循問題模板的 Bug 報告不受影響）。（S2）

## 3. 功能特色清單（S2，共 3 條，已確認無更多）

- 📊 保留公式、圖表、目錄和註釋（preserve formulas, figures, table of contents and annotations）
- 🌐 支援多種語言，以及多樣化的翻譯服務
- 🤖 提供命令列工具（CLI）、互動式使用者介面（WebUI）和 Docker
- 技術棧（致謝區，S2）：PDF 庫 PyMuPDF、PDF 解析 Pdfminer.six、PDF 預覽 Gradio PDF、版面解析 DocLayout-YOLO、多語言字型 BabelDOC-Assets、Asynchronize、Rich logging with multiprocessing、文件國際化 Weblate。

## 4. 支援的翻譯服務（S2 + S6）

- 首頁側邊欄「Translation Services」明確列出：**阿里云（Aliyun）**、**硅基流动（SiliconFlow）**。（S2）
- 完整清單位於「翻譯服務文件」頁 `advanced/Documentation-of-Translation-Services.html`（未擷取，見 §1）。（S2）
- 致謝區：SiliconFlow「為本專案提供基於大語言模型（LLM）的免費翻譯服務」。（S2）
- 進階頁參數機制：服務是以**動態參數名**選用，`--<Services>` 形式（如 `--openai`、`--deepseek`），故 `--service` 不是固定參數名。（S6）

## 5. 支援格式（S2）

- 首頁僅明確提及 **PDF**（科學論文）；未列出其他檔案格式。Paper_Kit 若需要其他格式資訊須另查文件頁。

## 6. 安裝方式（S2，官方推薦分類；實際指令在各自安裝頁，未擷取）

- **Windows EXE**（Windows 推薦）：`getting-started/INSTALLATION_winexe.html`
- **Docker**（Linux 推薦）：`getting-started/INSTALLATION_docker.html`
- **uv**（Python 套件管理器；macOS 推薦）：`getting-started/INSTALLATION_uv.html`
- Docker image：`awwaawwa/pdfmathtranslate-next`（hub.docker.com）。（S2）

## 7. 社群與授權（S2）

- GitHub 倉庫：https://github.com/PDFMathTranslate-next/PDFMathTranslate-next
- Telegram：https://t.me/+Z9_SgnxmsmA5NzBl（未見 Discord）
- 授權：**AGPL v3**（GitHub license badge + 頁面警告雙重載明）
- Weblate 文件翻譯：https://hosted.weblate.org/projects/pdfmathtranslate-next/
- DeepWiki：https://deepwiki.com/PDFMathTranslate-next/PDFMathTranslate-next
- 貢獻者：`awwaawwa`、`pppppop`、`shi`（頁尾）
- 頁尾註明：「本頁面的部分內容由 GPT 翻譯，可能包含錯誤」。

## 8. SiliconCloud（SiliconFlow）整合（S1 + S4）

### 8.1 免費服務 SiliconFlowFree

- CLI 指令：`pdf2zh_next --siliconflowfree example.pdf`（S1/S4）
- WebUI：Translation Options → Service 下拉選單選「SiliconFlowFree」→ 按 Translate → 在「Translated」區塊下載 PDF（S1/S4）
- 免費服務目前使用模型 **`THUDM/GLM-4-9B-0414`**（S4）
- 免費服務隱私模式：檔案內容先送到專案維護者 [@awwaawwa](https://github.com/awwaawwa) 的伺服器，再轉發給 SiliconFlow 翻譯；維護者只收集 SiliconFlow 回傳的錯誤資訊用於除錯，**不會收集你的檔案內容**。隱私政策：https://docs.siliconflow.cn/en/legals/privacy-policy（S1/S4）

### 8.2 使用 SiliconFlow 付費模型（S1/S4）

前置：註冊 https://siliconflow.cn 並建立 API key（https://cloud.siliconflow.cn/me/account/ak，點擊 key 複製）。

- CLI：
  - `pdf2zh_next --siliconflow --siliconflow-model "Pro/deepseek-ai/DeepSeek-V3" --siliconflow-api-key <your-api-key> example.pdf`
- WebUI 欄位（四個，S1/S4 逐欄原文）：
  - Service 下拉選單：選「SiliconFlow」
  - **Base URL for SiliconFlow API**：保留預設值（Keep default）
  - **SiliconFlow model to use**：輸入 `Pro/deepseek-ai/DeepSeek-V3` 或其他模型
  - **API key for SiliconFlow service**：貼上你的 API key
- Zotero：依 [zotero-pdf2zh](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/README_babeldoc.md) 說明將服務設為 SiliconFlow / SiliconFlowFree（S1）

### 8.3 模型名稱（官方文件記載，僅兩個；未列完整清單）

- `THUDM/GLM-4-9B-0414` — 免費服務用（S4）
- `Pro/deepseek-ai/DeepSeek-V3` — 付費範例模型；其餘以「or other models」帶過（S1/S4）

### 8.4 API base URL（明確記錄缺口）

- **官方兩頁（S1/S4）均未寫出 SiliconFlow API base URL 的實際網址**，只說「保留預設值」。未擷取到的翻譯服務文件頁可能有值；不要猜測。

### 8.5 環境變數

- **官方文件未提及任何 SiliconFlow 相關環境變數**（SILICONFLOW_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL 等均未出現在 S1/S4）。僅 CLI 參數 `--siliconflowfree`、`--siliconflow`、`--siliconflow-model`、`--siliconflow-api-key`。

### 8.6 其他

- 官方指此工具是 **BabelDOC 官方推薦的本地自行部署方式**，翻譯功能基於 funstory.ai 開源的 [BabelDOC](https://github.com/funstory-ai/BabelDOC)（S1）
- 最新用法教學：`/advanced/TranslationServices/SiliconFlow.html`；進階選項：`/advanced/advanced.html`（S1）
- 無價格/額度/速率限制資訊於 S1/S4。

## 9. WebUI 使用（S3 + S1/S4 補充）

### 9.1 啟動（S3，原文步驟）

1. 已安裝 Python（**3.10 <= 版本 <= 3.12**）
2. 安裝套件
3. 執行：`pdf2zh_next --gui`
4. 若瀏覽器未自動開啟，造訪 `http://localhost:7860/`
5. 將 PDF 拖入視窗並點擊 `Translate`
6. Docker 部署且以 ollama 為後端 LLM 時，在「Ollama host」填入 `http://host.docker.internal:11434`
- 注意：官方文件此頁**只記載 `pdf2zh_next --gui` 一個啟動指令**；無 `pdf2zh -w` 或 `python -m` 形式。

### 9.2 環境變數（S3）

| 變數 | 用途 | 預設值 |
|---|---|---|
| `PDF2ZH_LANG_FROM` | 設定源語言 | `"English"` |
| `PDF2ZH_LANG_TO` | 設定目標語言 | `"Simplified Chinese"` |

### 9.3 介面功能（S3 頁面本身極簡；合併 S1/S4 可知欄位）

- 上傳：拖入 PDF 視窗（S3）
- 翻譯按鈕：`Translate`；輸出在「Translated」區塊下載（S3/S1）
- 已知選項欄位（由 S1/S4 交叉補足）：Service 下拉選單、Base URL for SiliconFlow API、SiliconFlow model to use、API key for SiliconFlow service、Ollama host
- **明確缺口（S3）**：官方 WebUI 文件頁未列出 translate mode、target language、experimental options（實驗選項）等介面欄位清單；未提供 API endpoint / API key 設定 / curl 範例；未提供 CLI 與 WebUI 參數對照表。這些細節分散於 advanced 頁（S6，見 §11）與翻譯服務頁（S4）。
- 補充（S6）：WebUI 每次按翻譯按鈕會自動把目前設定存到 `~/.config/pdf2zh/config.v3.toml`，下次啟動預設載入；WebUI 使用者可直接上傳 CSV 術語表。

## 10. CLI 使用（S5）

- 基礎指令（S5 全文僅此）：
  - `pdf2zh_next document.pdf`
  - `pdf2zh_next "path with spaces/document.pdf"`（路徑含空格需加引號）
- 輸出：翻譯後檔案在**目前工作目錄**中生成（S5）
- 其他參數細節全部指向 advanced 頁（S6）；S5 未提及 `--threads`、`--ignore-cache`、`--prompt`、`--pages`、`--service`、`--lang` 等名稱，未提及環境變數與 config.json。

## 11. 進階選項參數全表（S6，`advanced/advanced.html`）

> S6 表格僅「Option / Function / Example」三欄，無型別欄；僅 `--auto-enable-ocr-workaround` 標註 `(default: False)`。**官方無 `--threads` 參數**；並行度由 `--qps` / `--pool-max-workers` 控制。

### 11.1 Args（一般參數）

| 參數 | 功能 |
|---|---|
| `input-files` | 要處理的輸入 PDF 檔 |
| `--output` | 輸出目錄 |
| `--<Services>` | 使用特定翻譯服務（如 `--openai`、`--deepseek`） |
| `--help`, `-h` | 顯示說明並離開 |
| `--config-file` | 設定檔路徑 |
| `--report-interval` | 進度回報間隔（秒） |
| `--debug` | 使用 debug 日誌等級 |
| `--gui` | 以 GUI 模式互動 |
| `--warmup` | 只下載並驗證所需資源後離開 |
| `--generate-offline-assets` | 在指定目錄產生離線資源包 |
| `--restore-offline-assets` | 從指定目錄還原離線資源包 |
| `--version` | 顯示版本後離開 |
| `--pages` | 部分文件翻譯，支援 `1,2,1-,-3,3-5`（頁碼語法） |
| `--lang-in` | 來源語言代碼 |
| `--lang-out` | 目標語言代碼 |
| `--min-text-length` | 可翻譯的最小文字長度 |
| `--rpc-doclayout` | 文件版面分析 RPC 服務位址 |
| `--qps` | 翻譯服務 QPS 上限 |
| `--ignore-cache` | 忽略翻譯快取 |
| `--custom-system-prompt` | 自訂翻譯 system prompt（文件註明用於 Qwen 3 的 `/no_think`） |
| `--glossaries` | 術語表檔案清單（逗號分隔） |
| `--save-auto-extracted-glossary` | 儲存自動抽取的術語表 |
| `--pool-max-workers` | 翻譯執行池最大 workers；未設定時以 qps 為準 |
| `--term-qps` | 術語抽取翻譯服務 QPS；未設定時跟隨 qps |
| `--term-pool-max-workers` | 術語抽取執行池最大 workers；未設定或 0 時跟隨 pool_max_workers |
| `--no-auto-extract-glossary` | 停用自動抽取術語表 |
| `--primary-font-family` | 覆寫翻譯文字主要字型（serif / sans-serif / script） |
| `--no-dual` | 不輸出雙語 PDF |
| `--no-mono` | 不輸出單語 PDF |
| `--formular-font-pattern` | 辨識公式文字的字型 pattern |
| `--formular-char-pattern` | 辨識公式文字的字元 pattern |
| `--split-short-lines` | 強制將短行拆成不同段落 |
| `--short-line-split-factor` | 短行分割門檻係數 |
| `--skip-clean` | 跳過 PDF 清理步驟 |
| `--dual-translate-first` | 雙語 PDF 中翻譯頁在前 |
| `--disable-rich-text-translate` | 停用 rich text 翻譯 |
| `--enhance-compatibility` | 啟用所有相容性增強選項 |
| `--use-alternating-pages-dual` | 雙語 PDF 使用交替頁模式 |
| `--watermark-output-mode` | PDF 浮水印輸出模式 |
| `--max-pages-per-part` | 分割翻譯時每部分最大頁數 |
| `--translate-table-text` | 翻譯表格文字（**實驗性**） |
| `--skip-scanned-detection` | 跳過掃描偵測 |
| `--ocr-workaround` | 強制翻譯文字為黑色並加白底 |
| `--auto-enable-ocr-workaround` | 自動啟用 OCR workaround（**default: False**） |
| `--only-include-translated-page` | 只包含翻譯頁（僅搭配 `--pages` 有效） |
| `--no-merge-alternating-line-numbers` | 停用有行號文件中交替行號與段落的合併 |
| `--no-remove-non-formula-lines` | 停用移除段落區域內非公式行 |
| `--non-formula-line-iou-threshold` | 辨識非公式行的 IoU 門檻（0.0–1.0） |
| `--figure-table-protection-threshold` | 圖表保護門檻（0.0–1.0）；圖表內行不處理 |
| `--skip-formula-offset-calculation` | 跳過公式偏移計算 |

### 11.2 GUI Args（S6）

| 參數 | 功能 |
|---|---|
| `--share` | 啟用分享模式 |
| `--auth-file` | 認證檔路徑 |
| `--welcome-page` | 自訂歡迎頁 HTML 路徑 |
| `--enabled-services` | 啟用的翻譯服務（如 `"Bing,OpenAI"`） |
| `--disable-gui-sensitive-input` | 停用 GUI 敏感輸入 |
| `--disable-config-auto-save` | 停用自動儲存設定 |
| `--server-port` | WebUI 連接埠 |
| `--ui-lang` | UI 語言 |

### 11.3 S6 其他內容區塊

- Rate Limiting 設定指南（見 §13）
- 部分翻譯：`--pages` 語法（`1,2,1-,-3,3-5`）
- 指定語言：`--lang-in` / `--lang-out`
- 翻譯例外、自訂 prompt（`--custom-system-prompt`）、自訂設定（config.toml）、Skip clean（`--skip-clean`）、翻譯快取（`--ignore-cache`）、公開部署（GUI args）、認證與歡迎頁、術語表（`--glossaries` + CSV 上傳）

## 12. 環境變數規則與設定檔（S6 + S3）

- 轉換規則（S6）：參數的 `--` 換成 `PDF2ZH_`、以 `=` 連接值、`-` 換成 `_`。
  - 範例：`PDF2ZH_GUI=TRUE pdf2zh_next`
  - 範例：`PDF2ZH_SKIP_CLEAN=TRUE pdf2zh_next example.pdf`
- 設定檔：**TOML**（`config.toml`），預設位置 `~/.config/pdf2zh`（`default` 目錄內為程式自動產生，請勿直接修改）；GUI 自動儲存為 `~/.config/pdf2zh/config.v3.toml`（S6）
- 優先順序：**cli/gui > env > user config file > default config file**（S6）
- 範例結構（S6）：
  ```toml
  [basic]
  gui = true

  [gui_settings]
  enabled_services = "Bing,OpenAI"
  disable_gui_sensitive_input = true
  disable_config_auto_save = true
  ```
- 認證與歡迎頁範例（S6）：
  ```toml
  [basic]
  gui = true

  [gui_settings]
  auth_file = "/path/to/auth/file"
  welcome_page = "/path/to/welcome/html/file"
  ```
- `auth.txt` 格式：每行 `username,password`；歡迎頁為自訂 HTML；**認證檔為空時不啟用認證**，歡迎頁只有認證檔非空時才生效（S6）
- 公開部署建議同時啟用 `disable_gui_sensitive_input` 與 `disable_config_auto_save`（S6）

## 13. Rate Limiting 指南（S6）

- RPM 限制時：`qps = floor(rpm / 60)`，`pool_size = qps * 10`；範例：600 RPM → `--qps 10 --pool-max-worker 100`（S6 原文即 `--pool-max-worker`，單數；§11 表為複數 `--pool-max-workers`——官方文件自身不一致，引用時留意）
- 並發連線限制時：`pool_size = max(floor(0.9 * limit), limit - 20)`，`qps = pool_size`；範例：50 連線 → `--qps 45 --pool-max-worker 45`
- 建議 pool 不超過 1000

## 14. 與 Paper_Kit 的關聯

Paper_Kit 現況（2026-08-12 掃描 `C:\Users\qaref\Code\Paper_Kit`）：骨架期——`src/paper_kit/{domain,application,infrastructure,presentation}` 皆為空 `__init__.py`，`tests/` 空，README 記載 Phase 1（票 01–11）尚未開始、POC 已完成（gemma / DeepSeek 翻譯品質、術語表、公式保真）；README 鎖定引擎 pdf2zh-next（BabelDOC 管線）、UI NiceGUI、務實 DDD + Ports & Adapters、TDD。官方文件已記載但 Paper_Kit 尚未實作（對照 docs/tickets/ 01–15）的功能：

- **自訂 system prompt**：`--custom-system-prompt`（官方文件僅提用於 Qwen 3 `/no_think`）→ Paper_Kit 規格書/tickets 未見此項目
- **翻譯快取控制**：`--ignore-cache`（忽略翻譯快取；官方另有「翻譯快取」章節）→ 對應票 08（任務歷史/重試）有部分重疊，但無快取語意
- **並行度控制**：官方無 `--threads`；改用 `--qps`、`--pool-max-workers`、`--term-qps`、`--term-pool-max-workers` → Paper_Kit 票 06（成本估算）未含並行調參
- **術語表進階能力**：自動抽取（`--save-auto-extracted-glossary` / `--no-auto-extract-glossary`）、`--term-qps` 分離速率 → 票 05 有匯入/管理，無自動抽取
- **頁面範圍進階**：`--pages` 語法（`1,2,1-,-3,3-5`）、`--only-include-translated-page` → 票 07 有頁面範圍，可對齊官方語法
- **OCR 路徑**：`--ocr-workaround` / `--auto-enable-ocr-workaround` / `--skip-scanned-detection` → 票 12 掃描件 OCR 可引用
- **雙語輸出選項**：`--no-dual` / `--no-mono` / `--dual-translate-first` / `--use-alternating-pages-dual` / `--watermark-output-mode`
- **多服務可插拔**：`--<Services>` 動態參數 + GUI `--enabled-services` + config.toml → Paper_Kit Ports & Adapters 設計的官方對照
- **公開部署**：`--share` / `--auth-file` / `--welcome-page` / `--server-port` / `--ui-lang` / `--disable-gui-sensitive-input`（配合敏感文件紅線票 10）
- **免費服務**：`--siliconflowfree`（維護者代理，隱私模式）→ 票 13 BabelDOC 線上 adapter 可參考
- **設定檔系統**：TOML `~/.config/pdf2zh/config.toml`、環境變數 `PDF2ZH_*` 自動映射規則、優先順序 cli/gui > env > user > default → Paper_Kit 現無設定檔規格
- **其他**：`--custom-welcome-page` 以外的資源離線包（`--generate-offline-assets` / `--restore-offline-assets`）、`--rpc-doclayout`（外部版面分析 RPC）、`--primary-font-family`、`--enhance-compatibility`
- **文件缺口提醒**：官方 WebUI 頁未記載實驗選項清單與 API 用法；Paper_Kit 設計 WebUI 時不能只依賴官方文件頁，需以 S6 參數表為準。
