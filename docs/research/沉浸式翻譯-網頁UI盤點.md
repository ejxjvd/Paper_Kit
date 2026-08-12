---
title: 沉浸式翻譯 網頁版 UI 盤點
date: 2026-08-12
tags: [paper_kit, research, immersive-translate, ui]
---

# 沉浸式翻譯（Immersive Translate）網頁版 UI 盤點

> 來源：使用者貼圖逐字轉錄（貼圖視覺 hook，10 頁全數轉錄，**資料完整保留**）＋桌機保存 HTML 三份（首頁／幫助文件／翻譯記錄）。
> 官方網址域：`immersivetranslate.com/zh-TW/`。公司：Funstory.ai Limited (Hong Kong)、© 2026 Immersive Translate。
> 用途：Paper_Kit UI 對照標竿之一（與 [[pdf2zh.com-線上GUI-盤點]] 並列；差距分析見 [[沉浸式翻譯-與Paper_Kit-差距分析]]）。

## 0. 全站共用框架（每頁皆同）

### 瀏覽器頂部（非站台元素）
- 分頁列（多頁籤＋新增分頁 `+`）
- 右上角：`問問 Gemini`、擴充功能圖示區、個人頭像、視窗控制（最小化「—」／最大化「□」／關閉「✕」）
- 書籤列（使用者個人書籤，略）

### 沉浸式翻譯頂部導覽列
- 品牌：`沉浸式翻譯`
- 選單：`產品 ˇ`、`價格`、`下載`、`資源 ˇ`
- 右側：`訂閱 Pro 會員 Pro`（按鈕）、`個人中心`、`🌐 繁體中文 ˇ`（語言下拉）

### 左側功能表
- `Upgrade to Pro` 按鈕、折疊按鈕 `<`
- 翻譯分類：`文字`、`文件`（當前選取＝粉紅色按鈕）、`影片`、`圖片`
- 擴展與 App：`Chrome`、`Edge`、`Firefox`、`Safari`、`iOS`、`Android`

### 底部通知橫幅
- `✨ 上新 Kimi + Qwen & Kimi + DeepSeek，點擊查看詳情`（按鈕）

## 1. 文件翻譯頁（`/zh-TW/document/`）

- 頁面頂部：`↪ 回到舊版本`、`📄 使用介紹`、`⏱ 查看翻譯歷史`
- 模式切換：`翻譯單一檔案` 按鈕、`批量翻譯` 按鈕
- 主操作：`📄 上傳文件並翻譯`（**粉紅色主要按鈕**）
- 說明文字：「基礎文件翻譯支援 PDF、ePub、HTML、TXT、JSON、Docx、Markdown、字幕等多種文件格式，PDF Pro 支援 OCR 掃描件翻譯，BabelDOC 可保留原格式進行雙語對照翻譯。」
- 支援格式：「支援 PDF、ePub、HTML、JSON、TXT、DOCX、Markdown 以及各種字幕檔案」
- 批量翻譯提示：「批量翻譯僅支持 Pro 會員使用，請點擊上方按鈕升級會員」（圖二＝`👤 升級為 Pro 會員` 黑色按鈕）
- **「翻譯單個文件」支援 pdf、epub、html、json、txt、docx、markdown 及各種字幕文件；「批量翻譯」僅支援 PDF**

## 2. 圖片翻譯頁（`/zh-TW/image/`）

- 麵包屑：`沉浸式翻譯 > 圖片翻譯`
- 說明：「沉浸式翻譯網頁版支持上傳圖片翻譯和剪貼簿貼圖圖片翻譯。安裝擴充功能後可體驗右鍵點擊一鍵翻譯圖片為目標語言。」
- 下拉選擇框：「將圖片翻譯為：」（顯示 `簡體中文 ˅`）
- 主操作：`📄 上傳圖片`（粉紅色按鈕）
- 上傳提示：「上傳或拖曳本地圖片到此處，也可以直接貼上圖片。」

## 3. PDF Pro 翻譯頁（`/zh-TW/document/pdf-pro-translator/`）

- 麵包屑：`沉浸式翻譯 > 文件翻譯 > PDF Pro`
- 說明：「沉浸式翻譯 AI 驅動的 PDF 翻譯專為追求精準的 PDF 文件而設計，無論是精確專業術語的學術論文，還是包含複雜表格和圖片的各類強效文件，AI 驅動的 PDF 解析技術都能確保保持內容高效率精確的解析，為了提升閱讀體驗，我們的 AI 引擎還會對 PDF 文件重新進行排版，將複雜的多欄佈局轉換為更加清晰、易於閱讀的單欄格式。」
- **支援格式：僅支援 PDF**

## 4. PDF 翻譯器頁（`/zh-TW/document/pdf-translator/`）

