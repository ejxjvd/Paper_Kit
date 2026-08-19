# Paper_Kit Release Notes

> CI 建 Release 時依 tag 提取對應區段作為 notes（見 `.github/workflows/release.yml`）。

## v0.1.9.7

### 🐛 修復：翻譯失敗「depends on pydantic … which depends on pydantic-core」

**背景（2026-08-19 使用者個人筆電實測 0.1.9.6）**：任務 `ecb42f3b`（Google 免費引擎）
建立後約 84 秒失敗，訊息只有殘缺的一句：

```
引擎執行失敗：        depends on pydantic (v2.11.10) which depends on pydantic-core
```

**根因（本機重現確認）**：`uv tool run pdf2zh_next` **未指定 `--python`**，uv 因此
挑用機器上最新的直譯器。以 Python 3.14 重現，完整錯誤是：

```
Python reports SOABI: cp314-win_amd64
   Building pydantic-core==2.33.2
  × Failed to build `pydantic-core==2.33.2`
  ╰─▶ Call to `maturin.build_wheel` failed (exit code: 1)
      Rust not found, installing into a temporary directory
```

`pydantic-core` 無 cp314 預編譯輪子 → uv 退回**從原始碼編譯** → 拉 Rust 工具鏈
（它甚至自動下載 rustup）→ 編譯失敗於：

```
error: the configured Python interpreter version (3.14) is newer than
       PyO3's maximum supported version (3.13)   [pyo3 0.24.1]
```

**關鍵**：這不是「輪子還沒跟上」的暫時現象。`pydantic-core 2.33.2` 內含的 PyO3 0.24.1
有 3.13 **硬上限**——那台機器上就算裝了完整 Rust 工具鏈也不可能編譯成功。要等
pdf2zh_next 整條相依鏈升級才會解，無法從我們這端修，只能避開。

這是**版本漂移型故障**：開發機（3.12）永遠正常，只有裝了新 Python 的使用者機器會炸，
而且 Python 每出一個新版就會再犯一次。

**修法**：

1. `pdf2zh_next` 與 `babeldoc` 的命令都插入 `--python 3.12`（常數 `ENGINE_PYTHON`
   單一真相，與 `.python-version`／`requires-python` 對齊）
2. 新增已知錯誤對映：萬一再現，訊息直說「相依套件需要從原始碼編譯」而非讓使用者猜

### 🐛 修復：多行錯誤只顯示最沒用的那一行

`_friendly_error` 取的是輸出的**最後一行**（`lines[-1]`）。uv 的錯誤是一棵樹——
真正的原因在開頭（`× No solution found`），結尾只是縮排的續行殘片。於是使用者拿到
的診斷剛好是整段訊息裡資訊量最低的部分。

**修法**：改為優先回報第一個帶錯誤標記（`×`／`╰─▶`／`No solution found`／
`Failed to build`／`error:`）的行；找不到才退回舊行為。

### 🔍 改善：引擎完整輸出進 log

先前引擎的 stdout **從未被記錄**，只有 `_friendly_error` 抽出的一行進 log。這正是
上面那個 bug 難診斷的原因——完整的錯誤樹當場就被丟棄了。

**修法**：任務結束時記一次完整引擎輸出（成功走 INFO、失敗走 ERROR，皆經 key 遮罩，
單筆上限 8000 字、保頭保尾）。翻譯以分鐘計，一任務一筆不會洗版。

順帶解除一個長期阻塞：頁面級進度（「翻譯到第 N 頁」）之所以遲遲沒做，是因為拿不到
引擎真實的進度輸出格式。現在跑一次真實翻譯，log 裡就有完整樣本。

### ✅ 驗證

- 4 個新迴歸測試：兩支引擎的 `--python` 釘定（含旗標位置必須在工具名之前）、
  多行錯誤回報根部而非續行、失敗 log 必帶 `engine_output`
- 兩個既有命令形狀測試同步更新（命令前綴確實改變，紅燈正確）
- 全套件 **793 passed**、零失敗
- 根因以 `uv tool run --python 3.14` 在本機實際重現，非推測
- **在原本失敗的那台使用者筆電上驗證修正**：`--python 3.14` → 編譯失敗（PyO3 上限）；
  `--python 3.12` → 133 套件 10.15s 安裝完成、`pdf2zh-next version: 2.9.0` 正常回應

## v0.1.9.6

### 🐛 修復：繁中 Windows 翻譯任務一啟動就崩潰（cp950 解碼）

**背景（2026-08-19 使用者實測，paper-kit-0.1.9.5-win-x64）**：三次任務
（`0daa2e5c`／`5eac47aa`／`093b6ba2`）建立後立即中斷，log 皆為同一形狀：

```
Exception in thread Thread-3 (read):
  File "paper_kit\infrastructure\cli_adapter_base.py", line 227, in read
UnicodeDecodeError: 'cp950' codec can't decode byte 0xc3 in position 2: illegal multibyte sequence
```

