# 04 — 引擎選擇＋API keys＋預設設定

**What to build:** 設定頁：選翻譯引擎（SiliconFlow gemma／DeepSeek／免費引擎）、API key 輸入（存 SQLite、不洩進 log）、預設引擎／目標語言（zh-TW）／輸出目錄。換引擎後下一次翻譯就用新引擎——用 FakeEngine 證明 UI 與領域零改動。

**Blocked by:** 03

**Status:** ✅ done（2026-08-12，98 測試全綠）

- [x] 設定頁：引擎選擇（含 SiliconFlow .com 預設、DeepSeek、免費引擎）
- [x] API key 表單存 SQLite，log 中不出現明文 key（redaction 實作於票 09 log 層）
- [x] 預設引擎／語言／輸出目錄可存可取
- [x] 換引擎後新任務走新引擎（FakeEngine 驗證；引擎註冊表驅動）

**實作**：engine_registry（5 引擎＋sensitive_ok 紅線 flag）＋SqliteSettingsRepository＋SettingsService.resolve_engine；build_command 免費引擎旗標對映（--google/--bing/--siliconflowfree 實測 CLI 存在）；設定頁 /settings。備註：本機無 DEEPSEEK_API_KEY，DeepSeek 真實驗證待 key。
