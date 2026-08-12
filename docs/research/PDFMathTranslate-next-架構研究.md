---
title: PDFMathTranslate-next 架構研究
date: 2026-08-12
tags: [research, pdf2zh, pdf-translation, babeldoc, architecture, paper-kit]
source: 一手來源（GitHub repo 主頁、官方文件站 pdf2zh-next.com、GitHub 源碼 API）
---

# PDFMathTranslate-next 架構研究

> 本文件為 Paper_Kit 開發者知識庫用途。所有知識點均標註來源 URL；抓不到或無法確認的內容明確標示「無法取得」，不以既有知識補寫。

---

## 0. 摘要（30 秒結論）

- **PDFMathTranslate-next**（PyPI 套件名 **`pdf2zh-next`**，2026-08-12 抓取時版本 **2.8.2**）是原版 `Byaidu/PDFMathTranslate`（pdf2zh 1.x）的**下一代後繼專案**，作者自承（README acknowledgements：「1.x version: Byaidu/PDFMathTranslate」）。
- 它不再自行實作 PDF 管線，而是**基於 BabelDOC 後端**（依賴 `babeldoc>=0.5.20,<0.6.0`），定位是「呼叫 BabelDOC 執行 PDF 翻譯的官方參考實作」。
- 授權 **AGPL-3.0**；README 明言「as is、無任何品質保證、維護者不提供使用協助、無關 issue 直接關閉」。
- 交付形式：CLI（`pdf2zh` / `pdf2zh2` / `pdf2zh_next` 三個指令）、WebUI（Gradio，`--gui`，`http://localhost:7860/`）、Docker、Windows EXE、第三方 Zotero 外掛（`guaguastandup/zotero-pdf2zh`）。
- 翻譯引擎採「metadata 驅動」架構：`translate_engine_model.py` 定義 **25 個引擎**（含棄用的 Bing/Google），LLM 引擎支援**術語抽取**（glossary）。
- **原版 1.x 的 `--threads`、`--jora`、`--scihub` 等旗標在 next 中不存在**——並行改為 **QPS / pool 速率模型**。不要照 1.x 文件對 next 下指令。
- 翻譯快取為 **SQLite**（peewee），位於 `~/.cache/pdf2zh_next/cache.v1.db`，key = `(engine, engine_params JSON, 原文)`；`--ignore-cache` 強制重譯。

---

## 1. 資料來源與抓取方法

| 來源 | URL | 抓取方式 |
|---|---|---|
| 專案主頁（含 README 渲染） | https://github.com/PDFMathTranslate/PDFMathTranslate-next | WebFetch |
| README raw（github 渲染頁） | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/README.md | WebFetch |
| 安裝（uv） | https://pdf2zh-next.com/getting-started/INSTALLATION_uv.html | WebFetch |
| 安裝（Docker） | https://pdf2zh-next.com/getting-started/INSTALLATION_docker.html | WebFetch |
| 安裝（Windows EXE） | https://pdf2zh-next.com/getting-started/INSTALLATION_winexe.html | WebFetch |
| CLI 使用 | https://pdf2zh-next.com/getting-started/USAGE_commandline.html | WebFetch |
| WebUI 使用 | https://pdf2zh-next.com/getting-started/USAGE_webui.html | WebFetch |
| 進階使用（全部旗標） | https://pdf2zh-next.com/advanced/advanced.html | WebFetch |
| 翻譯服務文件索引 | https://pdf2zh-next.com/advanced/Documentation-of-Translation-Services.html | WebFetch |
| 語言代碼 | https://pdf2zh-next.com/advanced/Language-Codes.html | WebFetch |
| 支援語言（轉址 BabelDOC） | https://funstory-ai.github.io/BabelDOC/supported_languages/ | WebFetch |
| Python API | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/API/python.md | WebFetch |
| SiliconFlow 服務文件 | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/TranslationServices/SiliconFlow.md | WebFetch |
| Aliyun 服務文件 | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/TranslationServices/Aliyun.md | WebFetch |
| 後端 BabelDOC README | https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md | WebFetch |
| 源碼 `pyproject.toml` | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pyproject.toml | WebFetch |
| 源碼 `pdf2zh_next/high_level.py` | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/high_level.py | WebFetch |
| 源碼 `pdf2zh_next/config/cli_env_model.py` | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/cli_env_model.py | WebFetch |
| 源碼 `pdf2zh_next/config/translate_engine_model.py` | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/translate_engine_model.py | WebFetch |
| 源碼 `pdf2zh_next/translator/cache.py` | https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/translator/cache.py | WebFetch |
| GitHub API（目錄樹） | https://api.github.com/repos/PDFMathTranslate/PDFMathTranslate-next/contents/... | WebFetch |

---

## 2. 專案定位

- 一句話定位（README 原文）：「PDF scientific paper translation and bilingual comparison.」＝ PDF 科學論文翻譯與雙語對照。
- 副標（README）：「基于 AI 完整保留排版的 PDF 文档全文双语翻译，支持 Google/DeepL/Ollama/OpenAI 等服务，提供 CLI/GUI/Docker」。
- 功能宣稱（README）：
  - 保留公式、圖表、目錄、註解（「Preserve formulas, charts, table of contents, and annotations」）
  - 支援多語言與多種翻譯服務
  - CLI、互動 UI、Docker 三種形式
- 與原版 pdf2zh 1.x 的關係：next 版本 = 後繼專案（PyPI 套件 `pdf2zh-next`），README acknowledgements 列「1.x version: Byaidu/PDFMathTranslate」；Windows EXE 安裝文件亦稱其為「community 'next' fork」。
- 與 BabelDOC 的關係：基於 BabelDOC；「此專案同時也是呼叫 BabelDOC 執行 PDF 翻譯的官方參考實作」。BabelDOC README 亦明言「所有 BabelDOC API 應視為內部 API，不支援直接使用」——Python 端建議一律走 pdf2zh_next 的 `high_level`。
- 商業線上版：Immersive Translate 的 BabelDOC 線上服務（https://app.immersivetranslate.com/babel-doc/），提供免費額度。
- 授權與支援態度（README 原文引用）：
  - 「This project is provided 'as is' under the AGPL v3 license, and no guarantees are provided for the quality and performance of the program.」
  - 「Due to the maintainers' limited energy, we do not provide any form of usage assistance or problem-solving. Related issues will be closed directly!」（歡迎改進文件的 PR 與依 template 提交的 bug report）
- 社群：Telegram 群組（badge 連結 https://t.me/+Z9_SgnxmsmA5NzBl）、Weblate 文件翻譯（https://hosted.weblate.org/projects/pdfmathtranslate-next/）。