- 說明：「Immersive Translate 的文件翻譯器使用 **18 個以上的 AI 引擎**，將 PDF 檔案轉換為超過 100 種語言，在保留原格式的同時提供雙語對照顯示，以實現準確且符合語境的翻譯。」
- 支援格式：僅支援 PDF

## 5. ePub 翻譯器頁（`/zh-TW/document/epub-translator/`）

- 說明：「將 ePub 電子書翻譯成超過 100 種語言，並在保留原格式的同時提供雙語對照文字」
- 支援格式：PDF、ePub、HTML、JSON、TXT、DOCX、Markdown 以及各種字幕檔案

## 6. 字幕翻譯器頁（`/zh-TW/document/subtitle-translator/`）

- 說明：「支援多種格式的字幕檔翻譯，**在保留時間軸的同時**，透過 18 個以上的 AI 引擎提供雙語或單語輸出」
- 支援格式：PDF、ePub、HTML、JSON、TXT、DOCX、Markdown 以及各種字幕檔案

## 7. Zotero 翻譯頁（`/zh-TW/zotero-translator/`）

- 主標題：`沉浸式翻譯 x Zotero`／`POWERED BY IMMERSIVE TRANSLATE`
- 文宣：`完美保留排版的雙語文獻翻譯`／`Zotero 用戶專屬 AI 科研利器`
- AI 模型標籤：`Claude`、`DeepSeek`、`GLM`、`xAI Grok`、`Qwen`
- 描述：「基於強大的 BabelDOC 文件解析引擎，在 Zotero 內一鍵將外文文獻翻譯成高品質的雙語對照版本。公式、圖表、多欄排版毫髮無損。」
- CTA：`⚓ 下載外掛`（紅色）、`🔗 線上使用`（藍色＋`推薦`粉紅標籤）、`↗ 取得授權碼`（白框）
- 預覽控制：左右滑動＋`🔄` 對調按鈕
- 預覽文字：`英文原文 vs 中文翻譯`／`排版完美保留`＋實例論文（EEG 小波分析）

## 8. Google Workspace 頁（`/zh-TW/google-workspace/`）

- 標題：`Immersive Translate`／`Google Workspace™`／`在 Google Docs™ 中直接使用 AI 翻譯文件。`
- 特色（✓ 清單）：`✓ 翻譯 Google Docs 文件`／`✓ 閱讀選取內容`／`✓ 支援術語表`／`✓ 查看雙語文件`／`✓ 保留文件格式`
- 使用方法：「從 Google Workspace Marketplace 安裝外掛程式。」（步驟 1/2/3）

## 9. 產品 Mega Menu（`產品 ˇ` 下拉，完整結構）

- **文件翻譯**：`BabelDOC 保留排版翻譯`、`PDF 翻譯`、`PDF Pro 翻譯`、`ePUB 電子書翻譯`、`字幕檔翻譯 / 下載`、`Zotero 翻譯`、`Google Docs™ 翻譯`
- **網頁翻譯**：`Steam 翻譯`、`AO3 翻譯`
- **文字翻譯**：`文字翻譯 >`
- **圖片翻譯**：`漫畫翻譯`、`圈選翻譯`（= 圖選翻譯）
- **影片翻譯**：`雙語字幕 / 無字幕影片翻譯`、`YouTube 直播翻譯`
- **會議翻譯**：`會議翻譯 >`
- **快捷翻譯**：`輸入框翻譯`、`劃詞翻譯 / 滑鼠懸停翻譯`
- 語言清單（13 語）：繁體中文／简体中文／繁體中文（香港）／English／日本語／العربية／Deutsch／Español／Français／हिन्दी／Italiano／한국어／Português／Português (Brasil)／Русский
- 資源下拉：`影片教學`、`幫助中心`、`部落格`、`聯盟計劃`、`禮品卡`、`使用兌換碼`、`安全與合規`、`聯絡客服`

## 10. 下載平台（首頁底部）

- 瀏覽器擴充功能：`Edge`、`Chrome`、`Firefox`、`Mac Safari`、`油猴腳本`、`crx 安裝包`
- 手機/平板：`iOS`（AppStore）、`Android APK`、`Google Play`、`Edge 瀏覽器`
- 主 CTA：`一鍵 AI 雙語對照翻譯`／`安裝到 Chrome`／`安裝到 Edge`／`下載`

## 11. 使用者實測觀察（控制項檢查）

- 翻譯紀錄表格有：勾選框（圓形，表頭可全選）、`🗑 批量刪除`、`⤓ 批量下載僅譯文`、`⤓ 批量下載雙語`、分頁（`<` 1 `>`、`每頁顯示 10 ˅ 條`）
- 各頁均未見排序控制項
