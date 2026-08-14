---
title: Groq API 速率限制查證（2026-08-14）
date: 2026-08-14
tags: [groq, api, rate-limits, research, paper-kit]
---

# Groq API 速率限制查證（2026-08-14）

> 查證目的：Paper_Kit 用 Groq 免費 API key 翻譯，registry 中 `openai/gpt-oss-120b` 的
> card_desc 寫「30 RPM、14,400 RPD」，需以官方文件徹底查證。
> 方法：直接讀取官方文件（rendered 頁面 HTML + raw Markdown + 頁面內嵌 JSON 資料），
> 並以搜尋結果交叉驗證。**所有數字皆直接取自官方頁面**，非轉述。

## 結論摘要

1. **card_desc「30 RPM、14,400 RPD」對 `openai/gpt-oss-120b` 是錯的**——30 RPM 正確，
   但 14.4K RPD 是 `llama-3.1-8b-instant` 的免費層數值；`openai/gpt-oss-120b` 免費層實為
   **30 RPM、1K RPD、8K TPM、200K TPD**（官方文件原表）。
2. 免費層與 Developer（付費）層差異巨大：gpt-oss-120b 付費層為 **1K RPM、500K RPD、
   250K TPM、每日 token 無上限**（免費層約 33 倍 RPM、500 倍 RPD）。
3. 速率限制**以組織（organization）為單位**，非 API key——多建 key 不會增加配額
   （官方明文）。
4. 「免費層每週 rolling 60 分鐘推理時間」政策**查無任何官方出處**（含歷史搜尋），
   現行官方文件純以 RPM/RPD/TPM/TPD（+音訊 ASH/ASD）計量，無時間型上限。
5. 429 退避：官方僅規定 429 回應與 `retry-after`（秒）標頭；退避演算法官方未規定，
   第三方共識為指數退避（1s→2s→4s，上限 60s）。

## 免費層 vs Developer 付費層：重點模型對照表

資料來源：[console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits)
（2026-08-14 直接讀取；頁面含 Free Plan / Developer Plan 兩分頁，兩表資料皆內嵌於頁面
JSON，本次已完整取出；官方並註明「表列為 Developer plan 基本額度，特定工作負載與企業
可取得更高額度」）。

| 模型 | 層級 | RPM | RPD | TPM | TPD |
|---|---|---|---|---|---|
| **openai/gpt-oss-120b** | 免費 | **30** | **1K** | **8K** | **200K** |
| | Developer | 1K | 500K | 250K | 無上限（無 TPD 欄位值） |
| openai/gpt-oss-20b | 免費 | 30 | 1K | 8K | 200K |
| | Developer | 1K | 500K | 250K | – |
| openai/gpt-oss-safeguard-20b | 免費 | 30 | 1K | 8K | 200K |
| | Developer | 1K | 500K | 150K | – |
| llama-3.3-70b-versatile | 免費 | 30 | 1K | 12K | 100K |
| | Developer | 1K | 500K | 300K | – |
| qwen/qwen3.6-27b | 免費 | 30 | 1K | 8K | 200K |
| | Developer | 1K | 500K | 250K | – |
| llama-3.1-8b-instant | 免費 | 30 | **14.4K** | 6K | 500K |
| | Developer | 1K | 500K | 250K | – |

（「–」= 官方未列該欄數值；Developer 層所有模型均無 TPD 數值＝每日 token 不設上限。
另：免費層所有模型皆無 ITPM/OTPM 分離欄；部分組織帳號才會有 input/output 分離限速。）

## 免費層完整表（官方原表逐行）

