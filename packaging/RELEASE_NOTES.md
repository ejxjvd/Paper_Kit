# Paper_Kit Release Notes

> CI 建 Release 時依 tag 提取對應區段作為 notes（見 `.github/workflows/release.yml`）。

## v0.1.7

### 🆕 新功能

- **智譜 Z.AI 免費引擎回補**（國際站 api.z.ai）：GLM-4.7-Flash（思考型、中文強）免費——模型 ID 須小寫；免費引擎區排第 2
- **ModelScope 全模型實測**（綁阿里雲後 42 模型全測，36/42 可生成）
- **Groq rate-limits 查證回補**：免費層 gpt-oss-120b 為 30 RPM／1K RPD／8K TPM／200K TPD（原「14,400 RPD」為誤植）

### 🐛 修復

1. **preflight 被 Cloudflare 指紋封鎖**（Groq 實測抓到）：urllib 預設 UA（`Python-urllib/3.x`）被 Groq 的 Cloudflare 擋掉（403 error 1010）——curl 200 但程式誤擋；改瀏覽器式 UA，各引擎同受惠
2. **ModelScope 思考型模型陷阱**：DeepSeek-V4-Pro／GLM-5.2 思考型模型的 `max_tokens` 被推理耗盡 → `message.content=None` → 翻譯崩潰（**HTTP 200 ≠ 可用**）；預設模型改為 non-thinking 的 **DeepSeek-V3.1**（翻譯 40.9s 實測產出正常）＋不變式測試防回歸（禁思考型模型設為預設）

### ✅ 真翻譯驗證

- Z.AI glm-4.7-flash：fixture 2 頁 275s 產出 mono+dual
- Groq gpt-oss-120b：72.6s 產出 mono+dual
- ModelScope DeepSeek-V3.1：40.9s 產出 mono+dual

## v0.1.6

### 🆕 新功能

- **假成功杜絕（#78 常駐問題包）**：翻譯前**自動預檢**（openai 引擎 POST 零成本驗證 key＋模型，非 200 直接報錯、引擎不上）——「顯示成功但沒產出 PDF」從根杜絕
- **錯誤即時診斷**：404→模型不存在、429→限流、401/key 無效→key 無效（附引擎 log）
- **「測試 API」補盲區**：除驗證 key 活性外，額外實際生成一次（max_tokens=1 零成本）確認「模型可生成」——清單有顯示≠可生成
- **Google Gemini 引擎**：28 模型實測、7 個可用（2.5-flash 43s 等）
- **國際站轉移**：ModelScope `.cn`→`.ai`、移除智譜中國站死卡（免費 GLM 需中國手機＋實名）——所有引擎皆國際站端點

### ✅ 真翻譯驗證

- Gemini gemini-pro：fixture 2 頁 84s 產出 mono+dual

## v0.1.5

### 🆕 新功能

- **CMD 狀態列 log**：黑色視窗即時顯示人類可讀狀態列（進度＋本地時區時間戳）——翻譯中可看進度，不再只有啟動訊息

### 🐛 修復

1. **NIM 翻譯超時常駐修復（重複問題 ≥3 次）**：「翻譯超時（超過 300 秒無輸出）」真因＝tqdm 非 TTY 不 flush＋8KB 緩衝＋NIM 120B 單頁 402s vs 誤判 300s 閒置——修 `PYTHONUNBUFFERED=1`＋引擎閒置超時可設（NIM 900 秒兜底）

### ✅ 真翻譯驗證

- NVIDIA NIM：OS_Chapter03.pdf 前 2 頁 142s 產出 mono+dual（in=2953/out=5748）

## v0.1.4

### 🐛 修復

1. **NVIDIA NIM 翻譯失敗（`--qps: invalid int value: '0.6'`）**：v0.1.3 節流把 `--qps` 當浮點數傳入，但 pdf2zh_next 的 CLI 契約為整數（argparse type=int）——修正為 `--qps 1`＋單線程串行（`--pool-max-workers 1`）；實際請求間隔由每次 LLM 生成時間（數秒）決定，遠低於 NIM 免費層 40 RPM

### 🆕 新功能

- **引擎模型挑選 UI**：設定頁引擎卡「🔄 載入模型清單」即時拉取該 API 最新模型下拉挑選（可自訂輸入）＋「儲存模型」——官方模型下線（EOL）不用等更新

## v0.1.3

### 🆕 新功能

- **NVIDIA NIM 免費引擎**：nemotron-3-super-120b-a12b 預設（WMT24++ 55 語種翻譯榜 #1）——免費層 40 RPM，內建節流
- **NIM 多模型品質評測**：nemotron 24s／gemma 41s 實測；gemma thinking 陷阱關閉（慢 10 倍）

### 🐛 修復

1. **NVIDIA EOL 410**：deepseek-v4-flash 下線 → 0731 快照
2. **Debug 時區**：UTC 存→本地顯示

## v0.1.2

### 🐛 修復

1. **AES-256 加密 PDF 判定錯誤**（「不是有效 PDF？」假象——真因缺 cryptography 依賴）＋錯誤訊息帶真實原因

### 🆕 新功能

- **portable 資料目錄**：資料跟程式走（`data/` 在 exe 旁）——刪除資料夾即完全移除、系統零殘留；`--uninstall` 可選保險

## v0.1.1

### 🆕 新功能

- **uv 自動安裝**：偵測→自動下載官方二進制（app 專屬目錄、不需管理員權限）——首次選用 BabelDOC 等自動就緒
- **macOS 相容**：瀏覽資料夾用 Finder、CI 自動出 mac 包
- **打包工程化＋CI 雙平台**：build.py 冒煙測試（HTTP 200＋監聽 PID）→ win-x64＋macos-arm64 雙資產自動上架

## v0.1.0

### 🆕 首版

- exe 打包（PyInstaller onedir，console 可見視窗）＋GitHub Release 上架
- 四引擎（SiliconFlow／DeepSeek／BabelDOC／LaTeX）＋免費三引擎（google/bing/siliconflowfree）
- 機密模式、RapidOCR 本機掃描、成本可見、歷史管理、術語表
