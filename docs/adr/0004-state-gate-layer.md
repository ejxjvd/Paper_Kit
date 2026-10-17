# ADR 0004：任務狀態守門人放在 application 層

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q4）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

狀態轉換與持久化可被拆開呼叫，並行時出現「排隊中」卡死（故障二）。

## 決策

`application/job_state.JobStateGate`：轉換與持久化不可拆，鎖不外借。

## 替代方案與否決理由

放 domain：會沾上 IO。放 infrastructure：並行不變式會藏起來，呼叫方仍可繞過。

## 後果

故障二在新 interface 下**寫不出來**。commit `a1b70a8`。
