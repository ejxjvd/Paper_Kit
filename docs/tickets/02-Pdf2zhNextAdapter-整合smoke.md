# 02 — Pdf2zhNextAdapter（DeepSeek）＋整合 smoke

**What to build:** 第一個真實引擎 adapter：把 `pdf2zh_next` CLI 包在 `TranslationEnginePort` 後面（key/base-url 一律 CLI 旗標直傳，不靠 process env；SiliconFlow 國際站 .com 端點）；一支標 slow 的整合 smoke 測試用 fixture 2 頁 PDF 斷言 mono/dual 產出與公式保留。

**Blocked by:** 01

**Status:** ✅ done（2026-08-12，commit f66759c，14 單元＋1 smoke 全綠）

- [x] Adapter 以 CLI 旗標傳 `--siliconflow-api-key`／`--siliconflow-base-url`（預設 `https://api.siliconflow.com/v1`）與 DeepSeek key
- [x] 引擎錯誤（401、CSV 格式錯）轉成領域錯誤訊息，不透傳原始 traceback 給 UI
- [x] 整合 smoke（標 slow）：fixture 2 頁公式密集 PDF → 產出 mono+dual → 抽樣文字斷言公式原樣、可搜尋
- [x] glossary CSV（標頭列）正確帶入 `--glossaries`
