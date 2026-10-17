# ADR 0001：共用子程序核心，保留兩種等待語意

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q1）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

兩套執行機制（CLI adapter 與 xelatex 呼叫）各自處理子程序，bug 有第二個棲息地。

## 決策

共用底層核心（`infrastructure/subprocess_exec`），但**保留兩種等待語意**：`stream()` 逐行串流、`collect()` 跑完取輸出。

## 替代方案與否決理由

全部統一成串流回調：xelatex 要的是「跑完給我輸出」，硬套串流只是噪音。維持現狀：等於留著 bug 的第二個棲息地。

## 後果

`cli_adapter_base` 淨減 90 行；新增 10 個真實子程序測試。commit `4e5ed12`。
