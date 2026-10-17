# ADR 0011：任務建立包含完整副作用

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q11）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

建任務→掛術語表→估價→啟動的順序原本留在 UI（`app.py`）。

## 決策

搬進 `application/job_intake`，含完整副作用。

## 替代方案與否決理由

只做純決策：順序仍留在 UI，換個包裝的同一個問題。

## 後果

十條規則搬出 UI；`app.py` −106 行；新增 9 個直接測試。commit `6035170`。
