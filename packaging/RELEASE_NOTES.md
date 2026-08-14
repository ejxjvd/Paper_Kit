# Paper_Kit Release Notes

> CI 建 Release 時依 tag 提取對應區段作為 notes（見 `.github/workflows/release.yml`）。

## v0.1.9.2

### 🐛 緊急修復：翻譯任務同秒失敗（2026-08-15 使用者真機抓到）

v0.1.9.1 Windows exe 實測發現：任務建立→開始翻譯→**同秒失敗**
`AttributeError: module 'paper_kit.platform.windows' has no attribute 'processes'`。

- **根因**：平台分派（`platform/__init__.py`）以屬性查找取用子模組
  （`windows.processes`／`windows.explorer`／`macos.processes`／`macos.finder`），
  而「import package」不會掛載子模組屬性——只有某處 import 過子模組才存在。
  pytest 恰被測試檔頭部 import 的副作用遮蔽（v0.1.9.1 全套件 761 passed 假象）；
  frozen exe 無此副作用 → `spawn_kwargs()` 每翻譯必呼叫 → 立即 AttributeError。
- **修復**：`platform/__init__.py` 顯式 import 四個子模組（分派父層職責，不違反
  macOS／Windows 互不 import 的分離守則）；PyInstaller 分析器亦以本層 import
  為準收包（子模組必進 exe）。
- **防回歸**：新測試以**獨立解釋器**（無測試側 import 副作用）實呼
  `spawn_kwargs()`＋`kill_tree()` 兩個分派入口——本機 Linux／CI Windows、
  macOS runner 各走真實平台分支。
- **Windows／macOS 同修**：macOS 分支（finder／processes）同一修法掛載——
  mac exe 同病同藥，CI macos-arm64 實跑驗證。

### ✅ 驗證

- TDD 1 新測試先紅後綠（修復前乾淨解釋器實測 AttributeError 重現使用者症狀）
  ——全套件 **762 passed**（+1）
- 真實翻譯驗證（驗證紀律）：adapter 路徑（google 免費引擎、paper_p34.pdf
  第 1 頁）**19.1s 產出 mono 464KB＋dual 455KB**——分派修復後真實執行路徑成功

## v0.1.9.1

### 🐛 macOS 嚴重問題修復（使用者實測轉交，BUG_REPORT_macOS_v0.1.8）

v0.1.8 macOS arm64 實測四問題全數修復（TDD 4 新測試鎖定）：

1. **`resource_tracker` 子程序無限遞迴（實測 117 程序連鎖）**：frozen exe＋macOS spawn 啟動模式 → 子程序重跑主程式。修復：入口**第一行** `multiprocessing.freeze_support()`（PyInstaller 官方慣例；Windows frozen exe 同受惠）——啟動 30 秒後程序數不再增加
2. **8080 被佔用仍輸出「NiceGUI ready」假象＋`connection lost`**：修復：啟動前 port 檢查——被佔用時顯示明確錯誤＋排查指令（macOS/Linux `lsof`、Windows `netstat`）後退出（exit 1），不再假裝就緒
3. **重複啟動 8080 衝突**：同上攔下（第二實例啟動即明確報錯）
4. **PDF 上傳 `connection lost`**：根源＝程序連鎖＋埠衝突——修復後上傳不再斷線

### 🖥️ 平台分離（2026-08-14 使用者要求：macOS／Windows 各自乾淨專案）

- 源碼統計：7,618 行中平台分支僅 18 處（99.8% 平台無關共用核心）——全部收斂於新 `src/paper_kit/platform/` 套件：
  - `platform/macos/`：macOS 版專屬（Finder 開啟、POSIX 樹殺）
  - `platform/windows/`：Windows 版專屬（explorer 開啟＋WSL 路徑正規化、taskkill 樹殺）
  - `platform/uv_assets.py`：uv 官方二進制資產查表（win32/darwin/linux）
  - 分離鐵律測試：macos/ 與 windows/ **互不 import**（AST 掃描鎖定，新增模組自動守門）
- 打包分離：`packaging/macos/` 與 `packaging/windows/` 各自 spec（UPX mac 不適用）＋專屬手冊（macOS 版含 Gatekeeper 繞過／`xattr -dr com.apple.quarantine` 整包處理／SHA-256 驗證／lsof 除錯）
- App 內版本標註：瀏覽器標題「Paper_Kit 論文翻譯器（Windows 版／macOS 版）」
- 共用核心（application/domain/infrastructure 其餘）零平台分支——未來平台行為一律進 platform/ 套件

### ✅ 驗證

- TDD 16 新測試（平台分離 12：標籤／open_folder 三平台分派／kill_tree 分派／spawn 參數／隔離鐵律；macOS 入口 4：port 檢查、freeze_support 最前、佔用明確退出）——全套件 **761 passed**（+16）
- macOS 驗收條件（朋友實測回饋後）：程序數不增、`lsof` 單一監聽者、`curl -I` 穩定、上傳不 connection lost、關閉無殘留

## v0.1.9

### 🆕 新功能

