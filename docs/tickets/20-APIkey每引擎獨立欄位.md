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

（待實作）
