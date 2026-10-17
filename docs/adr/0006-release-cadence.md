# ADR 0006：逐個提交、單次發布 0.2.0

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q6）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

四項架構深化會同時落地。

## 決策

每個改動各自 commit，可單獨回退；四個改動合併為單一 Release 0.2.0，release notes 說明重大修正事件與功能改動。

## 替代方案與否決理由

四個 Release：對使用者是零功能變化，不值得四次版本號。單一巨型 commit：無法單獨回退。

## 後果

四筆 commit 可獨立回退；Release 0.2.0 notes 記錄故障一至三。
