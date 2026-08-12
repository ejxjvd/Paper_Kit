# UI 補強規格書：資訊架構完整化（批 0＋批 A）

> 源起：使用者回饋「介面簡陋，對比 PDFMathTranslate/沉浸式翻譯差太多」。研究定論（[[2026-08-12-Paper_Kit-研究-統整索引]]）——**功能面已齊，差距在資訊架構與操作密度**。本規格收斂兩份差距分析（[[2026-08-12-Paper_Kit-UI-差距分析]]、[[2026-08-12-Paper_Kit-UI-差距分析-沉浸式翻譯]]）的批 0（任務歷史表格化＋批量操作）與批 A 核心（統一頁框＋就地選項＋每筆顯示引擎）。

## Problem Statement

使用者是學生研究者，每天要翻多篇論文。目前 Paper_Kit 的 UI：
- 三個頁面（`/`、`/settings`、`/debug`）各自獨立，沒有統一導覽框架——切換像在不同網站。
- 任務歷史是首頁捲動卡片流，量大難掃、無分頁、無批量操作——對比沉浸式翻譯的表格（勾選＋批量刪除＋批量下載）差距明顯。
- 翻譯選項（引擎、目標語言）藏在 /settings，主頁無法就地調整——每次翻譯都要跳頁。
- 任務卡片看不出用哪個引擎。

## Solution

把 Paper_Kit 補成「一個完整工具」的資訊架構：

1. **統一頁框**：左側欄導覽（翻譯／歷史／設定），三頁共用框架元件，全站一致的外觀與導覽。
2. **任務歷史頁**（新 `/history`）：表格化（勾選／文件名／創建時間／頁數／引擎／狀態／操作），分頁每頁 10 筆，空狀態提示。
3. **批量操作**（歷史頁）：全選勾選、批量刪除（含輸出檔，二次確認）、**「批量下載僅譯文（mono）」與「批量下載雙語（dual）」各一鍵**（zip）。
4. **雙語對照輸出**（既有能力，本次確保不可退化）：每筆任務產 mono＋dual，主頁卡片與歷史表格都提供 dual 下載——參考沉浸式翻譯「雙語對照」是其最核心賣點，Paper_Kit 已有，不能因 UI 重構弄丟。
4. **翻譯主頁就地選項**：引擎三選卡（SiliconFlow／DeepSeek／BabelDOC，含各引擎一行說明）＋目標語言下拉＋頁數快捷（全文／自訂）——不再強制跳 /settings。
5. **任務卡顯示所用引擎**＋狀態彩色標籤維持。

## User Stories

1. 作為使用者，我想要所有頁面有統一的左側導覽（翻譯／歷史／設定），以便不用記網址就能切換功能。
2. 作為使用者，我想要在翻譯主頁就地選引擎（三張引擎卡）與目標語言，以便不跳設定頁就開始翻譯。
3. 作為使用者，我想要歷史任務以**表格**呈現（文件名／創建時間／頁數／引擎／狀態／操作），以便大量任務一覽無遺。
4. 作為使用者，我想要歷史表格**分頁**（每頁 10 筆），以便不捲動長列表。
5. 作為使用者，我想要**勾選＋全選**任務，以便對多筆做批量操作。
6. 作為使用者，我想要**批量刪除**勾選任務（含其輸出檔），以便清掉舊任務；誤觸有二次確認保護。
7. 作為使用者，我想要**批量下載僅譯文（mono）**與**批量下載雙語（dual）**各一鍵、打包成 zip，以便一次取回多份論文。
8. 作為使用者，我想要每筆任務（表格與卡片）顯示**所用引擎**，以便知道哪次用了哪個模型。
9. 作為使用者，我想要歷史頁有「翻譯新文件」快捷入口，以便不跳回主頁也能開新任務。
10. 作為使用者，我想要空歷史時有明確提示與引導，以便知道功能在哪。
11. 作為使用者，我想要**雙語對照輸出永遠保留**（每筆任務都有 dual 可下載，主頁卡片與歷史表格皆然），以便對照原文精讀——這是「最不可或缺」的功能。
11. 作為使用者（要交付他人使用的人），我想要設定頁**每個引擎各有獨立的 API key 欄位**（SiliconFlow／DeepSeek／BabelDOC 各一），以便別人用自己的 key、不用共享我的 key。
12. 作為使用者，我想要**清除**已存 key 的能力，以便停用某引擎時移除憑證。
13. 作為使用者，我想要已存 key **遮罩回顯**（只顯示前 6 字符＋星號，切換時才露明文），以便設定頁不會洩漏 key 全文。
14. 作為使用者，我想要**未填 key 的引擎無法啟動翻譯**（開始前明確提示去設定頁），以便立即知道缺什麼、不會白等失敗。

## Implementation Decisions

