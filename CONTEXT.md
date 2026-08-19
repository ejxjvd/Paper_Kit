# Paper_Kit 領域詞彙

這份文件定義 Paper_Kit 的**通用語言**（ubiquitous language）——程式碼、註解、commit
訊息、UI 文案、以及與 AI 代理對話時，都應該使用這裡的詞。

目的是讓「同一個概念只有一個名字」。看到不在這裡的新詞，要嘛補進來，要嘛改用既有的詞。

---

## 核心概念

### 任務（Job / `TranslationJob`）

一次翻譯請求的完整生命週期，是本系統的**聚合根**。使用者選一個檔案、按下翻譯，
就產生一個任務。任務持有翻譯所需的全部決定（引擎、頁碼、術語表、機密與否），
而且這些決定**在建立當下就凍結**——之後改設定不影響已建立的任務。

### 任務狀態（`JobStatus`）

五個狀態，轉換表是領域的單一真相（`domain/translation_job.py`）：

```
排隊中 ──→ 翻譯中 ──→ 完成
  │           ├──→ 失敗 ──→ 排隊中（重試）
  └──→ 失敗   └──→ 已取消
```

| 中文 | 識別字 | 說明 |
|------|--------|------|
| 排隊中 | `QUEUED` | 已建立、尚未開始。UI **不顯示進度條** |
| 翻譯中 | `TRANSLATING` | 引擎執行中。UI 顯示進度 |
| 完成 | `COMPLETED` | 終態 |
| 失敗 | `FAILED` | 可重試（回到排隊中） |
| 已取消 | `CANCELLED` | 終態 |

**「排隊中」與「翻譯中」是刻意區分的兩種呈現**，不是同義詞。
`can_retry` / `can_cancel` / `can_delete` 全部由轉換表推導，不另外寫規則。

> 排隊中 → 失敗 是合法的：應用重啟時，中斷的任務會被標為失敗。

### 引擎（Engine）

實際執行翻譯的外部程式或服務。共 16 支，UI 分成三個入口：

| 分組 | 說明 | 例 |
|------|------|-----|
| 主引擎 | 付費或本機，品質優先 | `siliconflow`、`deepseek`、`babeldoc`、`latex`、`openai`、`gemini-pro` |
| 免費翻譯 | 不需 API key | `siliconflowfree`、`google`、`bing` |
| 免費 LLM | 自備免費 key（BYOK） | `nvidia`、`zai`、`modelscope`、`groq`、`openrouter`、`dashscope`、`gemini` |

注意 `gemini-pro`（付費主引擎）與 `gemini`（免費 key 層）是**兩支不同的引擎**，別混用。

多數引擎透過 `uv tool run` 驅動 CLI（pdf2zh_next / babeldoc）；`latex` 與 `ppt_vision`
走各自的路徑。

### 產出（`JobResult`）

翻譯完成後的檔案與計量：

- **mono**（單語）：只有譯文的 PDF
- **dual**（雙語）：左原文右譯文對照的 PDF
- **用量**：`input_tokens` / `output_tokens`——引擎實際消耗，用來與估價比對

### 術語表（Glossary）

使用者維護的 source/target 對照 CSV，翻譯時傳給引擎以固定專有名詞譯法。
可多份併用。**自動提取**（`auto_extract`）指讓引擎自己抽術語，與手動術語表獨立。

### 機密文件（sensitive）

使用者標記為隱私／敏感的來源。這是一條**紅線**：機密文件只准走純文字引擎，
不得送往視覺（把頁面轉成圖片上傳）的引擎。

判定採 **fail-closed**——未知引擎一律視為「不允許機密」，不是放行。

### 掃描件與文字層（OCR）

沒有文字層的 PDF（整頁是圖）稱為**掃描件**。直接翻譯會產出空白，所以要先在**本機**
跑 OCR 補上隱形文字層再交給引擎。OCR 只適用 PDF。

### 頁面範圍

三個容易混淆的數字，務必分清楚：

