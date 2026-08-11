# 09 — 錯誤處理與 log 追蹤

**What to build:** 故障可追蹤：統一錯誤 toast（領域錯誤→使用者看得懂的訊息）、結構化 log（時間／層級／元件／錯誤鏈）、debug 檢視頁——「DEBUG 方便好找」的專屬切片。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] 所有引擎／IO 失敗轉成統一的領域錯誤＋使用者訊息（不吐原始 traceback）
- [ ] 結構化 log（元件＋錯誤鏈），log 不含 API key
- [ ] debug 檢視頁：最近任務的 log 可查