- **統一頁框**：新增 presentation 元件 `app_frame()`（NiceGUI `ui.header` + `ui.left_drawer`）——普通函數、頁面建構時呼叫一次，不包 content slot（header/drawer 是 client 層級元素，不需包覆內容；實作初期曾以 context manager 包內容導致縮排重排，已棄）；三頁（`/`、`/settings`、`/debug`，歷史頁 `/history` 票 17 加入）共用。導覽項目：翻譯（`/`）、歷史（`/history`）、設定（`/settings`）；Debug 保留為側欄底部連結。
- **歷史表格**：新路由 `/history`（`_history_page` 模組級函數，同 `_index_page` 測試 seam 慣例）。資料來自 `JobService.list_jobs()`（既有契約，無需新 repository 方法；分頁在 UI 層切片——本機工具任務量級遠低於需 server 端分頁）。欄位：勾選框（`ui.table` selection 或自訂 checkbox 欄）、文件名、創建時間（`created_at` 轉本地格式）、頁數（由 source 推測或留空——**由 `result`/`pages` 呈現**）、引擎（`engine_id` 顯示名稱對照）、狀態（彩色標籤）、操作（下載 mono／dual、重試、取消）。
- **批量刪除**：`JobService.delete(job_id: str) -> None`（新方法；檢查任務不在執行中才可刪；刪除時移除 `output_dir` 下檔案）。批量＝UI 迴圈呼叫＋二次確認 dialog。
- **批量下載**：新 `/download-batch?ids=...&kind=mono|dual` 路由（**兩個獨立按鈕：僅譯文 mono／雙語 dual**），伺服端 zip 打包暫存後回傳（`zipfile`）；暫存檔送完即刪。
- **引擎卡**：主頁翻譯卡內三張可選卡（radio 卡片化，點選即設定該任務引擎——覆寫預設）。引擎顯示名對照表收攏（settings 已有清單，共用函式）。
- **就地選項**：主頁翻譯卡增加：引擎卡群、目標語言下拉（讀 defaults，改寫僅本任務）、頁數快捷（radio：全文／自訂＋既有 input）。機密／OCR 開關維持原位。
- **每筆顯示引擎**：任務卡與歷史表格顯示 `engine_id` 對照名。
- **API key 每引擎獨立欄位**（BYOK 交付）：設定頁引擎區改為每引擎一卡（引擎名＋說明＋獨立 key 欄＋儲存），取代「下拉選引擎＋單一 key 欄」；沿用 `settings.set_api_key(engine_id, api_key)` 契約（寫 `~/.paper_kit/paper_kit.db`，明文不入 repo/log）。**契約語意調整**：`api_key` 為空字串＝清除該引擎 key（現行 `_save_engine` 空串不寫、無法清除）。回顯遮罩：已存時只顯示前 6 字符＋其餘 `*`。翻譯啟動前置檢查：所選引擎無 key → 就地錯誤提示「此引擎未設定 API key，請到設定頁填寫」，不呼叫引擎。
- 不改 domain 模型；不改 repository 契約（分頁 UI 層）。`JobService` 只加 `delete`。

## Testing Decisions

- 測試只測外部行為（user_simulation 開真實頁面＋斷言元素），不測實作細節。
- **既有 seams**（沿用）：
  - `tests/presentation/`：`user_simulation` + `nicegui_reset_globals` autouse fixture；`FileWritingFakeEngine` 注入（`resolve_engine` monkeypatch）。
  - `tests/application/`：JobService 單元測試（InMemoryJobRepository）。
- 新增測試：
  - `test_history_page.py`：渲染表格欄位、分頁（20 筆→兩頁）、空狀態提示、引擎欄顯示、操作列下載連結。
  - `test_batch_ops.py`：全選、批量刪除（含輸出檔移除、執行中任務拒絕）、批量下載 zip 路由（產生 zip 含正確檔案、送完刪暫存）。
  - `test_index_page.py` 擴充：引擎卡存在且點選後任務卡顯示對應引擎、就地語言下拉存在。
  - `test_app_frame.py`：三頁都有側欄導覽項、點擊導航到正確頁。
  - `test_settings_page.py` 擴充：每引擎獨立 key 欄位、清除按鈕後 `settings.api_key` 回傳空、遮罩回顯（前 6 字符＋星號）、空 key 不覆寫他引擎。
  - `test_index_page.py`：未填 key 的引擎按開始翻譯 → 錯誤提示且引擎未被呼叫（fake 注入側信道驗證）。
- JobService.delete 單元測試：刪除後 list 不含、輸出目錄消失、執行中拒絕。

## Out of Scope

- 批 B 實驗選項（ignore-cache／threads／custom-prompt／lang-in）——旗標已驗證，另立規格。
- 批 C（URL 輸入、快捷頁數 First/20）。
- 翻譯快取（SQLite）——最大省錢項，另立規格。
- 批量佇列（一次上傳多檔依序翻譯）。
- 深色模式加強、品牌視覺系統。

## Further Notes

- 參考標竿：沉浸式翻譯記錄頁（欄位/批量/分頁）＋pdf2zh.com（就地選項密度）——詳見研究知識庫。
- 分頁用 UI 層切片即可（本機個人工具；若未來多人共用再 server 端分頁）。
- 刪除輸出檔屬破壞性操作——二次確認 dialog 必做；JobService.delete 對執行中任務拋錯由 UI 提示。
