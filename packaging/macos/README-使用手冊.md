# 🍎 Paper_Kit v0.1.9.1（macOS 版）使用手冊

> 平台分離（2026-08-14）：本手冊為 **macOS 版**專屬（Apple Silicon arm64 主
> 目標）——Windows 版手冊見 Windows 資產 zip 內附。程式碼層 macOS／Windows
> 各自獨立資料夾（src/paper_kit/platform/），互不污染。

**自建學術 PDF／簡報翻譯器 —— 免除被線上翻譯工具綁架。**

- 拖放 PDF 上傳即翻譯成繁體中文（mono 僅譯文＋dual 雙語並排）
- LaTeX 源碼路線整本約 **NT$0.34**、PDF 路線整本 **NT$5–8**
- 多引擎可插拔、BYOK（Bring Your Own Key）——各用各的 key，您的 key 不外流

---

## ✅ v0.1.9.1 重大修復（macOS 版必讀）

v0.1.9.1 修復 v0.1.8 實測發現的四個 macOS 問題（2026-08-14 使用者轉交）：

| 問題 | 修復 |
|---|---|
| 啟動後 `resource_tracker` 子程序無限連鎖（實測 117 程序） | 入口加入 `multiprocessing.freeze_support()`（PyInstaller 官方慣例）——frozen exe＋macOS spawn 啟動模式不再重跑主程式 |
| 8080 埠被佔用時仍輸出「NiceGUI ready」假象＋`connection lost` | 啟動前檢查 port——被佔用時顯示明確錯誤與排查指令後退出（不再假裝就緒） |
| 重複啟動 8080 衝突 | 同上：第二個實例啟動即明確報錯退出 |
| PDF 上傳 `connection lost` | 上傳失敗根源＝程序連鎖＋埠衝突——修復後（驗收條件見下）不再發生 |

**驗收條件**（修復後實測）：
- 啟動 30 秒後程序數維持不增（`ps -A | grep paper-kit` 應只有 1 個主程序）
- `lsof -nP -iTCP:8080 -sTCP:LISTEN` 只看到一個監聽者
- `curl -I http://127.0.0.1:8080/` 穩定回應
- 上傳 PDF 不再 `connection lost`
- 關閉主程序後無殘留子程序

---

## 🚀 快速啟動

1. 下載 `paper-kit-v0.1.9.1-macos-arm64.zip`（Apple 晶片）並解壓
2. **驗證檔案**（可選但建議）：下載後先比對 SHA-256（發布頁 Release notes 有附）
   ```bash
   shasum -a 256 paper-kit-v0.1.9.1-macos-arm64.zip
   ```
3. **首次開啟需繞過 Gatekeeper**（本程式未簽署 Developer ID，v0.1.8 起已知狀況）：
   - 方法 A（僅此一次）：右鍵執行檔 → 選「開啟」→ 再點「開啟」
   - 方法 B（整包一次處理，推薦）：Terminal 執行
     ```bash
     xattr -dr com.apple.quarantine "/下載路徑/paper-kit-v0.1.9.1"
     ```
     > ⚠️ 必須對**整個資料夾**遞迴移除——只移除主執行檔的隔離標記不夠：
     > 內嵌 Python 等檔案仍帶 quarantine 時，macOS 會拒絕載入
     > （`library load disallowed by system policy`，v0.1.8 實測錯誤）。
4. Terminal 執行（建議在資料夾內）：
   ```bash
   cd "/下載路徑/paper-kit-v0.1.9.1"
   ./paper-kit-v0.1.9.1
   ```
   看到 `NiceGUI ready to go on http://localhost:8080` 即啟動成功。
5. 瀏覽器開啟 **http://localhost:8080/** → 先到**設定頁**填入引擎 API key
6. 拖放 PDF（或 .tex）→ 選引擎 → 開始翻譯

> 伺服器停止：在 Terminal 按 `Ctrl+C` 即可（關閉 Terminal 視窗亦會停止）。

> ⚠️ **首次使用需連網**：第一次選用需要外部引擎的翻譯路線時，程式會自動下載
> 所需工具與引擎——之後離線可重複使用已下載的工具。

---

## 🔧 macOS 疑難排解

- **Gatekeeper「無法驗證是否含有惡意軟體」**：右鍵 → 開啟（方法 A）或整包
  `xattr -dr com.apple.quarantine`（方法 B）。正式交付版（簽署＋notarization）
  在未來版本計畫中。
- **`library load disallowed by system policy`**：隔離標記殘留——對整個資料夾
  遞迴移除（見快速啟動步驟 3 方法 B），不是只移主執行檔。
- **8080 埠被佔用**：
  ```bash
  lsof -nP -iTCP:8080 -sTCP:LISTEN
  ```
  若是舊的 Paper_Kit 執行個體 → 關閉它（或 `kill <PID>`）後重啟；若 v0.1.9.1
  啟動時偵測到佔用，會直接顯示明確錯誤並退出（不再假裝就緒）。
