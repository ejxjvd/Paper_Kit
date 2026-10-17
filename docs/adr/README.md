# 架構決策紀錄（ADR）

> 2026-08-19 架構審查的最終裁決，逐條落成文件。決策過程（候選、兩輪 grilling、
> 被推翻的判斷）見 `Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`；
> 本目錄只記錄**結論與理由**，是日後「為什麼這樣寫」的查詢入口。

## 索引

| 編號 | 決策 | 一句話 |
|---|---|---|
| [0001](0001-subprocess-core.md) | 共用子程序核心，保留兩種等待語意 | `spawn()` 單一啟動點；`stream()`／`collect()` 兩種等待 |
| [0002](0002-runner-signature.md) | 保留 `runner=` 注入簽名 | 既有 30 處 FakeRunner 測試零改動 |
| [0003](0003-real-subprocess-ci.md) | 真實子程序測試進 CI | 全平台跑，不標 slow |
| [0004](0004-state-gate-layer.md) | 狀態守門人放 application | `JobStateGate`：轉換與持久化不可拆 |
| [0005](0005-rejection-by-return.md) | 「拒絕」用回傳值 | 例外只留給真異常 |
| [0006](0006-release-cadence.md) | 逐個提交、單次發 0.2.0 | 可單獨回退，版本號不灌水 |
| [0007](0007-uv-stays-in-adapter.md) | uv 解析留在 adapter | 核心不認得 `"uv"` |
| [0008](0008-handle-ownership.md) | 核心回傳 handle | 子程序所有權歸呼叫方 |
| [0009](0009-gate-scope-internalized.md) | 守門人管轄全部內化 | 轉換／取消／刪除／進度四者皆然 |
| [0010](0010-job-and-warnings.md) | 結果帶 job 與 warnings | 警告是領域判斷，不是 UI 判斷 |
| [0011](0011-job-intake-side-effects.md) | 任務建立含完整副作用 | 十條規則搬出 UI |
| [0012](0012-engine-cards-scope.md) | 候選 3 只搬三個 `UI_*` tuple | 修依賴方向，不為拆而拆 |
| [0013](0013-progress-artifact-first.md) | 頁面級進度先留檔 | 沒有真實樣本前不寫解析器 |

## 撰寫規則（新增 ADR 時）

- 檔名 `NNNN-kebab-slug.md`，編號連續、不重用。
- 每篇必含：背景／決策／替代方案與否決理由／後果。
- 決策一旦被推翻，**不刪原檔**：狀態改「已被 ADR-NNNN 取代」並互連。
- 這份索引與每篇 ADR 同步更新；漏更新索引等於決策不可查。