**根因**：`cli_adapter_base` 的 `Popen` 只給了 `text=True` 而未指定 `encoding`
→ Python 回退系統地區編碼，繁中 Windows 即 **cp950**；引擎（pdf2zh_next／
babeldoc）輸出是 UTF-8，讀到 `0xC3` 前導位元組即拋 `UnicodeDecodeError`。

- `0xC3` 在 UTF-8 是雙位元組前導（`C3 89` = `É`）。cp950 認得 `0xC3` 是合法
  Big5 前導，於是去要第二位元組——但 Big5 合法後續是 `0x40–0x7E`／`0xA1–0xFE`，
  而 UTF-8 續接位元組落在 `0x80–0xBF`，兩者在 `0x80–0xA0` 區間不相容 → 例外。
- **這是潛伏已久的 bug，不是 v0.1.9.5 新引入**——觸發與否取決於引擎輸出當下
  有沒有非 ASCII 字元，所以先前多數任務僥倖正常。
- **更該警覺的是靜默面**：若續接位元組剛好落在 `0xA1–0xFE`（如 `C3 A9` = `é`），
  cp950 會「成功」解碼成不相干的中文字——不拋例外，只產生亂碼 log，更難發現。

**真正的卡死點（比解碼錯誤本身更嚴重）**：例外殺死的是 reader thread，主迴圈的
`not reader.is_alive()` 會把它**誤判成 EOF** 而 break，接著 `proc.wait()` 無限等
——子程序寫滿 pipe 緩衝後阻塞在 write 永不退出，而 inactivity 看門狗此時已離開
迴圈救不了。使用者看到的是「任務沒反應」，不是錯誤訊息。

**修法**（讀寫兩端一起釘死，外加保險絲）：

1. `Popen` 明確指定 `encoding="utf-8", errors="replace"`——不吃地區設定；壞位元組
   退化成 U+FFFD 而非炸掉執行緒
2. 子程序環境補 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`——叫對方也寫 UTF-8
3. `read()` 就地接住例外並樹殺子程序 → `wait()` 立刻回來，rc≠0 走既有錯誤路徑：
   **吵著失敗，勝過靜默卡死**
4. `process_utils.run_command` 同一 bug 一併修正（LaTeX／PPT 引擎走這條，xelatex
   log 帶非 ASCII 時會直接炸掉整個編譯流程）

### 🐛 修復：翻譯全程只顯示「排隊中」，結束才跳「完成」

**背景（2026-08-19 使用者回報）**：翻譯進行中看不出任何進展，任務卡片整段時間
停在「排隊中」，直到翻完才直接變「完成」。

**根因**：`StartTranslation.run()` 的 `job.transition(TRANSLATING)` **只改記憶體
物件、沒有 save 回 repo**。而 UI 的 `list_jobs` 是從 repo（SQLite）讀的——那一列
整段翻譯期間都還是 `QUEUED`，直到終態才被寫入。

`#72` 當初刻意把「排隊中（不顯示進度條）」與「翻譯中（顯示進度）」設計成兩種
不同呈現；狀態不持久化，等於這個區分從未生效過。`_progress_writer` 的 save 也
救不了——它要等引擎回報進度才觸發，而 `_on_line` 目前是 no-op（見下）。

**修法**：transition 後立即 `save`（沿用 `_finalize()` 鎖，與其他終態轉換一致）。

**已知限制（尚未完成）**：頁面級進度（「翻譯到第 N 頁」）仍未實作。
`CliAdapterBase._on_line` 是 no-op 基線、無任何子類覆寫，引擎進度回調從未被觸發，
因此進度條在翻譯期間為 indeterminate（不確定進度）。要做確定值需先取得
pdf2zh_next／babeldoc 的真實 stdout 進度格式——目前 app 未將引擎輸出寫入 log，
無從取樣。下一版處理。

### ✅ 驗證

- 新增 3 個迴歸測試，**皆先驗證紅燈**（還原修正後必失敗）：
  - cp950 兩測：未修正版跑出的 traceback 與使用者實測 log 完全同形
    （`line 227, in read` → `for line in proc.stdout` → cp950 0xc3），確認測試
    真的重現了故障，而非只是斷言實作細節
  - 狀態持久化一測：斷言「引擎執行當下 repo 裡的狀態」而非 job 物件本身——
    記憶體物件是共用參考，測它永遠會過，測不到持久化這件事
- 全套件 **787 passed**（+3）
- **既有測試為何擋不住 cp950**：現有測試全部以 `FakeRunner`／`FakeProc` 注入，
  `stdout` 直接 yield `str`——解碼層從未被執行過。789 個測試全綠卻對這個 bug
  完全盲目。新測試改鎖 `Popen` kwargs 契約與 reader 死亡後的不死鎖行為
