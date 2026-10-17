# ADR 0012：候選 3 只搬三個 `UI_*` tuple

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q12）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

引擎呈現（排序、標籤）混在 infrastructure。

## 決策

只把三個 `UI_*` tuple 搬到 `presentation/engine_cards`。

## 替代方案與否決理由

把 `EngineSpec` 硬拆成多層：真正的問題是依賴方向，不是檔案數量；硬拆收益是理論上的。

## 後果

UI 排序移出 infrastructure。commit `9fe930a`。
