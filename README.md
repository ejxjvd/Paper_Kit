# Paper_Kit

自建學術 PDF／簡報翻譯器 —— 免除被線上翻譯工具綁架。

- **引擎**：pdf2zh-next（BabelDOC 管線，公式保真＋原像重排版）
- **UI**：NiceGUI（純 Python 一體、事件驅動、可大量美化）
- **架構**：務實 DDD + Ports & Adapters（引擎可插拔，不被單一供應商綁死）
- **開發流程**：TDD（紅→綠）、垂直切片

## 文件

- `docs/規格書.md` — 規格書（PRD，GitHub issue #1 同步）
- `docs/tickets/` — 15 張開發票（GitHub issues #2–#16 同步）
- 完整研究與計畫存於 Obsidian Vault（`_personal/Paper_Kit/`）

## 狀態

Phase 1（票 01–11）尚未開始；POC 驗證已完成（gemma / DeepSeek 翻譯品質、術語表、公式保真）。