- 既有失敗 `test_app_entry.py::test_main_calls_freeze_support_first` 在乾淨的
  origin/main 上同樣為紅，與本次修改無關（未處理）

## v0.1.9.5

### ⚠️ 新增：LaTeX 數學密集 PDF 偵測＋行重疊風險標注

**背景（2026-08-15 診斷 0211159.pdf，Perelman《Ricci 流的熵公式》——39 頁 LaTeX 數學論文）**：使用者回報翻譯後格式錯誤、文字重疊。完整診斷結論：

- **不是 LaTeX 的錯**——原文排版完全正常（CMR12 字形 12pt、行距 14.4pt）
- **真因**：pdf2zh_next 底層 BabelDOC 引擎重排時把翻譯行距壓縮到 8.7–9.4pt，而翻譯中文用 Source Han Serif TW（字形 bbox 17.2pt 高）→ 行距 < 字形高度 → 行間視覺重疊（像素剖面實測：連續 18.7pt 墨跡無間隙，正常對照行間 7–8pt 空白）
- **公式參數 A/B 實測無效**：`--formular-font-pattern 'CMSY|CMEX|CMMI|CMR'` 與無參數版 CJK+CJK 重疊對完全同位（p12 三對、p32 三對）
- **mono 模式實測同樣無效**：mono 版同位置 6 對 CJK+CJK、像素剖面與 dual 一致
- 重疊分佈：使用者指定 5 頁（6/13/21/26/33）共 6–7 對 CJK+CJK 真重疊；另有大量 MATH+CJK 為 bbox 偽影（行間實有 5.5pt 空隙，gemma-31B 視覺複核讀成正常）

**v0.1.9.5 實作**（UI 標注方案——參數與 mono 都無效，改成誠實告知）：

1. 新模組 `latex_detector.py`：掃 PDF 全部頁字體清單（pymupdf），判別 LaTeX 字體系——Computer Modern／AMS（CMR/CMMI/CMSY/CMEX/LASY/MSBM…）＋Latin Modern（lmodern，LMRoman/LMMath）＋unicode-math 符號系（LatinModernMath/STIXTwoMath/XITSMath/TeXGyre*Math，含子集前綴 XXXX+ 剝離）——**公式符號字體存在＋LaTeX 頁面覆蓋率 ≥50%** → 判定「疑似 LaTeX 數學密集」
2. 任務卡片標注：翻譯完成的 LaTeX 密集 PDF 顯示 **「⚠️ 疑似 LaTeX 密集」** 徽章，tooltip 說明行重疊是引擎限制、公式參數與 mono 實測無效、建議以 dual 左半原文對照閱讀；tooltip 亦誠實註明判定侷限（XeLaTeX/CTeX 中文論文若完全不用 CM/LM 數學字體可能漏標）
3. 只偵測一次（memo 機制，1s 輪詢不重複掃 PDF）

**偵測的侷限（2026-08-15 使用者質詢後補強）**：字體名判定是啟發式、非保證。漏判面——XeLaTeX/CTeX 中文論文（CJK 字體不帶 CM 名，但公式通常仍是 CM 系符號字體→多數仍命中）、TeX Gyre 系正文（LibreOffice 也有散佈，不列入正文標誌防誤報）、無文字層掃描件（無法判定）。誤判防護——50% 覆蓋率閾值擋掉論文合集（296 頁僅 2-3 頁含 LaTeX 字體，實測 ALL-Agents PDF 正確不判）。

### ✅ 驗證

- TDD 11 新測試（字體判別含子集前綴／Latin Modern／unicode-math 符號系／fixture paper_p34.pdf 即 LaTeX 論文正例／掃描件反例／缺檔 None／50% 閾值純函式／viewmodel 透傳）——全套件 **789 passed**（+11）
- 真實大樣本掃描：使用者全部 PDF（29 檔）——0211159 系列 5 檔全命中 dense=True，OS_Chapter 系列／CH4／切結書／證明／說明書／SLAM 等全 False，296 頁合集正確拒絕
- A/B 驗證（診斷核心）：base vs `--formular-font-pattern` 5 頁重疊對完全一致（CJK+CJK 6 對同位）——參數無效定案

## v0.1.9.4

### 🐛 修復：打開 exe 的 CMD 看不到 uv 安裝進度（另一台 Windows 機器真機實測）

v0.1.9.3 發布後實測：CMD 視窗只有 `NiceGUI ready`，承諾的 uv 安裝進度一行都沒有。
兩個根因（皆真機/真 exe 驗證）：

1. **console log 卡在緩衝區**：`logging.StreamHandler` 寫 stdout 後**不 flush**——
   開發時 stdout 是 tty（line-buffered）恰好即時；PyInstaller frozen exe 的 stdout
   是 **block-buffered** → log 卡在緩衝、CMD 永遠看不到（**frozen exe 實測重現**：
   迷你 console exe 執行中讀不到 log 行，退出才吐出）。
