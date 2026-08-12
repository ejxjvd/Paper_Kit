---
title: 沉浸式翻譯 產品結構與 BabelDOC 知識
date: 2026-08-12
tags: [paper_kit, research, immersive-translate, babeldoc]
---

# 沉浸式翻譯（Immersive Translate）產品結構與 BabelDOC 知識

> 來源：桌機保存 HTML `沉浸式翻譯 - 新一代AI翻譯軟體...html`（首頁，629KB）＋`幫助文件.html`（756KB）文字抽取。
> 公司：**Funstory.ai Limited (Hong Kong)**、© 2026 Immersive Translate；「2000 萬用戶」。

## 1. BabelDOC 定位（首頁核心產品）

- 「BabelDOC 是新一代智慧 PDF 翻譯工具，採用先進的排版保持技術，提供專業級的雙語對照翻譯體驗。」
- **「BabelDOC 已正式開源，項目託管於 GitHub」**（即 funstory-ai/BabelDOC，見 [[2026-08-12-Paper_Kit-研究-BabelDOC]]）
- 首頁標籤切換：`Simple Document`／`PDF Pro`／`BabelDOC`（三種文件翻譯模式）

### 四大技術賣點（逐字）
1. **精準雙語對照，原汁原味呈現**——「採用智慧版面分析技術，精確識別文件結構與段落布局。譯文與原文智慧對齊，讓您在閱讀時可以即時對照」
2. **智慧公式文字混排**——「採用公式識別技術，完美處理數學公式與文字的複雜混排場景。公式內容原樣保留，文字部分智慧翻譯，確保學術文獻的專業性和準確性」
3. **原生樣式完美呈現**——「採用先進的樣式映射技術，完整保留原文件的字體、顏色、間距等設計元素。支持標點懸掛、自適應縮放等專業排版特性」
4. **複雜排版智慧處理**——「採用深度學習布局分析技術，從容應對多欄布局、表格、列表等複雜排版形式」

### 支援引擎（Pro 會員）
`DeepSeek`、`DeepL`、`OpenAI`、`Claude`、`Gemini`——「提供精準、流暢、自然的閱讀體驗」；「多引擎整合讓用戶能針對不同情境選擇翻譯文句」

## 2. 常見問題（FAQ 標題清單，答案在頁內摺疊）

- 如何在 Zotero 中使用 BabelDOC 翻譯 PDF？（→ Zotero 沉浸式翻譯擴充功能倉庫，README 安裝；**目前僅 Pro 會員可用**）
- 最佳應用場景／暫不適用的場景
- 使用的翻譯服務
- BabelDOC 的技術優勢
- 翻譯額度說明
- 翻譯性能說明
- 並發任務數說明
- 文件限制說明
- 使用技巧
- 已知限制
- **BabelDOC 與沉浸式翻譯現有 PDF 翻譯有什麼區別**
- 翻譯效果不如預期
- 為什麼導出 PDF 很慢
- 什麼時候需要啟用兼容模式？／啟用兼容模式的影響是什麼？
- 為什麼翻譯後的文件譯文和原文疊起來了
- 何時需要啟用 OCR 版臨時解決方案？
- **為什麼 BabelDOC 不支持自定義 API？**

## 3. 全產品線（對應 [[沉浸式翻譯-網頁UI盤點]] §9 mega menu）

| 分類 | 產品 |
|---|---|
| 文件翻譯 | BabelDOC 保留排版翻譯、PDF 翻譯、PDF Pro 翻譯、ePUB 電子書翻譯、字幕檔翻譯/下載、Zotero 翻譯、Google Docs™ 翻譯 |
| 網頁翻譯 | Steam 翻譯、AO3 翻譯 |
| 文字翻譯 | 文字翻譯 |
| 圖片翻譯 | 漫畫翻譯（50+ 漫畫網站，含集英社、MANGA Plus）、圈選翻譯 |
| 影片翻譯 | 雙語字幕/無字幕影片翻譯（100+ 影音平台）、YouTube 直播翻譯 |
| 會議翻譯 | 會議翻譯 |
| 快捷翻譯 | 輸入框翻譯、劃詞翻譯/滑鼠懸停翻譯 |

## 4. 市場面知識（Paper_Kit 不需對標，僅供脈絡）

- 口碑：Mobile01、AI 郵報、INSIDE、香港 01、中央社 3C、UDN、電腦王阿達、Techbang、TechNews、LINE TODAY、Cindy 等 KOL 推薦
- 使用情境：「預設閱讀環境」（論文/文件閱讀）、「跨國會議即時翻譯」、「保留排版翻譯 PDF」
- 品牌調性：一鍵、雙語對照、多引擎自由切換、不破壞閱讀節奏

## 5. 對 Paper_Kit 的關鍵啟示（BabelDOC 知識整合）

1. **三模式文件翻譯**（Simple Document／PDF Pro／BabelDOC）＝三種引擎切換的產品化呈現——Paper_Kit 引擎選擇頁概念相同但更技術化（設定頁），可考慮主頁三卡式切換
2. **BabelDOC 四賣點**＝Paper_Kit LaTeX 路線已在兌現的（公式保真/版面保留）——但 Paper_Kit 沒有「樣式映射」級輸出（原生樣式、標點懸掛、自適應縮放）
3. **「為什麼 BabelDOC 不支持自定義 API？」**＝免費/訂閱制商業決策——Paper_Kit 完全自帶 API key（BYOK），是與之相反的定位優勢（免綁架，見 [[paper-kit-ui-goal]]）
4. **兼容模式／OCR 臨時解決方案**＝對應 pdf2zh-next 的 `--enhance-compatibility`／`--ocr-workaround`（見 [[pdf2zh-next-CLI旗標參考]]）——Paper_Kit UI 若做「相容模式」開關可直接映射旗標
5. **額度/性能/並發/文件限制四說明**＝線上服務的 SLA 話術；Paper_Kit 本機工具無此限制，反而是賣點