**來源**：[GitHub 主頁](https://github.com/PDFMathTranslate/PDFMathTranslate-next)、[raw README](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/README.md)、[INSTALLATION_winexe.html](https://pdf2zh-next.com/getting-started/INSTALLATION_winexe.html)、[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)

---

## 3. 版本與開發狀態

- 抓取時間：2026-08-12。
- GitHub 統計（主頁可見）：約 560 stars、44 forks、1,784 commits（main）；badge：PyPI 版本／下載量、Docker pulls、Telegram、License、Weblate、Ask DeepWiki、Trendshift。
- PyPI 專案名：`pdf2zh-next`；`pyproject.toml` 版本 **2.8.2**。
- Docker 映像（兩個 registry）：
  - Docker Hub：`awwaawwa/pdfmathtranslate-next`
  - GitHub Container Registry：`ghcr.io/pdfmathtranslate-next/pdfmathtranslate-next`
- 授權：AGPL-3.0（LICENSE 檔案 + pyproject `license = "AGPL-3.0"`）。
- 版本格式（BabelDOC 側，供參考）：`0.MAJOR.MINOR`；MAJOR 為 API 不相容或重大變更。
- 主頁顯示「forked from PDFMathTranslate-next/PDFMathTranslate-next」——repo 曾搬移／fork 網路關係；以現行網址 `PDFMathTranslate/PDFMathTranslate-next` 為準。

**來源**：[GitHub 主頁](https://github.com/PDFMathTranslate/PDFMathTranslate-next)、[pyproject.toml](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pyproject.toml)、[INSTALLATION_docker.html](https://pdf2zh-next.com/getting-started/INSTALLATION_docker.html)、[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)

---

## 4. 架構總覽

### 4.1 套件結構（源碼目錄 `pdf2zh_next/`，GitHub API 目錄樹）

| 元件 | 職責 |
|---|---|
| `main.py` | CLI 進入點（entry point `pdf2zh_next.main:cli`） |
| `high_level.py` | 高階 Python API（`do_translate_async_stream` 等；見 §15） |
| `gui.py` | Gradio WebUI |
| `http_api.py` | HTTP API |
| `i18n.py` | 多語系（Weblate 支援） |
| `config/model.py` | `SettingsModel`（pydantic，所有設定的單一權威來源；含 env var alias） |
| `config/cli_env_model.py` | 動態建立 `CLIEnvSettingsModel`＝CLI 旗標＋環境變數合併模型 |
| `config/translate_engine_model.py` | `TRANSLATION_ENGINE_METADATA`／`TERM_EXTRACTION_ENGINE_METADATA`（引擎清單權威來源） |
| `translator/base_translator.py` | 翻譯器抽象基底 |
| `translator/cache.py` | SQLite 翻譯快取（peewee） |
| `translator/rate_limiter/` | QPS 限制器 |
| `translator/translator_impl/` | 16 個引擎實作檔（見 §11） |
| `assets/`、`utils/` | 資源與工具 |

（`config/` 另有 `translate_engine_model.py` 之上游資料；根目錄另有 `Dockerfile`、`app.json`、`mkdocs.yml`、`script/`、`test(s)/`。）

**來源**：[GitHub API 目錄樹](https://api.github.com/repos/PDFMathTranslate/PDFMathTranslate-next/contents/pdf2zh_next)

### 4.2 翻譯管線（BabelDOC 兩階段模型）

BabelDOC README 將問題拆成兩大階段：

1. **Parsing**：「to get the structure of the pdf such as text blocks, images, tables, etc.」（取得 PDF 結構：文字區塊、圖片、表格…）
2. **Rendering**：「to render the structure into a new pdf or other format.」（把結構渲染成新 PDF 或其他格式）

關鍵設計：兩階段之間有 **intermediate representation（中間表示）**，保留原始文件結構——這是與 mathpix 等單欄 reader-order 渲染器的本質差異。**管線是 plugin-based 系統**（原文：「The pipeline is also a plugin-based system which everybody can add their new model, ocr, renderer, etc.」）。

事件流中可見的階段名（`do_translate_async_stream` 的 `stage_summary` 範例，來自官方 API 文件）：

- `Parse PDF and Create Intermediate Representation`（佔比約 10.9%）
- `DetectScannedFile`（掃描檔偵測，約 1.9%）
- `Parse Page Layout`（頁面版面分析，約 10.8%）
- `Translate Paragraphs`（段落翻譯）
- 之後：輸出 mono／dual PDF（`finish` 事件回傳）

組成元件（BabelDOC README acknowledgements ＋ README）：

- **DocLayout-YOLO**：版面分析（文件版面辨識模型）
- **pdfminer / PyMuPDF**：PDF 解析與渲染
- **BabelDOC-Assets**：多語字型資源
- **RapidOCR**：掃描檔 OCR workaround（`--auto-enable-ocr-workaround` 時啟用 OCR 處理）
- 相關外部方案（承認清單，非依賴）：layoutreader（閱讀順序）、Surya（文件結構）
- 遠端版面分析：`--rpc-doclayout`（RPC 服務位址，做文件版面分析）

**來源**：[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)、[PDFMathTranslate-next README](https://github.com/PDFMathTranslate/PDFMathTranslate-next)、[python.md API 文件](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/API/python.md)

### 4.3 執行模型：subprocess + IPC（`high_level.py`）

- 正常模式：**翻譯在子程序（`multiprocessing.Process`）中執行**，父程序透過 **兩個 duplex pipe**（progress pipe、cancel pipe）與 **一個 logging Queue** 與子程序通訊。
- 進度事件：子→父（progress pipe，dict 事件流）；取消：父→子（cancel pipe → `config.cancel_translation()`）；日誌：子→父（Queue + `QueueHandler` + `log_thread`）。
- 30 分鐘 timeout：`asynchronize.AsyncCallback(timeout=30*60)`。
- 崩潰偵測：子程序 exitcode 非 0/None 且無錯誤回報 → 拋 `SubprocessCrashError`。
- **debug 模式（`settings.basic.debug`）直接在主程序內跑 `babeldoc_translate`**，事件結構相同。
- 錯誤模型：`TranslationError` 階層（`BabeldocError`、`SubprocessError`、`IPCError`、`SubprocessCrashError`），實作 `__reduce__` 以便跨行程 pickling。
- 大型文件會被**自動分片（parts）**，事件帶 `part_index`／`total_parts`；分片大小由 `--max-pages-per-part` 控制。

**來源**：[python.md API 文件](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/API/python.md)、[high_level.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/high_level.py)

### 4.4 翻譯快取（LLM 快取，`translator/cache.py`）

- 儲存：**SQLite**（peewee ORM），WAL journal 模式、1000ms busy timeout。
- 位置：`~/.cache/pdf2zh_next/cache.v1.db`（檔名含版號；源碼註解：「目前版本不支援 DB migration，故在檔名加版號」）。
- key：`(translate_engine, translate_engine_params, original_text)` UNIQUE 約束，`ON CONFLICT REPLACE`——即**命中需引擎名、參數（JSON 遞迴排序序列化）、原文三者完全相同**。引擎名限制 <20 字元。
- 公開類別 `TranslationCache`：`get(original_text) -> str | None`、`set(original_text, translation)`、`replace_params/update_params/add_params`；`set()` 吞例外只留 debug log。
- 清除方式：`init_db(remove_exists=True)` 會刪除 db 檔後重建（無專用 view/clear CLI；可直接查 SQLite 檔）。
- CLI 對應：`--ignore-cache` 強制重譯（見 §9）。
- 另：`config.v3.toml` 的 GUI 自動儲存機制（§10）與翻譯快取是不同東西。

**來源**：[cache.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/translator/cache.py)、[advanced.html](https://pdf2zh-next.com/advanced/advanced.html)

### 4.5 速率限制與並行（取代 1.x 的 `--threads`）

- 參數模型：`--qps`（服務 QPS 上限）＋ `--pool-max-workers`（翻譯 pool 最大 worker 數；未設時 fallback 到 qps 值）。
- 術語抽取獨立參數：`--term-qps`（未設時跟 qps）、`--term-pool-max-workers`（未設時跟 pool_max_workers）。
- 官方建議（advanced.html）：
  - pool 建議上限 **1000**。
  - RPM 限制：`qps = floor(rpm / 60)`、`pool_size = qps * 10`（10 倍稱為「經驗係數」）；例：600 RPM → qps 10、pool 100。
  - 並發連線限制（例 GLM）：`pool_size = max(floor(0.9 * official_concurrent_limit), official_concurrent_limit - 20)`、`qps = pool_size`。
  - 文件範例指令用單數 `--pool-max-worker`，旗標表列複數 `--pool-max-workers`（源碼中欄位名以 metadata 為準）。

**來源**：[advanced.html](https://pdf2zh-next.com/advanced/advanced.html)

---

## 5. CLI 用法

### 5.1 基本

```bash
pdf2zh_next document.pdf
pdf2zh_next "path with spaces/document.pdf"     # 路徑含空白需引號
pdf2zh_next example.pdf --lang-in en --lang-out ja
pdf2zh_next -h    # help 尾段列出各翻譯服務的詳細資訊（服務清單權威來源）
```

- 輸出：產生在**當前工作目錄**（advanced 文件範例顯示實際輸出路徑為 `pdf2zh_files/<session>/...`）。
- 可執行檔名：`pdf2zh`、`pdf2zh2`、`pdf2zh_next` 三個 script 全部指向 `pdf2zh_next.main:cli`。

**來源**：[USAGE_commandline.html](https://pdf2zh-next.com/getting-started/USAGE_commandline.html)、[pyproject.toml](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pyproject.toml)、[python.md](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/API/python.md)

### 5.2 旗標總表（advanced.html 完整轉錄）

**基本參數：**

| 旗標 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `input-files` | positional | — | 輸入 PDF 檔 |
| `--output` | string | — | 輸出目錄 |
| `--<Services>` | string | — | 指定翻譯服務（例如 `--openai`、`--deepseek`） |
| `--help` / `-h` | flag | — | 顯示說明 |
| `--config-file` | string | — | 設定檔路徑（TOML） |
| `--report-interval` | int | — | 進度回報間隔（秒） |
| `--debug` | flag | — | debug 層級日誌 |
| `--gui` | flag | — | 以 GUI（WebUI）互動 |
| `--warmup` | flag | — | 只下載並驗證所需資源後退出 |
| `--generate-offline-assets` | string | — | 在指定目錄產生離線資源包 |
| `--restore-offline-assets` | string | — | 從指定目錄還原離線資源包 |
| `--version` | flag | — | 顯示版本後退出 |

**翻譯參數：**

| 旗標 | 型別 | 預設 | 說明 |
|---|---|---|---|
| `--pages` | string | — | 部分翻譯（`1,2,1-,-3,3-5`；`25-`＝25 到結尾、`-25`＝1–25） |
| `--lang-in` | string | — | 來源語言代碼 |
| `--lang-out` | string | — | 目標語言代碼 |
| `--min-text-length` | int | — | 翻譯的最小文字長度 |
| `--rpc-doclayout` | string | — | 文件版面分析的 RPC 服務位址 |
| `--qps` | int | — | 翻譯服務 QPS 上限 |
| `--ignore-cache` | flag | — | 忽略翻譯快取 |
| `--custom-system-prompt` | string | — | 自訂 system prompt（Qwen 3 用 `/no_think`） |
| `--glossaries` | string | — | 術語表檔清單（CSV，逗號分隔） |
| `--save-auto-extracted-glossary` | flag | — | 儲存自動抽取的術語表 |
| `--pool-max-workers` | int | qps | 翻譯 pool 最大 worker；未設時以 qps 為準 |
| `--term-qps` | int | qps | 術語抽取 QPS；未設時跟 qps |
| `--term-pool-max-workers` | int | pool_max_workers | 術語抽取 pool 最大 worker |
| `--no-auto-extract-glossary` | flag | — | 停用自動術語抽取 |
| `--primary-font-family` | string | auto | 覆寫主要字型族：`serif`／`sans-serif`／`script`；否則依原文自動 |
| `--no-dual` | flag | — | 不輸出雙語 PDF |
| `--no-mono` | flag | — | 不輸出單語 PDF |
| `--formular-font-pattern` | regex | — | 辨識公式文字的字型 pattern |
| `--formular-char-pattern` | regex | — | 辨識公式文字的字元 pattern |
| `--split-short-lines` | flag | — | 強制把短行拆成不同段落 |
| `--short-line-split-factor` | float | — | 短行拆分門檻因子 |
| `--skip-clean` | flag | — | 跳過 PDF 清理步驟（提升相容性） |
| `--dual-translate-first` | flag | — | 雙語 PDF 中譯文頁置前 |
| `--disable-rich-text-translate` | flag | — | 停用 rich text 翻譯 |
| `--enhance-compatibility` | flag | — | 啟用所有相容性增強選項（含 skip-clean） |
| `--use-alternating-pages-dual` | flag | — | 雙語 PDF 用交替頁模式 |
| `--watermark-output-mode` | string | — | PDF 浮水印輸出模式（`no_watermark`／`both`／`watermarked`） |
| `--max-pages-per-part` | int | — | 分片翻譯的每片最大頁數 |
| `--translate-table-text` | flag | — | 翻譯表格文字（實驗性） |
| `--skip-scanned-detection` | flag | — | 跳過掃描檔偵測 |
| `--ocr-workaround` | flag | — | 強制譯文為黑色並加白底 |
| `--auto-enable-ocr-workaround` | flag | False | 自動 OCR workaround：若重度掃描，啟用 OCR 處理並跳過後續掃描偵測 |
| `--only-include-translated-page` | flag | — | 只輸出已翻譯頁（僅搭配 `--pages` 生效） |
| `--no-merge-alternating-line-numbers` | flag | — | 停用交替行號與文字段落的合併 |
| `--no-remove-non-formula-lines` | flag | — | 停用段落區域內非公式行的移除 |
| `--non-formula-line-iou-threshold` | float | — | 非公式行 IoU 門檻（0.0–1.0） |
| `--figure-table-protection-threshold` | float | — | 圖/表保護門檻（0.0–1.0） |
| `--skip-formula-offset-calculation` | flag | — | 處理中跳過公式位移計算 |

**GUI 參數：**

| 旗標 | 說明 |
|---|---|
| `--share` | 啟用分享模式 |
| `--auth-file` | 驗證檔路徑 |
| `--welcome-page` | 自訂歡迎 HTML 頁路徑 |
| `--enabled-services` | 啟用的翻譯服務，例 `"Bing,OpenAI"` |
| `--disable-gui-sensitive-input` | 停用 GUI 敏感輸入 |
| `--disable-config-auto-save` | 停用設定自動儲存 |
| `--server-port` | WebUI 埠 |
| `--ui-lang` | UI 語言 |

### 5.3 進階說明（advanced.html）

- **部分翻譯**：`--pages "1,3,10-20,25-"`（逗號組合範圍、開放範圍）。
- **語言**：`--lang-in`／`--lang-out`，代碼參考 Google 與 DeepL 清單（§12.2）。
- **例外（公式保留）**：regex pattern 保留公式文字，例：
  `--formular-font-pattern "(CM[^RT].*|MS.*|.*Ital)"` 搭配對應的 `--formular-char-pattern`。
  預設保留字型：「`Latex`, `Mono`, `Code`, `Italic`, `Symbol` and `Math`」，
  預設 pattern：`--formular-font-pattern "(CM[^R]|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Ital|.*Sym|.*Math)"`。
- **自訂 prompt**：`--custom-system-prompt "/no_think You are a professional, authentic machine translation engine"`（主要用於 Qwen 3 的 `/no_think`）。
- **公開部署**：建議 `gui = true`、`enabled_services = "Bing,OpenAI"`、`disable_gui_sensitive_input = true`、`disable_config_auto_save = true`；文件警告專案**未經專業安全稽核**。
- **驗證**：`--auth-file` 內容為 `username,password`（逗號分隔，每行一組）；`--welcome-page` 只在有 auth file 時生效。
- **術語表**：CSV 三欄 `source`,`target`,`tgt_lng`；多檔逗號分隔：`--glossaries "glossary1.csv,glossary2.csv,glossary3.csv"`；WebUI 可上傳並點檔名檢視。
- **skip-clean**：`--skip-clean`（或 `PDF2ZH_SKIP_CLEAN=TRUE`）跳過 PDF 清理以提升相容性；`--enhance-compatibility` 自動含之。

### 5.4 原版 1.x 旗標與 next 的差異（重要）

以下旗標**在 next 的文件與源碼 metadata 中未出現**，應視為原版 pdf2zh 1.x（或更早期 next 版本）的旗標，勿對 next 使用：

- `--threads`（next 改為 `--qps` / `--pool-max-workers` 速率模型）
- `--jora`、`--scihub`、`--llm`、`--model`、`--webui`、`--port`、`--server`、`--timeout`、`--retries`、`--retry-backoff`、`--max-connection`、`--color`、`--exclude`
- `--skip-font-subsetting`（字型 subsetting 選項未見於 next；字型控制僅有 `--primary-font-family`）
- 註：timeout 在 next 中以 per-engine 欄位存在（如 `openai_timeout`、`aliyun_dashscope_timeout`）；重試參數未見。

> 「無法取得」註記：以上旗標僅以「未出現在已抓取之 advanced.html 旗標表與 translate_engine_model.py」為證；並未逐一掃描全部源碼確認其絕不存在，但官方文件表為權威使用者介面。

**來源**：[advanced.html](https://pdf2zh-next.com/advanced/advanced.html)、[translate_engine_model.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/translate_engine_model.py)

---

## 6. 環境變數與設定檔

### 6.1 慣例（advanced.html 明文）

- 設定優先序：「**cli/gui > env > user config file > default config file**」。
- 環境變數規則：旗標名去 `--`、`-` 換 `_`、全部大寫、前綴 `PDF2ZH_`、值用 `=`。例：`PDF2ZH_GUI=TRUE pdf2zh_next`、`PDF2ZH_SKIP_CLEAN=TRUE`。
- 設定檔：預設路徑 `~/.config/pdf2zh`；GUI 每次翻譯後自動儲存 `config.v3.toml`。「v2/v3」是**設定檔版號，不是 pdf2zh 程式版號**。

### 6.2 WebUI 頁明列的環境變數

- `PDF2ZH_LANG_FROM`：設定來源語言，預設 "English"。
- `PDF2ZH_LANG_TO`：設定目標語言，預設 "Simplified Chinese"。

### 6.3 API key 環境變數

> **無法取得（明確記錄）**：官方文件頁（advanced.html、服務文件頁）**沒有列出 `OPENAI_API_KEY` 之類的 API key 環境變數**。源碼層面（`translate_engine_model.py`）API key 是各引擎設定模型的 pydantic 欄位（`openai_api_key`、`deepseek_api_key`、`deepl_auth_key` 等，對應 CLI 旗標 `--openai-api-key` 等）。`cli_env_model.py` 的 env 對應是透過 `SettingsModel` 欄位的 `alias` 轉發（該檔未含字面環境變數字串）——因此是否有 `OPENAI_API_KEY` 同名環境變數直接被讀取，**未能從已抓取的來源確認**。實務上以 CLI 旗標／GUI 欄位傳 key 為文件明載之道。

**來源**：[advanced.html](https://pdf2zh-next.com/advanced/advanced.html)、[USAGE_webui.html](https://pdf2zh-next.com/getting-started/USAGE_webui.html)、[cli_env_model.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/cli_env_model.py)、[translate_engine_model.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/translate_engine_model.py)

---

## 7. 翻譯服務

### 7.1 官方分層（Documentation-of-Translation-Services.html）

- 服務清單權威來源：`pdf2zh_next -h`（「在 help 訊息尾段可查看各翻譯服務的詳細資訊」）。
- **Tier 1（官方直維）**：SiliconFlowFree、OpenAI、AliyunDashScope、DeepSeek、SiliconFlow、Zhipu、OpenAICompatible。
- **Tier 2（社群維護）**：未列入 Tier 1 且仍支援者皆屬之；修正經 `help wanted` 標籤與貢獻者 PR。
- **已棄用（不再維護）**：Bing、Google。
- 免費服務：SiliconFlow 提供本專案免費翻譯服務（`THUDM/GLM-4-9B-0414` 模型）。

### 7.2 完整引擎清單（源碼 `TRANSLATION_ENGINE_METADATA`，權威）

| 引擎（type） | CLI 旗標 | 支援 LLM | 預設模型 / base URL / 重點欄位 |
|---|---|---|---|
| SiliconFlowFree | `--siliconflowfree` | 是 | 免 API key；**預設引擎**；`siliconflow_free_enable_json_mode=False`；免費模型 GLM-4-9B-0414 |
| OpenAI | `--openai` | 是 | `openai_model="gpt-4o-mini"`；`openai_base_url=None`；`openai_api_key=None`；timeout/temperature/reasoning_effort/enable_json_mode/send_temperature/send_reasoning_effort 皆可設 |
| AliyunDashScope | `--aliyundashscope` | 是 | `aliyun_dashscope_model="qwen-plus-latest"`；base `https://dashscope.aliyuncs.com/compatible-mode/v1`；timeout=500、temperature=0.0；enable_json_mode |
| Google | `--google` | 否 | **已棄用**；無設定欄位 |
| Bing | `--bing` | 否 | **已棄用**；無設定欄位 |
| DeepL | `--deepl` | 否 | `deepl_auth_key=None` |
| DeepSeek | `--deepseek` | 是 | `deepseek_model="deepseek-chat"`；`deepseek_api_key`；transform → base `https://api.deepseek.com/v1` |
| Ollama | `--ollama` | 是 | `ollama_model="gemma2"`；`ollama_host="http://localhost:11434"`；`num_predict=2000` |
| Xinference | `--xinference` | 是 | `xinference_model="gemma-2-it"`；`xinference_host=None` |
| AzureOpenAI | `--azureopenai` | 是 | `azure_openai_model="gpt-4o-mini"`；`azure_openai_api_version="2024-06-01"`；base_url/api_key 可設 |
| ModelScope | `--modelscope` | 是 | `modelscope_model="Qwen/Qwen2.5-32B-Instruct"`；transform → `https://api-inference.modelscope.cn/v1` |
| Zhipu | `--zhipu` | 是 | `zhipu_model="glm-4-flash"`；transform → `https://open.bigmodel.cn/api/paas/v4` |
| SiliconFlow | `--siliconflow` | 是 | base `https://api.siliconflow.cn/v1`；`siliconflow_model="Qwen/Qwen2.5-7B-Instruct"`；`enable_thinking=False`、`send_enable_thinking_param=False`、`enable_json_mode=False` |
| TencentMechineTranslation | `--tencentmechinetranslation` | 否 | `tencentcloud_secret_id` / `tencentcloud_secret_key` |
| Gemini | `--gemini` | 是 | `gemini_model="gemini-1.5-flash"`；transform → `https://generativelanguage.googleapis.com/v1beta/openai/`（即 OpenAI 相容端點） |
| Azure | `--azure` | 否 | `azure_endpoint="https://api.translator.azure.cn"`；`azure_api_key`（微軟翻譯器） |
| AnythingLLM | `--anythingllm` | 否 | `anythingllm_url`；`anythingllm_apikey` |
| Dify | `--dify` | 否 | `dify_url`；`dify_apikey` |
| Grok | `--grok` | 是 | `grok_model="grok-2-1212"`；transform → `https://api.x.ai/v1` |
| Groq | `--groq` | 是 | `groq_model="llama-3-3-70b-versatile"`；transform → `https://api.groq.com/openai/v1` |
| QwenMt | `--qwenmt` | 否 | `qwenmt_model="qwen-mt-plus"`；base `https://dashscope.aliyuncs.com/compatible-mode/v1`；內建學術論文翻譯長 prompt（`ali_domains`） |
| OpenAICompatible | `--openaicompatible` | 是 | `openai_compatible_model="gpt-4o-mini"`；`openai_compatible_base_url`／`openai_compatible_api_key`（**自訂 OpenAI 相容 API 的入口**） |
| ClaudeCode | `--claudecode` | 否* | `claude_code_path="claude"`；`claude_code_model="sonnet"`（*無 support_llm 欄位） |
| CLITranslator | `--clitranslator` | 否 | `clitranslator_command=""`；`clitranslator_timeout=60`（ge=1, le=300）；`clitranslator_postprocess_command=None`（自訂外部程式翻譯器） |

- `cli_flag_name` 依引擎 type 轉小寫（如 `--openai`）；引擎細節欄位命名 `<flag>_detail`。
- **術語抽取引擎**（`TERM_EXTRACTION_ENGINE_METADATA`）：僅支援 LLM 的引擎可用作術語抽取，共 14 個：SiliconFlowFree、OpenAI、AliyunDashScope、DeepSeek、Ollama、Xinference、AzureOpenAI、ModelScope、Zhipu、SiliconFlow、Gemini、Grok、Groq、OpenAICompatible。欄位前綴 `term_`（例 `term_openai_model`），CLI 旗標為 `--term-<flag>`。
- GUI 密碼遮罩欄位清單（17 個，含各 `*_api_key`、`tencentcloud_secret_id/key`）；敏感欄位另含各 base URL。

### 7.3 使用範例（文件原文）

```bash
# SiliconFlow 免費服務
pdf2zh_next --siliconflowfree example.pdf

# SiliconFlow 付費模型（API key 由使用者提供）
pdf2zh_next --siliconflow --siliconflow-model "Pro/deepseek-ai/DeepSeek-V3" --siliconflow-api-key <your-api-key> example.pdf
```

- SiliconFlowFree 隱私政策：檔案內容會送到維護者 @awwaawwa 的伺服器再轉發 SiliconFlow；維護者只收集錯誤資訊除錯，不收集檔案內容。
- Aliyun DashScope 建議設定（文件原文）：Translation Service `qwen-plus-latest`、Base URL 保持預設、timeout 500、temperature 0.0、Send temperature: True、Enable JSON mode: True；限流建議 Custom 模式 QPS 30–40、Pool Max Workers 1000。
- WebUI 選擇方式：Translation Options → Service 下拉選單；SiliconFlow 需填 Base URL（預設即可）、model、API key。

### 7.4 自訂 LLM（OpenAI 相容 API）

- 官方入口：`--openaicompatible` 引擎，搭配 `--openaicompatible-base-url`（自訂 base URL）、`--openaicompatible-model`、`--openaicompatible-api-key`；亦有多個內建引擎以「transform 到 OpenAI 相容端點」實作（DeepSeek、Zhipu、Gemini、Grok、Groq、ModelScope）。
- BabelDOC 純 CLI（無 pdf2zh_next）只支援 OpenAI 相容 LLM（`--openai-model`／`--openai-base-url`／`--openai-api-key`，可選 JSON mode；建議模型 `glm-4-flash`、`deepseek-chat`；可用 litellm 代理多模型）——但官方**不建議直接使用 BabelDOC CLI**，PDFMathTranslate-next 才有 WebUI 與更多服務。

**來源**：[Documentation-of-Translation-Services.html](https://pdf2zh-next.com/advanced/Documentation-of-Translation-Services.html)、[translate_engine_model.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/translate_engine_model.py)、[SiliconFlow.md](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/TranslationServices/SiliconFlow.md)、[Aliyun.md](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/TranslationServices/Aliyun.md)、[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)

---

## 8. WebUI

### 8.1 啟動

```bash
pdf2zh_next --gui
```

- 前置：Python 3.10–3.12（文件頁；pyproject 實為 >=3.10,<3.14）＋已安裝套件。
- 執行後瀏覽器應自動開啟；否則手動開 `http://localhost:7860/`。
- 操作：把 PDF 拖進視窗，點 **Translate**。
- Docker 內以 Ollama 為後端時，「Ollama host」欄填 `http://host.docker.internal:11434`。
- Docker 啟動：

```bash
docker pull awwaawwa/pdfmathtranslate-next
docker run -d -p 7860:7860 awwaawwa/pdfmathtranslate-next
# 或 GHCR：docker pull ghcr.io/pdfmathtranslate-next/pdfmathtranslate-next
```

### 8.2 GUI 選項（advanced.html GUI 旗標表）

- `--share`（分享模式）、`--auth-file`（username,password 行格式）、`--welcome-page`（自訂歡迎頁，需 auth file 才生效）、`--enabled-services`（例 `"Bing,OpenAI"`）、`--disable-gui-sensitive-input`、`--disable-config-auto-save`、`--server-port`（WebUI 埠）、`--ui-lang`（UI 語言）。
- WebUI 環境變數：`PDF2ZH_LANG_FROM`（預設 English）、`PDF2ZH_LANG_TO`（預設 Simplified Chinese）。
- GUI 支援：上傳術語表 CSV 並點檔名檢視內容；翻譯結果在下方 "Translated" 區塊。
- 安全註記：專案未經專業安全稽核；公開部署建議停用敏感輸入與設定自動儲存、限制服務清單。

**來源**：[USAGE_webui.html](https://pdf2zh-next.com/getting-started/USAGE_webui.html)、[INSTALLATION_docker.html](https://pdf2zh-next.com/getting-started/INSTALLATION_docker.html)、[advanced.html](https://pdf2zh-next.com/advanced/advanced.html)

---

## 9. 安裝

### 9.1 官方推薦（依作業系統）

| 方式 | 適用 | 來源 |
|---|---|---|
| Windows EXE（release 下載 zip） | Windows | INSTALLATION_winexe.html |
| Docker | Linux | INSTALLATION_docker.html |
| uv（Python 套件管理） | macOS | INSTALLATION_uv.html |

### 9.2 uv 安裝（原文指令）

```bash
pip install uv
uv tool install --python 3.12 pdf2zh-next
```

- PATH 錯誤 `command not found: pdf2zh_next` 時：
  - macOS/Linux：`export PATH="$PATH:/Users/Username/.local/bin"`（加進 `~/.zshrc`，重開終端）
  - Windows PowerShell：`$env:Path = "C:\Users\Username\.local\bin;$env:Path"`
- Python 版本：**文件頁寫 3.10 <= version <= 3.12**；**pyproject.toml 實為 `requires-python = ">=3.10,<3.14"`**（以 pyproject 為準，文件頁可能未更新）。

### 9.3 Docker

- 映像：`awwaawwa/pdfmathtranslate-next`（Docker Hub）／`ghcr.io/pdfmathtranslate-next/pdfmathtranslate-next`（GHCR，Docker Hub 無法存取時的替代）。
- 指令見 §8.1。文件頁**未列** volume mounts／環境變數（如 OPENAI_API_KEY）／compose／GPU 設定——無法取得。

### 9.4 Windows EXE

- 下載：release 頁的 `pdf2zh-<version>-with-assets-win64.zip`（**含字型與模型等資源檔**；相較 `pdf2zh-<version>-win64.zip` 不需要執行時動態下載——無 assets 版「download may fail due to network issues」）。
- 無法執行時安裝 Visual C++ Redistributable：https://aka.ms/vs/17/release/vc_redist.x64.exe
- 步驟：解壓縮（需時間）→ 進 `pdf2zh` 資料夾 → 雙擊 `pdf2zh.exe` → 等 30–60 秒 → 瀏覽器自動開 `http://localhost:7860/`。
- EXE 也能跑 CLI：

```bash
cd /path/pdf2zh_next/build
./pdf2zh_next.exe "document.pdf"
./pdf2zh_next.exe "document.pdf" --lang-in en --lang-out ja
```

### 9.5 依賴（pyproject.toml 完整清單）

`requests`、`pymupdf<1.25.3`、`tqdm`、`tenacity`、`numpy`、`ollama`、`xinference-client`、`deepl`、`openai>=1.0.0`、`azure-ai-translation-text<=1.0.1`、`gradio<5.36`、`tencentcloud-sdk-python-tmt`、`gradio-pdf>=0.0.21`、`peewee>=3.17.8`、`fontTools`、`babeldoc>=0.5.20,<0.6.0`、`rich`、`pydantic-settings>=2.8.1`、`pydantic>=2.10.6`、`httpx>=0.28.1`、`sse-starlette>=2.3.3`、`fastapi>=0.115.12`、`uvicorn>=0.34.2`、`legacy-cgi`（僅 python_version >= '3.13'）、`chardet>=5.2.0`、`gradio-i18n==0.3.4`、`pyyaml>=6.0.2`。

- **無 `[project.optional-dependencies]`**（沒有 `pdf2zh-next[llm]` 之類 extras——所有服務依賴皆為硬性）。
- Build：hatchling；script 入口：`pdf2zh`、`pdf2zh2`、`pdf2zh_next` → `pdf2zh_next.main:cli`。

**來源**：[INSTALLATION_uv.html](https://pdf2zh-next.com/getting-started/INSTALLATION_uv.html)、[INSTALLATION_docker.html](https://pdf2zh-next.com/getting-started/INSTALLATION_docker.html)、[INSTALLATION_winexe.html](https://pdf2zh-next.com/getting-started/INSTALLATION_winexe.html)、[pyproject.toml](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pyproject.toml)

---

## 10. Python API（高階層）

- 官方建議（BabelDOC README）：所有 BabelDOC API 皆為內部 API，Python 端一律用 pdf2zh_next 的 `high_level`。

```python
from pdf2zh_next.high_level import do_translate_async_stream

async for event in do_translate_async_stream(settings, file):
    # settings: SettingsModel（需先通過 settings.validate_settings()）
    # file: str | pathlib.Path（忽略 settings.basic.input_files，只譯此檔）
    ...
```

- 事件型別（dict）：`stage_summary`（可選，前置階段估算）、`progress_start`／`progress_update`／`progress_end`（stage 名、stage_progress 0–100、overall_progress 0–100、part_index/total_parts、stage_current/stage_total）、`finish`、`error`（error、error_type、details；之後 generator 再拋出 `TranslationError` 衍生例外，兩者都要處理）。
- `finish` 的 `translate_result` 屬性：`original_pdf_path`、`mono_pdf_path`、`dual_pdf_path`、`no_watermark_mono_pdf_path`、`no_watermark_dual_pdf_path`、`auto_extracted_glossary_path`、`total_seconds`、`peak_memory_usage`。
- `error_type` 列舉：`BabeldocError`、`SubprocessError`、`IPCError`、`SubprocessCrashError` 等。
- `report_interval`（SettingsModel 設定）只控制 `progress_update` 的發射頻率：預設 0.1s、最小 0.05s；`stage_total <= 3` 時不節流。
- 其他進入點：`do_translate_file_async(settings, ignore_error=False) -> int`（多檔驅動，rich 進度條，回傳 error 計數）、`do_translate_file(settings, ignore_error=False)`（同步包裝，處理 KeyboardInterrupt）。
- 範例輸出檔名（官方範例）：`pdf2zh_files/<session>/table.zh-CN.mono.pdf`、`table.zh-CN.dual.pdf`、`table.no_watermark.zh-CN.mono.pdf`、`table.zh-CN.glossary.csv`。
- 注意：該 API 文件自帶免責聲明「可能含 AI 生成內容」。

**來源**：[python.md](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/API/python.md)、[high_level.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/high_level.py)、[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)

---

## 11. 語言代碼

### 11.1 Google 代碼（部分重點；完整表見來源頁）

- 小寫；`en`（美式）、`en-GB`、`pt-BR`、`pt-PT`、`zh-CN`（簡中）、`zh-TW`（繁中）、`ja`、`ko`、`de`、`fr`、`es`、`ru`、`vi`、`th`…；希伯來語為 `iw`（非 `he`）。

### 11.2 DeepL 代碼（部分重點）

- 大寫：`ZH`（中，source+target）、`ZH-HANS`（簡中，僅 target）、`ZH-HANT`（繁中，僅 target）、`EN`／`EN-GB`／`EN-US`（GB/US 僅 target）、`JA`、`KO`、`DE`、`FR`、`ES`、`PT`／`PT-BR`／`PT-PT`、`RU`、`AR`、`TR`…。

### 11.3 BabelDOC 支援語言（pdf2zh 轉址指向此頁）

- 網址：https://funstory-ai.github.io/BabelDOC/supported_languages/ （「The information there also applies to pdf2zh」）。
- 重點：`EN`、`zh-CN`、`zh-HK`、`zh-TW`、`JA`、`KO`、`PL`、`RU`、`es`、`pt`、`fr`、`de` 等逾百種。
- **不支援依賴 ligature（連字）的語言**；Polish、French、Serbian（兩種字母）、Burmese、Oriya 標示「Partial」。
- 頁面列單有重複（Oriya、Croatian、Moldovan、Kyrgyz、Tagalog 各出現兩次），照錄。

**來源**：[Language-Codes.html](https://pdf2zh-next.com/advanced/Language-Codes.html)、[supported_languages.html](https://pdf2zh-next.com/supported_languages.html)、[BabelDOC supported_languages](https://funstory-ai.github.io/BabelDOC/supported_languages/)

---

## 12. 實驗／進階功能一覽（對照 §5 旗標）

- **Custom Prompt**：`--custom-system-prompt`（Qwen 3 `/no_think` 用法見 §5.3）。
- **Ignore cache**：`--ignore-cache` 強制重譯（快取機制見 §4.4）。
- **並行**：`--qps`／`--pool-max-workers`（＋術語側 `--term-qps`／`--term-pool-max-workers`）；官方調校公式見 §4.5。
- **分片翻譯**：`--max-pages-per-part`；事件層面的 part_index/total_parts。
- **部分翻譯**：`--pages "1,3,10-20,25-"`；可搭配 `--only-include-translated-page`。
- **術語表（glossary）**：`--glossaries`（CSV `source,target,tgt_lng`）、`--save-auto-extracted-glossary`、`--no-auto-extract-glossary`（LLM 自動術語抽取，14 引擎可用）。
- **公式保留**：`--formular-font-pattern`／`--formular-char-pattern`（regex）、`--formular-char-pattern` 對應、`--skip-formula-offset-calculation`。
- **版面／字型**：`--primary-font-family`（serif/sans-serif/script）、`--rpc-doclayout`（遠端版面分析 RPC）、`--split-short-lines`、`--short-line-split-factor`、`--no-merge-alternating-line-numbers`、`--no-remove-non-formula-lines`、`--non-formula-line-iou-threshold`、`--figure-table-protection-threshold`。
- **掃描檔**：`--skip-scanned-detection`、`--auto-enable-ocr-workaround`（重度掃描時啟用 OCR）、`--ocr-workaround`（譯文強制黑字白底）。
- **輸出控制**：`--no-dual`／`--no-mono`、`--dual-translate-first`、`--use-alternating-pages-dual`、`--watermark-output-mode`、`--output`、`--skip-clean`／`--enhance-compatibility`、`--disable-rich-text-translate`、`--translate-table-text`（表格翻譯，實驗性）。
- **離線資源**：`--warmup`（下載並驗證資源後退出）、`--generate-offline-assets`／`--restore-offline-assets`（打包/還原字型+模型）。
- **BabelDOC 整合**：無獨立旗標——next 本身就是 BabelDOC 的封裝（`babeldoc>=0.5.20,<0.6.0`），`create_babeldoc_config` 把 SettingsModel 對映成 BabelDOCConfig（含分片策略、浮水印模式、OCR model、glossary 等）。
- **font subsetting**：**未見於 next**（見 §5.4）。

**來源**：[advanced.html](https://pdf2zh-next.com/advanced/advanced.html)、[high_level.py](https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/high_level.py)、[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)

---

## 13. 已知限制（BabelDOC README 明列）

1. 作者與參考文獻區的解析錯誤：翻譯後會合併成單一段落。
2. 不支援「行（lines）」。
3. 不支援 drop caps（首字放大）。
4. 過大的頁面會被跳過。
- 路線圖：line 支援、table 支援、跨頁/跨欄段落、更多進階排版、outline 支援。

**來源**：[BabelDOC README](https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md)

---

## 14. 無法取得的資訊（誠實清單）

1. **API key 的環境變數名稱**（如 `OPENAI_API_KEY`）：官方文件頁未列出；源碼中 key 是 pydantic 欄位／CLI 旗標，env alias 機制在 `SettingsModel`（未逐檔抓取 `config/model.py` 全文）。→ 需直接看 `config/model.py` 才能確定。
2. **`--skip-font-subsetting`**：next 的官方旗標表與引擎 metadata 皆無；未逐一掃描全部源碼確認。
3. **`--threads`／`--jora`／`--scihub`／`--llm`／`--webui`／`--port`／`--timeout`／`--retries`** 等：未出現在 next 官方文件；判斷屬 1.x 或舊版。
4. **Docker 進階設定**（volume mount、API key 傳遞、compose、GPU）：Docker 安裝頁未含，無法取得。
5. **README 原始 markdown 全文**：raw 抓取仍回渲染 HTML；已取得內容與主頁渲染版一致（README 本身即無 CLI 範例）。
6. **PDF 解析/渲染的內部細節**（BabelDOC 中間表示格式、字型嵌入方式）：BabelDOC README 只有兩階段總述，未提供細節。
7. **GitHub 統計與版本號**為 2026-08-12 抓取當下數值，會隨時間變動。

---

## 15. 與 Paper_Kit 的關聯（差異分析）

**Paper_Kit 目標**（記憶：自建 UI 翻譯器、引擎鎖 Python pdf2zh 家族、UI 首選 NiceGUI、TDD＋DDD＋Ports&Adapters、repo PRIVATE）。以下為 pdf2zh-next 具備、Paper_Kit 目前架構**沒有或需考慮引入**的功能：

1. **翻譯快取（ignore-cache 對應物）**：SQLite keyed by `(engine, engine_params, 原文)`，可跨 session 省 LLM 費用——Paper_Kit 目前沒有翻譯快取設計。
2. **QPS/pool 並行模型**：`--qps`＋`--pool-max-workers`（含術語抽取獨立 pool）＋官方調校公式（RPM→qps、pool=qps*10）——Paper_Kit 若接多 worker 並行翻譯需此設計。
3. **Custom system prompt**：`--custom-system-prompt`（Qwen 3 `/no_think` 為實例）——Paper_Kit 沒有 prompt 覆寫機制。
4. **術語表（glossary）**：CSV `source,target,tgt_lng` 手動上傳＋LLM 自動抽取＋自動儲存抽取結果——Paper_Kit 沒有。
5. **版面分析模型層**：DocLayout-YOLO＋RPC 遠端版面分析（`--rpc-doclayout`）＋掃描偵測與 OCR workaround（RapidOCR）＋公式字型/字元 regex pattern 保留——Paper_Kit 目前沒有版面/公式感知。
6. **分片與部分翻譯**：`--max-pages-per-part` 自動分片（大文件進度事件帶 part 資訊）、`--pages "1,3,10-20,25-"` 部分翻譯——Paper_Kit 沒有。
7. **輸出多型**：mono/dual/無浮水印版本、`--dual-translate-first`、交替頁模式、`--watermark-output-mode`——Paper_Kit 目前只輸單一版本。
8. **進度事件流契約**：`stage_summary/progress_*`（stage 內 0–100 與 overall 0–100）＋`finish` 結果物件（含 token 用量、peak memory）——Paper_Kit 的 UI 若要即時進度需此契約；且**應直接對接 `pdf2zh_next.high_level.do_translate_async_stream` 而非 BabelDOC 內部 API**（BabelDOC 官方明言不支援直接使用）。
9. **引擎即插即用（metadata 驅動）**：25 引擎清單集中在 `TRANSLATION_ENGINE_METADATA`，Ports&Adapters 的「Port」設計可仿照；「支援 LLM 的引擎可兼任術語抽取」的組合式設計值得借鏡。
10. **警訊**：next 已將 **Bing/Google 標記為棄用**（1.x 時代的免費主力是 Google）——Paper_Kit 若以 1.x 或免費服務為依賴須注意風險；next 的免費方案目前為 SiliconFlowFree（GLM-4-9B-0414，檔案會經第三方伺服器轉發）。
11. **授權風險**：AGPL-3.0——Paper_Kit 若直接內嵌/改寫 pdf2zh-next 或 BabelDOC 程式碼，repo 需注意 AGPL 義務（Paper_Kit 目標 repo 為 PRIVATE，但仍須注意散布義務）；以 pip 依賴黑盒方式呼叫則影響較小（高階 API 文件授權態勢建議諮詢/另行查證，本文件不構成法律意見）。

---

## 16. 參考來源 URL 總表

- https://github.com/PDFMathTranslate/PDFMathTranslate-next
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/README.md
- https://pdf2zh-next.com/getting-started/INSTALLATION_uv.html
- https://pdf2zh-next.com/getting-started/INSTALLATION_docker.html
- https://pdf2zh-next.com/getting-started/INSTALLATION_winexe.html
- https://pdf2zh-next.com/getting-started/USAGE_commandline.html
- https://pdf2zh-next.com/getting-started/USAGE_webui.html
- https://pdf2zh-next.com/advanced/advanced.html
- https://pdf2zh-next.com/advanced/Documentation-of-Translation-Services.html
- https://pdf2zh-next.com/advanced/Language-Codes.html
- https://pdf2zh-next.com/supported_languages.html
- https://funstory-ai.github.io/BabelDOC/supported_languages/
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/API/python.md
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/TranslationServices/SiliconFlow.md
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/docs/en/advanced/TranslationServices/Aliyun.md
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pyproject.toml
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/high_level.py
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/cli_env_model.py
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/config/translate_engine_model.py
- https://raw.githubusercontent.com/PDFMathTranslate/PDFMathTranslate-next/main/pdf2zh_next/translator/cache.py
- https://raw.githubusercontent.com/funstory-ai/BabelDOC/main/README.md
- https://github.com/guaguastandup/zotero-pdf2zh（第三方 Zotero 外掛）
- https://app.immersivetranslate.com/babel-doc/（Immersive Translate BabelDOC 線上服務）
