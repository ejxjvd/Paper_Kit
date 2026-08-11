# 04 — 引擎選擇＋API keys＋預設設定

**What to build:** 設定頁：選翻譯引擎（SiliconFlow gemma／DeepSeek／免費引擎）、API key 輸入（存 SQLite、不洩進 log）、預設引擎／目標語言（zh-TW）／輸出目錄。換引擎後下一次翻譯就用新引擎——用 FakeEngine 證明 UI 與領域零改動。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] 設定頁：引擎選擇（含 SiliconFlow .com 預設、DeepSeek、免費引擎）
- [ ] API key 表單存 SQLite，log 中不出現明文 key
- [ ] 預設引擎／語言／輸出目錄可存可取
- [ ] 換引擎後新任務走新引擎（FakeEngine 驗證；引擎註冊表驅動）