- **術語庫擴充（#90）**：設定頁新增「匯入樂詞網詞表」按鈕——一鍵匯入 **`naer-core`**（國家教育研究院樂詞網學術名詞 **30,073 條單詞層**，電子計算機／電機工程／食品科技／魚類四領域全量）：
  - 授權：**政府資料開放授權條款-第 1 版**（可再授權、商業可用、僅需顯名聲明——docstring／生成腳本檔頭即顯名聲明）；取代無 LICENSE 不可用的 immersive-translate/terms 來源（研究查證見 `docs/research/2026-08-14-Paper_Kit-研究-GitHub術語庫全面掃描-查證.md`）
  - 資料為版本化 gzip 資源檔（`src/paper_kit/infrastructure/data/naer_core.csv.gz`，0.37 MB）；生成可重現：`uv run python scripts/naer_build.py`（下載樂詞網 ODS → 過濾 → gzip）
  - 選取準則：source 小寫字母開頭、單詞、無括號/引號/檔名/代碼噪音；target 無簡體字形污染（官方品質，簡體防線實測 0 命中）
  - seed 冪等（已存在不覆寫，與 paper-kit-basic 同契約）；大詞表編輯頁自動截斷（顯示前 500 條＋計數提示）不卡 UI

### 🐛 修復

1. **免費引擎＋術語表任務必敗（真機實測抓到）**：`--google --glossaries` 真翻譯實測引擎直接拒絕「Google does not support glossary. Please choose a different translator or remove the glossary.」——google/bing 不支援術語表，build_command 原無條件送 `--glossaries`。修復：google/bing＋術語表 → 明確 EngineError（「請改用付費引擎、siliconflowfree 或取消勾選術語表」），付費引擎與 siliconflowfree 行為不變（TDD 新測試鎖定）
2. **術語表 0 條匯入誤導**（DEBUG log 真機定案）：三欄 CSV 的 `tgt_lng`（如 zh-TW）與任務目標語言（如 zh）不符時，BabelDOC 語言過濾器**整表跳過 0 條**——UI 舊行為綠字「已匯入（0 條）」，使用者以為成功、任務卻無詞表可用。修復：0 條匯入負面警示＋提示原因（CSV 無資料或 tgt_lng 語言不符）＋手冊說明兩欄格式為語言中性（TDD 新測試鎖定）

### 📖 詞表生效真相（2026-08-14 DEBUG 真機定案）

- **載入鏈路全通**（`--glossaries` → settings → `Glossary.from_csv` → hyperscan 建 DB）；斷點是 **tgt_lng 語言過濾器**——`zh_tw ≠ lang_out` → 全跳過
- **兩欄 CSV（source,target，無 tgt_lng）＝語言中性**：任何目標語言（zh／zh-TW）都全量載入生效；seed_naer 產出即兩欄（領域 `to_csv` 收斂）
- 真機 DEBUG 鐵證：三欄 0 entries vs 兩欄 **30,070 entries**（0.52s 建 DB）→ 產出檔 483,518 B vs 495,141 B（譯文改變＝詞表生效）

### ✅ 驗證

- TDD 13 新測試先紅後綠（資料契約 7：資源存在/可解析/規模 >2 萬、source 契約、tgt_lng 全 zh-TW、naive CSV 相容、source 唯一、學術詞抽樣、seed 冪等；UI 3：樂詞網按鈕建立＋冪等、0 條匯入警示；免費引擎守衛 3：google/bing 擋＋siliconflowfree 放行送旗標）——全套件 **745 passed**
- 真翻譯驗證（真 runner／真 API／產出檔，2026-08-14 實測）：
  - **SiliconFlow 國際站付費引擎＋naer-core 兩欄詞表**：35.9s 產出 mono PDF 495 KB；DEBUG 證 30,070 條載入＋產出檔改變＝詞表生效
  - **siliconflowfree 免費引擎＋naer-core 詞表**：42.2s 產出 mono PDF 480 KB（支援術語表，源碼 support_llm=yes＋真機雙證）
  - **google 免費引擎（無詞表，正確組合）**：17.8s 產出 mono PDF 482 KB
  - 詳見 docs/research/2026-08-14-Paper_Kit-研究-術語庫對比分析 §4

## v0.1.8

### 🐛 修復

1. **空殼模型誤報 401（#79）**：HTTP 200 但 `choices=null` 的「登錄但未提供服務」模型群（實測 ERNIE-4.5-300B/21B、Hy3、Intern-S1、GLM-4.7-Flash）——pdf2zh 在 `choices[0].message.content` 對 `NoneType` 拋 TypeError，traceback 的「line 401」**行號**被 401 診斷 regex 誤判為「API key 無效」。修復：
   - 翻譯前預檢（與設定頁「測試 API」同源）對 200 空殼回報 **590「模型未提供服務」**（登錄但未開放，換模型或換引擎）
   - 引擎 log 診斷：空殼特徵（`choices[0]`＋`NoneType`，含思考型 `content=None`）優先辨識＋排除 traceback 行號誤判

### 🆕 新功能

- **架構健檢卡① 端點探測收斂**（內部品質）：設定頁「測試 API」／「載入模型清單」／翻譯前預檢三處共四份探測邏輯收斂為單一模組 `llm_probe`——v0.1.7 的瀏覽器 UA 修復任一端改動全端生效；淨刪 371 行

### ✅ 驗證

- TDD 5 新測試先紅後綠（probe_model 590×2、diagnose 590、line 排除、空殼簽名）——全套件 701 passed
- 架構健檢卡① 測試隨遷移（76 個探測/UI/preflight 測試全綠）

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
