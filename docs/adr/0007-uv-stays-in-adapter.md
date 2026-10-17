# ADR 0007：uv 解析留在 adapter，不進執行核心

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q7）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

引擎多以 `uv tool run` 啟動。

## 決策

`uv` 屬引擎家族的部署細節，留在 adapter（`uv_bootstrap.engine_tool_run`）。

## 替代方案與否決理由

核心認得 `"uv"`：等於把 CLI 引擎知識漏進通用機制；xelatex／soffice 都不經過 uv。

## 後果

核心保持引擎無關；換引擎不改核心。