2. **啟動時零 uv 狀態**：uv 動作只在**第一次翻譯時** lazy 觸發——打開 exe 時什麼
   都還沒發生，自然沒有進度可顯示。

### 🛠 修復內容

1. **FlushingConsoleHandler**：console handler 每次 emit 後立即 flush——
   frozen exe 的 CMD 逐行即時顯示（frozen exe 實測：執行中 0.5s 內即讀到
   log 行、DONE 前全部出現）
2. **啟動即 uv 狀態檢查**（`_uv_startup_status`）：exe 啟動時立即檢查——
   已找到 → 印位置；未找到 → **背景下載安裝**（不阻塞 UI ready），CMD
   即時顯示「uv 檢查：未找到——自動安裝中（4 源備援…）」＋後續進度/速度/
   完成/失敗重試
3. **並發防護**：`download_uv` 加執行緒鎖＋鎖內入口查——啟動背景安裝與
   翻譯時 resolve_uv 並發時不重複下載、不互踩

### ✅ 驗證

- TDD 4 新測試（flush 行為／鎖內入口查短路／啟動檢查已存在／缺時啟動背景安裝）
  ——全套件 **778 passed**（+4）
- **frozen exe 決定性驗證**（PyInstaller 迷你 console exe 實測）：執行中即時
  讀到「uv 檢查／嘗試 1/2／下載中 50%」三行 log——flush 修復在 frozen 環境成立
- 真實翻譯驗證（scripts/verify-translate.py）：google 免費引擎 23.1s 產出
  mono 464KB＋dual 455KB

## v0.1.9.3

### 🔧 修復：uv 自動下載在部分網路全滅（全新 Windows 機器真機實測）

v0.1.9.2 在無 uv 的全新 Windows 機器（使用者測試機）實測：Google 免費引擎任務
失敗「系統缺少 uv 工具（引擎中介）且自動下載失敗（離線?）」——機器有網但
**GitHub 域被擋**：自動下載只有 GitHub release 單一來源＝單點故障。

- 根因①：自動下載單一 GitHub 源——任何「GitHub 域被擋／慢／超時」的網路直接全滅
- 根因②：錯誤訊息「離線?」是猜測（實測機器有網），且手動備援給 POSIX 指令
  （`curl -LsSf … | sh`）——Windows PowerShell 實證 `sh : 無法將 'sh' 詞彙
  辨識為 Cmdlet`，使用者照做必卡

### 🛠 修復內容

1. **多源自動下載（4 源依序嘗試，任何一源可用即成功）**：GitHub 官方 release →
   PyPI 官方（uv 同發 wheel）→ 清華鏡像 → 阿里雲鏡像（PEP 503 簡單索引）；
   每源**自動重試 2 次**（瞬時網路問題可救回）
2. **安裝進度即時顯示**（使用者要求）：安裝中每 ~2 秒或每 8MB 輸出
   「下載中 X%（… MB，速度 Z MB/s）」＋來源/嘗試次數/完成/失敗 log——
   直接印在 exe 的 CMD 視窗
3. **失敗實因呈現**：錯誤訊息改帶各源失敗原因（取代「離線?」猜測），
   未知使用者照樣看得懂下一步
4. **平台正確的手動備援**：Windows 給 CMD／PowerShell 皆可執行的 3 條備援
   （`winget install astral-sh.uv`／官方 install.ps1／手動下載放 data\bin）；
   macOS 給 install.sh＋brew＋手動
5. **PyPI wheel 支援**：wheel 解壓（執行檔在 `.data/scripts/uv`）、
   非 Windows 補執行權限位、平台＋架構精準匹配（真網實測避免誤選 aarch64
   wheel 致 Exec format error）、鏡像相對 href 正確解析（urljoin）

### ✅ 驗證

- TDD：uv_bootstrap 測試擴充至 27 個（多源 fallback 順序、重試 2 次、
  進度 log、失敗實因、Windows／POSIX 備援指令文案）——全套件 **774 passed**
- 真網三源實測（`scripts/verify-uv-sources.py`，2026-08-15）：
  情境 A 全鏈 → uv 0.12.4、B 只留 PyPI → 0.12.4、C 只留清華鏡像 → 0.9.9，
  各產物 `uv --version` 可執行
- 真實翻譯驗證（`scripts/verify-translate.py`，驗證紀律）：google 免費引擎
  paper_p34.pdf 第 1 頁 **16.4s 產出 mono 464KB＋dual 455KB**（resolve_uv
  命中自動安裝產物）
- 驗證腳本化（使用者要求）：真翻譯／多源真網驗證收進 `scripts/` 可重用，
  鏡像存 Obsidian Vault

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
