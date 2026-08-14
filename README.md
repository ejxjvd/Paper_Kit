# 📄 Paper_Kit

[![Release](https://img.shields.io/github/v/release/ejxjvd/Paper_Kit?label=最新發布)](https://github.com/ejxjvd/Paper_Kit/releases)
[![Tests](https://img.shields.io/badge/tests-745%20passed-green)](https://github.com/ejxjvd/Paper_Kit/actions)

**自建學術 PDF／簡報翻譯器 —— 免除被線上翻譯工具綁架。**

純 Python 一體的 Web UI：拖放 PDF 上傳即翻譯成繁體中文（mono 僅譯文＋dual 雙語並排）。
LaTeX 源碼路線整本約 **NT$0.34**、PDF 路線整本 **NT$5–8**。四引擎可插拔、BYOK——
交付他人各用各的 key，您的 key 不外流。

## ✨ 功能

- 🖼️ **主頁就地選引擎**：SiliconFlow（gemma 視覺，預設）／DeepSeek（機密文件專用）／BabelDOC（版面重排）／LaTeX 四卡＋目標語言就地選
- 📐 **LaTeX 源碼路線**（票 27）：上傳 `.tex` 自動鎖定 LaTeX 引擎——公式指令原封、xelatex 編譯重排，token 最省（整本 ≈NT$0.34）
- 📑 **雙輸出**：每筆任務產 mono（僅譯文）＋dual（雙語對照），卡片與歷史表格皆可下載
- 🗂️ **歷史管理**：表格化＋分頁＋勾選全選＋批量刪除（二次確認）＋批量下載 mono/dual zip
- 🔑 **BYOK**：引擎 API keys 每引擎獨立——交付他人各用各的 key；遮罩回顯、未填攔截
- 🔒 **機密模式**：R18／隱私文件只准 DeepSeek 純文字引擎（視覺模型不上雲）
- 🔍 **掃描件 OCR**：本機 RapidOCR（onnxruntime）預處理，不上雲——機密相容
- 💰 **成本可見**：估算→實際成本＋tokens 用量；引擎單價可在設定頁調整
- ⚙️ **工程面**：務實 DDD＋Ports & Adapters＋TDD（紅→綠、垂直切片）——**745 tests passed**

## 🚀 快速開始

### 一般使用者（免安裝版）

從 [Releases](https://github.com/ejxjvd/Paper_Kit/releases) 下載對應平台的 zip：

| 平台 | 檔案 | 說明 |
|---|---|---|
| Windows x64 | `paper-kit-v0.1.9-win-x64.zip` | 解壓 → 雙擊 `paper-kit-v0.1.9.exe` |
| macOS（Apple 晶片） | `paper-kit-v0.1.9-macos-arm64.zip` | 解壓 → 右鍵 exe →「開啟」（繞過 Gatekeeper） |

瀏覽器自動開啟 http://localhost:8080/。自包含免安裝（內建 Python runtime＋全部依賴），操作說明見資料夾內 `README-使用手冊.md`。
**首次使用需連網**：第一次選用需要外部引擎的翻譯路線時自動下載所需工具（uv）與引擎；之後離線可重複使用。

### 開發者（原始碼）

先決條件：Python ≥3.12＋[uv](https://docs.astral.sh/uv/)、任一引擎的 API key
（SiliconFlow 為預設；`google`／`bing`／`siliconflowfree` 三支免費引擎不需 key）。

```bash
uv sync                # 安裝依賴
uv run paper-kit       # 啟動（預設 http://localhost:8080）
```

開啟 http://localhost:8080 → 拖放 PDF 或 .tex →（選頁面範圍）→ 選引擎 → 開始翻譯。

### 交付他人使用

- **BYOK（推薦）**：每個使用者在自己的設定頁填各自的 API key（每引擎獨立、遮罩回顯）——您的 key 不會外流、費用各自承擔
- **免費引擎**：三支不需 key 的引擎已內建（`google`／`bing`／`siliconflowfree`）——限流／品質較低，適合試用入口
- **自架選項**：本機 ollama 等 OpenAI 相容後端可直接插（引擎註冊表單點）——零 API 費用
- 免費引擎（Free-LLM-Collection）查證與品質優先序收錄於開發知識庫

## 📖 使用教學

| 想做什麼 | 怎麼做 |
|---|---|
| 翻譯 PDF | 拖放上傳 → 勾選頁面範圍（可多選）→ 選引擎 → 開始；完成後卡片／歷史頁下載 mono、dual |
| 翻譯 .tex | 拖放 `.tex` → 自動鎖定 LaTeX 引擎（整份編譯、無頁面範圍） |
| 機密文件 | 勾選 🔒——引擎自動切 DeepSeek、視覺卡灰化（R18／隱私不上雲） |
| 掃描 PDF | 勾選 🔍——本機 OCR 抽出文字層再翻譯 |
| 設定 keys／預設值 | 設定頁：引擎 keys、目標語言、輸出目錄、引擎單價、術語表庫、翻譯快取 |

## 🏗️ 架構

> 換引擎＝換插頭，不被單一供應商綁死。

- **Ports & Adapters**：`TranslationEnginePort`／`JobRepository`／`OcrPort`／`TeXCompilePort`——引擎註冊表（`engine_registry`）單點分派四支 adapter
- **務實 DDD**：domain（`TranslationJob` 狀態機）→ application（`JobService` 等）→ infrastructure（SQLite repo／adapter）→ presentation（NiceGUI＋handlers 純函式，widget 邏輯盡量薄）
- **TDD**：紅→綠、垂直切片、590 tests；20+ 張票全部完成，後續工作以 GitHub issues 追蹤

## 📁 文件

規格書（PRD）、20 張開發票（GitHub issues #2–#22 同步）、研究與問題修復紀錄
已移至開發知識庫管理——專案文件不入 repo，repo 只留程式碼。

## 📊 狀態

票 01–20 全部完成＋快取三票（24–26）＋票 27 LaTeX 主 UI 整合＋架構健檢 #1–9＋v0.1.3–v0.1.9（NVIDIA EOL 修復、引擎模型挑選、NIM 節流、免費引擎守衛、術語庫擴充）——**745 tests passed**
（2026-08-14）；冒煙全綠。**v0.1.9 已發布**（免安裝 exe 版：portable 資料跟程式走＋`--uninstall` 乾淨卸載＋術語庫 naer-core 30,073 條擴充＋免費引擎術語表守衛，見 [Releases](https://github.com/ejxjvd/Paper_Kit/releases)）。後續工作以 GitHub issues 追蹤。

## 🙏 致謝

- [pdf2zh-next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)（BabelDOC 管線：公式保真＋原像重排版）
- [NiceGUI](https://nicegui.io/)（純 Python 一體 Web UI）
- SiliconFlow／DeepSeek 引擎、xelatex（LaTeX 編譯）
