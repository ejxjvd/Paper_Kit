# 冒煙 / e2e 腳本（scripts/smoke/）

2026-08-13 由 Temp 收編入 repo（夜間批次決策：真實驗收資產不該躺在 Temp）。

## ⚠️ 真實 API 成本警告

`smoke-v3.sh`／`smoke-cdp.sh`／`e2e_web_test2.py`／`e2e-web-run.py` 走**真實引擎＋真實 API key**（`~/.paper_kit/paper_kit.db` 設定）——每次執行消耗真實費用＋操作真實 DB（自動術語提取開關會暫動並還原）。**CI 或陌生人環境勿跑**；本機驗收才用。

## 分層

| 腳本 | 層級 | 內容 |
|---|---|---|
| `smoke-ui.sh` | 最輕 | curl 四頁（/ /settings /history /debug）回 http code |
| `smoke.sh`（../smoke.sh，票 18 舊版） | 輕 | 起 app＋curl 四頁＋zip 路由＋清 process |
| `smoke-v3.sh` | 重（真實 API） | Playwright headless chromium 最嚴苛冒煙：主頁→設定頁（auto_extract 開關一致性＋暫開）→真實上傳 paper_p34.pdf→開始翻譯→輪詢 DB 至終態→mono/dual 非空＋glossary.csv 產出＋Token 有值→UI 無 450/401＋無 pageerror→auto_extract 還原。**14/14 全過版本（2026-08-13 實測）** |
| `smoke-cdp.sh` | 重（真實 API） | 同上但經 Windows Chrome CDP（--remote-debugging-port=9222）跑 headless——WSL chromium libs 失效時的替代路徑 |
| `e2e_web_test2.py` | 重（真實 API） | pytest 版（user_simulation＋真實引擎）：狀態變化才印＋每 15s 印子程序樹＋逾時 dump job 全欄位 |
| `e2e-web-run.py` | 重（真實 API） | 同上一段程式（非 pytest）：上傳→等 COMPLETED→驗證輸出 PDF |
| `e2e-download.sh` | 前置 | 下載 arXiv 測試 PDF 到 /tmp/paperkit-e2e/（e2e 系前置） |
| `check-e2e.sh` | 診斷 | 檢查 pdf2zh/babeldoc 子程序＋輸出樹 |

## 前置

- app 在 http://localhost:8080 執行中（`uv run paper-kit`）
- **smoke-v3.sh**：WSL 側 headless chromium libs 已解壓至 `/tmp/deps`（`LD_LIBRARY_PATH=/tmp/deps/...` 在腳本內寫死——重裝 WSL 後需重建，非持久解法；失效時改用 smoke-cdp.sh）
- e2e 系：先跑 `e2e-download.sh`；`REAL_DB`/`PDF`/`OUT` 常量依環境調整（腳本內 `Path(...)` 直接改）

## 常用指令

```bash
# 輕量四頁冒煙（app 已起）
bash scripts/smoke/smoke-ui.sh

# 最嚴苛冒煙（Playwright＋真實 API，~5 分鐘）
bash scripts/smoke/smoke-v3.sh

# e2e pytest 版
bash scripts/smoke/e2e-download.sh
.venv/bin/python -m pytest scripts/smoke/e2e_web_test2.py -s 2>&1 | tee /tmp/paperkit-e2e/e2e-run2.log
```

## 決策紀錄

- **收編**：2026-08-13 夜間批次——真實驗收資產（冒煙三版歷程＋e2e）不躺在 Temp；`run-e2e2/3.sh` 包裝器不入（Temp 路徑寫死，README 指令替代）；`e2e-equiv/`（C# 等價性實驗產物）不入 repo。
- **WSL chromium libs 非持久**：`/tmp/deps` 手工解壓解法重裝即失效——已由 smoke-cdp.sh（Windows Chrome CDP）補位。
