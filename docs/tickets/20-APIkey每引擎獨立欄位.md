# 票 20：API key 每引擎獨立欄位＋清除＋遮罩＋未填攔截

**Parent:** [issue #17 UI 補強規格書](https://github.com/ejxjvd/Paper_Kit/issues/17)

## What to build

設定頁引擎區改為每引擎一卡（SiliconFlow／DeepSeek／BabelDOC），各有獨立 API key 欄位＋儲存＋清除。已存 key 回顯只顯示前 6 字符＋星號。翻譯啟動前置檢查：所選引擎無 key → 就地錯誤提示（「此引擎未設定 API key，請到設定頁填寫」），不呼叫引擎。目的：工具交付他人時各自用自己帳號的 key（BYOK），不共用使用者本人的 key。

## Acceptance criteria

- [ ] 設定頁顯示三張引擎卡，每卡獨立 key 欄位＋儲存
- [ ] 儲存後 settings.api_key 對應引擎回傳該 key（寫 ~/.paper_kit/paper_kit.db，不入 repo/log）
- [ ] 回顯遮罩：已存時顯示前 6 字符＋其餘星號；儲存另一引擎不覆寫他引擎 key
- [ ] 清除按鈕：清空後 api_key 回傳空
- [ ] 主頁以無 key 的引擎開始翻譯 → 錯誤提示且引擎未被呼叫（fake 側信道驗證）
- [ ] 現有全部測試綠

## Blocked by

- 票 16：統一頁框（issue #18，已完成 2026-08-12）

## 實作紀錄

### 2026-08-12 完成

**AC 對照：**

- [x] 設定頁顯示三張引擎卡，每卡獨立 key 欄位＋儲存 — 「引擎 API keys」卡內 `for eid, desc in ENGINE_CARDS` 迴圈三張子卡（`.mark(f"engine-key-{eid}")`），各含「已設定/未設定 key」badge＋`ui.input(password=True)`＋「儲存 key」＋「清除」；0 參數 factory `_save_engine_key`/`_clear_engine_key`（票 19 教訓：`lambda eid=eid:` 被 event 物件覆寫）
- [x] 儲存後 settings.api_key 對應引擎回傳該 key — 既有 `SettingsService.set_api_key`（SQLite `~/.paper_kit/paper_kit.db`，無 log/repo 路徑）
- [x] 回顯遮罩：前 6 字符＋其餘星號 — `_mask_key`（短 key ≤6 全星號——隱私最小化，全顯示＝整把曝光）；儲存另一引擎不覆寫他卡（測試同時存 deepseek/siliconflow 驗證互不影響）
- [x] 清除按鈕：清空後 api_key 回傳空 — `_clear_engine_key`；**spec review 修正**：一併清 input 顯示值（見下）
- [x] 主頁以無 key 的引擎開始翻譯 → 錯誤提示且引擎未被呼叫 — 票 19 既有 `_resolve_task_engine` 建引擎前查 key（override 路徑）＋票 04 `resolve_engine`（global 路徑）；本票補側信道測試：monkeypatch spy `build_engine` 計數＋斷言 `list_jobs()==[]`
- [x] 現有全部測試綠（426 passed）

**新增測試（7 個）：** test_settings_page.py 6（mask 純函式＋三卡遮罩回顯＋儲存只寫該卡＋遮罩防寫回＋清除清空；spec review 後補清除清 input 斷言）＋ test_index_page.py 1（AC5 未填攔截側信道）。

**兩軸 code review 裁決：**

- **Spec 軸（1 真 bug 全修）：** 清除 key 後 input 仍顯示遮罩——「清除後再按儲存」時 `_save_engine_key` 防遮罩判斷（current="" 時任何值都過）把遮罩字串寫回 DB，key 損毀不可復原。修：`_clear_engine_key` 一併 `key_input.value = ""`＋測試補 input 空斷言（紅→綠實證）。次要（錯誤文案與規格引號內措辭微差）跳過——票 19 既有措辭、AC 只要求「錯誤提示」。
- **Standards 軸（5 findings，修 1）：** 測試回顯遮罩用 `_mask_key(...)` 算預期值＝tautology → 改字面 `"sk-tes*******"`；其餘跳過（引擎卡迴圈頭同形但兩頁內容分歧大、notify label 查表重複但三訊息形狀不同抽 helper 反裂、硬編碼三卡名＝規格明定三支、`eid` 命名＝既有慣例）。

**開發中陷阱（防重現，詳見 TDD-Log）：** `_save_engine_key` 防遮罩寫回是「值≠遮罩才寫」——清除後 current=""、遮罩=""，殘留 input 值必過判斷，**清除必須同時清 input**（spec review 抓到）；notify 訊息用 `spec.label` 全文（測試動態組 `f"已儲存 {ENGINE_SPECS['deepseek'].label} 的 API key"`——寫死短名找不到）。

**冒煙（scripts/smoke.sh）：** `/`、`/history`、`/settings`、`/debug` 四頁 200；zip-none 404；bad kind 400。

**Commit：** 票 20 完成 commit（見 git log；票 19 為 `d5040db`）。
