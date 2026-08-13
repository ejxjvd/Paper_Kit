# Paper_Kit

自建學術 PDF／簡報翻譯器 —— 免除被線上翻譯工具綁架。

- **引擎**：pdf2zh-next（BabelDOC 管線，公式保真＋原像重排版）
- **UI**：NiceGUI（純 Python 一體、事件驅動、可大量美化）
- **架構**：務實 DDD + Ports & Adapters（引擎可插拔，不被單一供應商綁死）
- **開發流程**：TDD（紅→綠）、垂直切片

## 功能

- 上傳 PDF 翻譯：主頁就地選引擎（SiliconFlow／DeepSeek／BabelDOC／LaTeX 四卡）＋目標語言
- 上傳 `.tex` 源碼：自動鎖定 LaTeX 引擎（票 27）——整份編譯、token 最省（整本 ≈NT$0.34）
- 每筆任務產 mono（僅譯文）＋ dual（雙語對照）雙輸出，卡片與歷史表格都可下載
- 歷史頁（/history）：表格化＋分頁＋勾選全選＋批量刪除（二次確認）＋批量下載 mono/dual zip
- 統一頁框（側欄導覽：翻譯／歷史／設定）＋深色模式
- 引擎 API keys 每引擎獨立（BYOK——交付他人各用各的 key）、遮罩回顯、未填攔截
- 掃描件 OCR、PPT 視覺路徑、LaTeX 源碼路線（主 UI 整合）、術語表、成本估算、任務取消重試

## 文件

- `docs/規格書.md` — 原始規格書（PRD，GitHub issue #1 同步）
- `docs/UI補強-規格書.md` — UI 補強規格書（issue #17 同步）
- `docs/tickets/` — 20 張開發票（GitHub issues #2–#16 與 #18–#22 同步）
- 完整研究與計畫存於 Obsidian Vault（`_personal/Paper_Kit/`）

## 狀態

票 01–20 全部完成＋快取三票（24–26）＋票 27 LaTeX 主 UI 整合——**590 tests passed**（2026-08-13）；冒煙全綠。後續工作以 GitHub issues 追蹤。