來源：[console.groq.com/docs/rate-limits](https://console.groq.com/docs/rate-limits)
（Free Plan 分頁；「–」為官方未列）。

| MODEL ID | RPM | RPD | TPM | TPD | ASH | ASD |
|---|---|---|---|---|---|---|
| canopylabs/orpheus-arabic-saudi | 10 | 100 | 1.2K | 3.6K | – | – |
| canopylabs/orpheus-v1-english | 10 | 100 | 1.2K | 3.6K | – | – |
| groq/compound | 30 | 250 | 70K | – | – | – |
| groq/compound-mini | 30 | 250 | 70K | – | – | – |
| llama-3.1-8b-instant | 30 | 14.4K | 6K | 500K | – | – |
| llama-3.3-70b-versatile | 30 | 1K | 12K | 100K | – | – |
| meta-llama/llama-prompt-guard-2-22m | 30 | 14.4K | 15K | 500K | – | – |
| meta-llama/llama-prompt-guard-2-86m | 30 | 14.4K | 15K | 500K | – | – |
| openai/gpt-oss-120b | 30 | 1K | 8K | 200K | – | – |
| openai/gpt-oss-20b | 30 | 1K | 8K | 200K | – | – |
| openai/gpt-oss-safeguard-20b | 30 | 1K | 8K | 200K | – | – |
| qwen/qwen3.6-27b | 30 | 1K | 8K | 200K | – | – |
| whisper-large-v3 | 20 | 2K | – | – | 7.2K | 28.8K |
| whisper-large-v3-turbo | 20 | 2K | – | – | 7.2K | 28.8K |

## Developer 付費層完整表（官方頁面內嵌資料，逐行）

來源同上（Developer Plan 分頁資料；官方註明「表列為 base limits，特定工作負載與企業
可申請更高」）。

| MODEL ID | RPM | RPD | TPM | TPD | ASH | ASD |
|---|---|---|---|---|---|---|
| canopylabs/orpheus-arabic-saudi | 250 | 100K | 50K | – | – | – |
| canopylabs/orpheus-v1-english | 250 | 100K | 50K | – | – | – |
| groq/compound | 200 | 20K | 200K | – | – | – |
| groq/compound-mini | 200 | 20K | 200K | – | – | – |
| llama-3.1-8b-instant | 1K | 500K | 250K | – | – | – |
| llama-3.3-70b-versatile | 1K | 500K | 300K | – | – | – |
| meta-llama/llama-prompt-guard-2-22m | 100 | 50K | 30K | – | – | – |
| meta-llama/llama-prompt-guard-2-86m | 100 | 50K | 30K | – | – | – |
| openai/gpt-oss-120b | 1K | 500K | 250K | – | – | – |
| openai/gpt-oss-20b | 1K | 500K | 250K | – | – | – |
| openai/gpt-oss-safeguard-20b | 1K | 500K | 150K | – | – | – |
| qwen/qwen3.6-27b | 1K | 500K | 250K | – | – | – |
| whisper-large-v3 | 300 | 200K | – | – | 200K | 4M |
| whisper-large-v3-turbo | 400 | 200K | – | – | 400K | 4M |

交叉驗證：[console.groq.com/docs/models.md](https://console.groq.com/docs/models.md)
（models 頁）Production 模型標示的開發者層額度（gpt-oss-120b：1K RPM / 250K TPM；
llama-3.3-70b：1K RPM / 300K TPM）與上表完全一致。

## 免費層模型白名單

- **官方未刊登明確白名單/黑名單**。rate-limits 頁僅為上表 14 個模型刊出免費層數值；
  models 頁（[console.groq.com/docs/models](https://console.groq.com/docs/models)）
  分類為 Production / Preview / Deprecated 三類，未標明免費層可用性；唯一明確限縮的是
  `minimaxai/minimax-m2.7`（標 Enterprise、價額與額度皆「Contact Sales」）。
- 實務判準：**rate-limits 頁表內刊有免費層數值的模型＝免費層可用**；表外模型（如
  `moonshotai/kimi-k2-instruct`、`qwen/qwen3-32b`、`meta-llama/llama-4-maverick-*` 等仍
  存在於 API 目錄）未刊免費層額度。第三方（FreeRideV3 provider survey）亦證實模型目錄
  不顯示 plan 可用性、免費層可用名單須以 rate-limits 頁為準做 hardcode allowlist。
  此點官方未明文，判定**「以官方 rate-limits 表為準」**。

## 速率限制單位：組織（非 API key）

官方明文（[rate-limits 文件](https://console.groq.com/docs/rate-limits)）：
「Rate limits apply at the organization level, not individual users.」——
以組織為單位，建立多支 API key 不會提高配額。

其他官方規定：
- 快取 token（prompt caching）不計入限額。
- 觸及任一額度（RPM/RPD/TPM/TPD/ITPM/OTPM…）即被限流，取先到者。
- 部分組織另有 ITPM/OTPM 分離額度（帳號 Limits 頁的 TPM 值可懸停看「X in / Y out」）。

## 「60 分鐘推理時間」政策現況

- **2026-08 現行官方文件無任何時間型（分鐘/小時）推理上限**——全部以 RPM/RPD/TPM/TPD
  計量（rate-limits 頁全文 81 行內無「minute of inference」或時間額度字樣）。
- 多方搜尋（含歷史政策、2024/2025 變革、FAQ 存檔）**查無「weekly rolling 60 minutes」
  的任何官方或可引用出處**，亦無 2026 年第三方來源記載——判定此說法為過時或誤傳，
  現行免費層為純 token/request 計量。
- 現行官方文件之外的補充：第三方課程文件（The Neural Base，引官方 Limits 頁）稱免費層
  另有**每月 token 預算（約 12M tokens/月，曆月重置，非 rolling 30 天）**；官方 rate-limits
  文件未刊登此數字，僅在帳號 Limits 頁顯示——此點以「第三方轉述」標記，未列入主表。
  另第三方（TokenMix）稱免費層請求於尖峰時段會被降優先權處理。

## 429 錯誤與退避建議

- 官方（[rate-limits 文件](https://console.groq.com/docs/rate-limits)）：
  - 超過額度時 API 回 `429 Too Many Requests`。
  - **`retry-after` 僅在 429 時附上**（單位秒）；其餘 `x-ratelimit-*` 標頭恆在：
    `x-ratelimit-limit-requests` = RPD、`x-ratelimit-limit-tokens` = TPM、
    `x-ratelimit-remaining-*`、`x-ratelimit-reset-*`（格式如 `2m59.56s`）。
  - 官方未規定退避演算法。
- 官方 [errors 文件](https://console.groq.com/docs/errors)對 429 的建議僅一句：
  「Implement request throttling and respect rate limits.」
- 第三方共識（Tickerr、TokenMix 等）：429 時以指數退避重試（1s→2s→4s，上限 60s），
  並以 `x-ratelimit-remaining-*` 標頭控制節奏。**此為第三方建議，非官方規定。**

## 附帶發現（對 Paper_Kit 有用）

- gpt-oss-120b 免費層 TPM 僅 8K——翻譯長 PDF 時每分鐘 token 很快見底；
  30 RPM 之下單篇大文件可拆多請求分批送。
- 若付費升級 Developer 層（需綁信用卡，按量計費）：gpt-oss-120b 額度 1K RPM /
  500K RPD / 250K TPM，另可解鎖 **Batch API**（gpt-oss-120b 支援，50% 折扣，批次限額
  與同步 API 獨立，不佔一般額度）與 Flex 處理。
- cached tokens 不計額度→對重複文字段落使用 prompt caching 可降低 TPM 消耗。

## 來源清單

1. [Groq Docs — Rate Limits（官方，直接讀取）](https://console.groq.com/docs/rate-limits)
   ——本文所有額度數值（Free/Developer 兩分頁）與 429/標頭規定之唯一依據；另以
   `https://console.groq.com/docs/rate-limits.md`（raw Markdown）與頁面內嵌 JSON
   （freeRows/devRows 兩組陣列）交叉驗證，數字一致。
2. [Groq Docs — Models（官方）](https://console.groq.com/docs/models) —— Production/
   Preview/Deprecated 分類、(DEVELOPER PLAN) 額度欄（與 1 交叉驗證一致）、
   minimax-m2.7 Enterprise 限縮。
3. [Groq Docs — Errors（官方）](https://console.groq.com/docs/errors) —— 429 官方建議。
4. [Groq Docs — Batch（官方）](https://console.groq.com/docs/batch) —— Batch 獨立額度、
   gpt-oss-120b 支援、50% 折扣。
5. The Neural Base — Groq Beginner/Intermediate Course（第三方，引官方 Limits 頁）：
   [rate-limits-tpm-and-rpm](https://theneuralbase.com/groq/learn/beginner/rate-limits-tpm-and-rpm/)、
   [free-tier-vs-paid-tier-limits](https://theneuralbase.com/groq/learn/intermediate/free-tier-vs-paid-tier-limits/)
   —— 每月 token 預算（~12M/月、曆月重置）、rolling window 機制（第三方轉述）。
6. Tickerr — [Groq limits](https://tickerr.ai/limits/groq)（第三方限額追蹤）—— 30 RPM/
   6K TPM/14.4K RPD 舊制摘要、並發 5、退避建議（第三方轉述）。
7. Dmytro Klymentiev — [Groq API Pricing & Free Tier Rate Limits 2026](https://klymentiev.com/blog/groq-pricing)
   （第三方）—— Developer 升級 ≈10 倍額度、Batch 折扣。
8. FreeRideV3 provider survey（[GitHub](https://github.com/Shaivpidadi/FreeRideV3/blob/main/docs/providers/SURVEY.md)，
   第三方）—— 模型目錄不顯示 plan 可用性，免費名單須以 rate-limits 頁 hardcode。
9. TokenMix — [Groq API Tutorial 2026](https://tokenmix.ai/blog/groq-api-tutorial-getting-started)
   （第三方）—— 免費層尖峰降優先、退避 1s→2s→4s 建議。

> 備註：來源 5–9 僅用於補充官方未刊登之處（每月 token 預算、退避慣例、白名單實務）；
> 所有 RPM/RPD/TPM/TPD 主表數字均以來源 1（官方）為準。搜尋到的若干第三方頁面
> （pricepertoken.com 等）回 403/429 無法直接讀取，未採用；另有第三方稱免費層全模型
> 「14,400 RPD」與官方逐模型表（gpt-oss 系列 1K RPD）衝突——以官方逐模型表為準。
