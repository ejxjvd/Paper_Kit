# 01 — 專案骨架＋domain 核心＋Port 契約

**What to build:** 專案的「地基切片」：Python 3.12 + uv 專案、pytest、NiceGUI 空殼；純邏輯領域（TranslationJob 狀態機、Glossary、CostCalculator）；`TranslationEnginePort` 契約與 FakeEngine 注入測試。這張完成時**測試全綠、無任何 IO 依賴的領域邏輯被完整鎖定**——後續所有切片都站在這上面。

**Blocked by:** None — can start immediately

**Status:** ✅ done（2026-08-12，commit 330fb09，44 測試全綠）

- [x] uv 專案初始化，`pytest` 全綠（紅→綠循環，先議接縫再寫測試）
- [x] TranslationJob 狀態機：`queued→translating→completed/failed/cancelled` 合法轉換表全測過；非法轉換（如 completed→queued）被拒絕
- [x] Glossary 值物件：CSV 標頭列驗證（缺 `source`/`target` 欄報明確錯誤）、tgt_lng 過濾、無 IO 純函式
- [x] CostCalculator 邊界測試：0 頁、1 頁、極大頁數、單價參數化
- [x] `TranslationEnginePort` 介面契約定義（translate(job)→job_result）
- [x] application 指令（StartTranslation 等）以 FakeEngine 注入測試：任務被正確送出、結果被正確存回