- **關閉後有殘留程序**：`ps -A | grep paper-kit` 找到殘留 PID → `kill <PID>`
  （v0.1.9.1 正常關閉應無殘留——若仍發生請回報）。

---

## ⚙️ 設定 API keys（BYOK）

- 每個引擎的 key **獨立**設定、遮罩回顯、可個別清除
- 未填 key 的引擎無法選用（卡片會灰化）
- 免費引擎三支不需 key：`google`／`bing`／`siliconflowfree`（限流、品質較低，適合試用）

### 需 key 引擎

| 引擎 | 用途 | key 來源 |
|---|---|---|
| SiliconFlow（預設） | gemma 視覺翻譯，一般 PDF | SiliconFlow 付費 key |
| NVIDIA NIM（免費旗艦） | nemotron 3 Super 120B——WMT 品質第一、1M 上下文 | NVIDIA 免費帳號 API key |
| 智譜 Z.AI（免費） | GLM-4.7-Flash（思考型、中文強） | api.z.ai 免費 key（小寫模型 ID） |
| ModelScope 魔搭（免費） | DeepSeek-V3.1（品質天花板、中文最強） | modelscope.ai 免費 key（須綁阿里雲帳號） |
| Groq（免費） | gpt-oss-120b 高速推理（30 RPM／1K RPD） | console.groq.com 免費 key |
| Google Gemini | gemma-4-31b-it 等免費模型 | Gemini API 免費 key |
| 阿里雲 Model Studio（免費） | Qwen 免費模型 | 國際站 key（需先開通模型） |
| OpenRouter :free | 翻譯最強免費模型群 | OpenRouter 免費 key |
| DeepSeek | 純文字翻譯，**機密文件專用** | DeepSeek 付費 key |
| OpenAI | GPT 系列付費翻譯 | OpenAI 付費 key |
| Google Gemini Pro | Gemini 付費模型 | Gemini 付費 key |
| BabelDOC | 版面重排（公式保真） | ✅（DeepSeek key 亦可） |
| LaTeX | .tex 源碼路線，最省 token | ✅（DeepSeek key 亦可） |

---

## ✨ 功能一覽

- **主頁就地選引擎**：引擎卡片＋目標語言就地選——免費引擎集中在「免費區」優先展示
- **LaTeX 源碼路線**：上傳 `.tex` 自動鎖定 LaTeX 引擎——公式指令原封、編譯重排（**前置需求見下**）
- **雙輸出**：每筆任務產 mono（僅譯文）＋dual（雙語對照），卡片與歷史表格皆可下載
- **歷史管理**：表格化＋分頁＋勾選全選＋批量刪除（二次確認）＋批量下載 mono/dual zip
- **機密模式**：勾選 🔒 後引擎自動切 DeepSeek、視覺模型灰化（R18／隱私文件不上視覺模型）
- **掃描件 OCR**：本機 RapidOCR 預處理（onnxruntime）——**不上雲，機密相容**
- **成本可見**：估算→實際成本＋tokens 用量；引擎單價可在設定頁調整
- **頁面範圍**：可只翻譯選中頁（未選頁原樣保留）
- **引擎模型挑選（v0.1.4 新增）**：設定頁引擎卡「🔄 載入模型清單」即時拉取該 API 最新模型下拉挑選（可自訂輸入）＋「儲存模型」——官方模型下線（EOL）不用等更新
- **NVIDIA NIM 節流（v0.1.3 新增，v0.1.4 修正）**：免費層 40 RPM——已內建節流（每秒 1 請求上限＋單線程不併發），避免 429/503
- **翻譯超時常駐修復（v0.1.5）**：NIM 大型模型單頁生成慢（可達數百秒）——超時判定改以「無輸出閒置」為準（NIM 900 秒兜底），不再誤殺正常翻譯；log 即時輸出（unbuffered）
- **狀態列 log（v0.1.5 新增）**：Terminal 即時顯示人類可讀狀態列（進度、時間戳本地時區）
- **假成功杜絕（v0.1.6 新增）**：翻譯前**自動預檢**（驗證 key＋模型可生成，零成本）、錯誤即時診斷——不再出現「顯示成功但沒產出 PDF」
- **國際站全支援（v0.1.6/0.1.7）**：所有引擎皆為國際站端點——申請到的 key 即可用
- **「測試 API」更可靠（v0.1.6）**：實際生成一次（零成本）確認模型可翻譯
- **空殼模型診斷（v0.1.8 新增）**：HTTP 200 但 choices 為空 → 即時回報「模型未提供服務」
- **術語庫擴充（v0.1.9 新增）**：設定頁「匯入樂詞網詞表」——**naer-core**（國家教育研究院樂詞網學術名詞 3 萬條單詞層；政府資料開放授權條款第 1 版、繁體中文官方品質）一鍵匯入；大詞表編輯頁自動截斷顯示不卡 UI
- ⚠️ **google／bing 不支援術語表**：勾選術語表＋google/bing 會被擋下並提示改付費引擎、siliconflowfree 或取消勾選——其餘引擎（SiliconFlow／DeepSeek／OpenAI 相容／siliconflowfree）皆支援
- 📖 **詞表格式**：兩欄 `source,target` 為語言中性（任何目標語言都生效，本 App 匯入即此格式）；若 CSV 含 `tgt_lng` 欄位，語言與任務目標不符的列會被整表跳過（匯入 0 條時會警示）——外部下載的三欄詞表若匯入顯示「0 條」，刪除 tgt_lng 欄位即可
- **「📂 瀏覽資料夾」用 Finder 開啟**（open 指令）

