# 09 — 錯誤處理與 log 追蹤

**What to build:** 故障可追蹤：統一錯誤 toast（領域錯誤→使用者看得懂的訊息）、結構化 log（時間／層級／元件／錯誤鏈）、debug 檢視頁——「DEBUG 方便好找」的專屬切片。

**Blocked by:** 03

**Status:** ✅ done（2026-08-12，239 測試全綠）

- [x] 所有引擎／IO 失敗轉成統一的領域錯誤＋使用者訊息（不吐原始 traceback）
- [x] 結構化 log（元件＋錯誤鏈），log 不含 API key
- [x] debug 檢視頁：最近任務的 log 可查

**實作**：`application/errors.py`（新）——`to_user_message` 統一錯誤→使用者訊息對映（InvalidTransition 固定中文、EngineError／GlossaryFormatError／ValueError 直通、其餘遮 traceback 的「發生未預期錯誤」）；`infrastructure/logging_setup.py`（新）——JSON Lines 結構化 log（time/level/component/message＋job_id/error_chain/error extra）、setup_logging 防重複 handler、`redact`／`redact_command` 遮 API key（log、toast、job.error 三處都守）、`format_error_chain` 沿 `__cause__`（沒有則 `__context__`）、`recent_log_entries` 依 job_id 過濾、`format_log_line` 顯示；JobService 事件 log（建立／開始／取消／完成／失敗都帶 job_id）＋`_run` 兜底 except（非 EngineError 意外例外→FAILED＋使用者訊息，不讓 daemon thread 帶 traceback 死亡；取消後引擎才爆→維持 CANCELLED）；adapter 逾時／失敗 log 含錯誤鏈＋遮罩命令（`raise ... from` 真實鏈）；`/debug` 檢視頁（job_id 過濾＋行顯示＋空狀態）。兩軸 review（standards 硬問題 H1 key 回顯 redact 回歸測試＋H2 rename KeyError 語境修正；spec 兜底 except、KeyError 泛對映移除、`__context__` fallback、tail_log 死碼刪除）全部套用。