| 中文 | 識別字 | 意義 |
|------|--------|------|
| 頁面範圍 | `pages` | 使用者輸入的字串，如 `"1-2,5"`；空白＝全文 |
| 翻譯頁數 | `total_pages` | 實際會翻幾頁（範圍展開後的數量） |
| PDF 總頁數 | `pdf_pages` | 原始 PDF 有幾頁 |

UI 上的「N/M 頁」＝`total_pages`/`pdf_pages`。

### 估價與用量

- **估價**（`CostEstimate`）：**建立任務前**依頁數與引擎定價推算的成本與 token 數
- **用量**：翻譯**完成後**引擎回報的實際 token 數

估價在建立時就隨任務凍結，因為完成後要比對的是「使用者當初看到的那個數字」。

### 快取

以來源檔內容加上翻譯決定算出**指紋**（fingerprint）；指紋相同就直接複用先前產出，
完全不呼叫引擎。命中的任務在 UI 標記為快取命中。

### LaTeX 密集

一種**品質警告**，不是引擎。偵測來源 PDF 是否大量使用 Computer Modern／Latin Modern
等 LaTeX 數學字體；是的話提醒使用者譯文可能行重疊（引擎限制，已實測無法用參數解決）。

判定是啟發式的，會漏判也可能誤判——文案必須誠實說明這點。

---

## 執行相關

### uv 中介

引擎 CLI 不預先安裝，而是透過 `uv tool run` 隨用隨跑。`uv` 本身若不存在會自動下載
（多來源備援）。使用者不需要手動安裝任何東西。

### 活性信號與 inactivity 逾時

判斷引擎是否卡死，**不看總時間**，看「最後一行輸出到現在多久」。
只要還有輸出行就續命——因為單頁翻譯可能合法地耗上數分鐘。總牆鐘只是最後保險。

### 樹殺（kill tree）

取消或逾時要殺掉的是**整棵子程序樹**，不只是 `uv` 這個中介行程——否則真正在跑的
引擎會變成孤兒繼續消耗 API 額度。

---

## 架構詞彙

描述程式碼結構時使用這組詞（取自 `/codebase-design`）：

- **module**：一個有明確職責的單元；理想是**深的**——窄 interface、厚實作
- **interface**：module 對外暴露的呼叫面。「interface 就是測試面」
- **seam**：兩個 module 之間可替換的接縫
- **adapter**：把外部系統包在我們的 interface 後面的 module
- **locality**：理解一件事所需的資訊是否集中在一處
- **deletion test**：刪掉這個 module，複雜度會**集中**還是只是**搬走**？集中才值得留

分層依賴方向：`presentation → application → domain`，`infrastructure` 實作
`application` 定義的 port。**presentation 不應該直接 import infrastructure**
（組裝進入點除外）。

---

## 深化後的 module

2026-08-19 架構審查後實作。這些名字是討論這個系統時的共同詞彙：

| 名稱 | 位置 | 職責 |
|------|------|------|
| 任務建立 | `application/job_intake` | 把使用者意圖變成一個已備妥的任務，或一個帶理由的拒絕。不知道 UI 存在 |
| 串流執行 | `infrastructure/subprocess_exec` | 唯一的子程序啟動點；`stream()` 逐行＋看門狗、`collect()` 跑完拿全部。以值為 interface，不靠繼承 |
| 任務狀態守門 | `application/job_state` | 狀態轉換與持久化是同一個不可拆的動作，鎖不外借 |
| 引擎卡片 | `presentation/engine_cards` | 主頁三個入口各顯示哪些引擎、什麼順序（純呈現決定） |
| 引擎目錄 | `infrastructure/engine_registry` | 引擎的身分與能力（id／provider／model／needs_key／sensitive_ok／定價） |

三條在重構中被寫進 interface 的規則，值得記住：

- **轉換狀態必然伴隨持久化**——UI 從 repo 輪詢，不持久化等於沒發生
- **拒絕是回傳值不是例外**——選錯引擎是預期結果；例外留給真正的異常
- **誰持有子程序，誰負責取消**——所有權含糊是死鎖的溫床