---

## 📌 進階路線前置需求（非預設功能）

核心翻譯（PDF 路線＋SiliconFlow／DeepSeek 引擎）開箱即用。以下兩條路線需要額外工具：

### LaTeX 路線（.tex 翻譯）

需要 **MiKTeX**（內含 xelatex，中文支援）：
1. 安裝 MiKTeX：https://miktex.org/download（macOS 版）
2. 安裝時或首次使用時接受套件自動安裝
3. 重新啟動 Paper_Kit 即可

### BabelDOC 路線（版面重排）

**v0.1.1 起 uv 自動安裝**（不再需要手動裝）：
1. 首次選用 BabelDOC 時，程式**自動下載 uv 工具**到應用程式專屬資料夾（不需管理員權限、不修改您的 PATH）
2. 接著自動下載 babeldoc CLI（需連網，首次等待較久——引擎本體數百 MB）

---

## 💾 資料位置（v0.1.2 起：資料跟程式走）

| 內容 | 位置 |
|---|---|
| 設定（API keys）、任務歷史 | `data/paper_kit.db`（程式資料夾內） |
| 輸出翻譯 PDF | `data/outputs/` |
| 術語表庫 | `data/glossaries/` |
| 翻譯快取 | `data/cache/` |
| 除錯 log | `data/logs/` |
| 自動安裝的 uv 工具 | `data/bin/` |

> **換新版**：解壓新版本後，把舊版本資料夾裡的 `data` 整個複製到新資料夾，
> 歷史與設定（API keys）就會帶過去。不複製＝全新開始（零殘留）。

---

## 🧹 完整移除（v0.1.2 新增）

**刪除整個程式資料夾即完成卸載**——`data` 在程式資料夾內，刪掉資料夾 =
任務歷史、設定、API keys、輸出全部清除，**系統零殘留**。

1. 先在 Terminal 按 `Ctrl+C` 停止程式（若正在執行）
2. 刪除整個 `paper-kit-v0.1.9.1` 資料夾（拖到「垃圾桶」）
3. 完成

> 可選：只想清資料、保留程式——Terminal 執行 `./paper-kit-v0.1.9.1 --uninstall`
> （`data` 即被清空）。

---

## ❓ 常見問題

- **Gatekeeper 警告／無法開啟？**：見上方「macOS 疑難排解」——右鍵開啟或
  `xattr -dr com.apple.quarantine` 整包移除（v0.1.8 實測的 `library load
  disallowed` 就是只移主執行檔造成的）
- **8080 埠被佔用？**：`lsof -nP -iTCP:8080 -sTCP:LISTEN` 找佔用者——v0.1.9.1
  起被佔用時會明確報錯退出（不再有「ready 假象」）
- **翻譯品質**：免費引擎（google/bing/siliconflowfree）限流且品質較低——正式
  使用請用 SiliconFlow、DeepSeek 或免費品質引擎（ModelScope/Z.AI/NIM）
- **「系統缺少 uv 工具且自動下載失敗」**：表示離線或 GitHub 無法連線——連網後
  重試翻譯即可
- **換新版後沒看到歷史紀錄/設定？**：資料跟程式走——把舊版本資料夾的 `data`
  複製到新資料夾即可帶過去（見「💾 資料位置」）
- **翻譯報「模型不存在／限流／key 無效」？**：v0.1.6 起翻譯前自動預檢＋錯誤
  即時診斷——依訊息換模型、稍後重試或檢查 key
- **翻譯報「模型未提供服務」？**：該模型登錄但未開放給您（或為思考型、回應
  異常）——換模型（設定頁「🔄 載入模型清單」挑選可生成者）或換引擎
- **NIM 大型模型翻譯很久？**：120B 單頁可達數分鐘——屬正常（免費旗艦的品質
  代價），v0.1.5 起不會誤報超時；等待即可

---

## 🔒 隱私

- 上傳即代表同意：檔案內容將送**您填寫的引擎 API** 翻譯
- 機密文件（R18／隱私）請勾選 🔒——僅 DeepSeek 純文字引擎可處理、不上視覺模型
- 掃描件 OCR 全程本機執行（RapidOCR），**不上雲**
- 免費引擎檔案送雲端（ModelScope/Z.AI/NIM/Groq 等）——機密文件用付費 DeepSeek

---

Paper_Kit v0.1.9.1（macOS 版，2026-08-14）
