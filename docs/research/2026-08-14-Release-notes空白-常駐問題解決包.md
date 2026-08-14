# Release notes 空白：CI 提取 regex 與文件標題不一致（常駐問題解決包）

> ⚠️ **常駐問題解決包（最優先）**——2026-08-14 使用者抓到 v0.1.8 Release 頁面
> notes 空白。發布流程缺陷：**任何版本發布都可能在 Release 頁面出空 notes**，
> 且不影響 CI 綠燈——本包常駐，發布流程確認清單必須含「Release 頁面 body 確認」。
> 使用者指定：此類問題可能頻繁遇到，納入常駐包並同步開發知識庫。

## 症狀

- GitHub Releases 頁面 v0.1.8 顯示空白說明（只有標題「Paper_Kit 0.1.8」）
- CI 全綠、資產正常上傳（雙 zip 在、可下載）——**空 notes 不影響任何綠燈**，
  只能靠人眼開 Release 頁面抓到

## 根因

`packaging/RELEASE_NOTES.md` 區段標題帶 v 前綴（`## v0.1.8`），但
`.github/workflows/release.yml` 的 awk 提取 regex 為 `"^## " tag "$"`（**無 v**）
→ 匹配 0 行 → `NOTES` 空 → fallback「Paper_Kit 0.1.8」（15 字元）。

```awk
# 壞：regex = ^## 0.1.8$，檔案是 ## v0.1.8 → 不匹配
$0 ~ "^## " tag "$" {found=1; print; next}
# 好：regex = ^## v?0.1.8$，兩式相容
$0 ~ "^## v?" tag "$" {found=1; print; next}
```

## 修復（2026-08-14，commit `74d2819`）

1. `release.yml` awk regex 改 `"^## v?" tag "$"`＋根因註解
2. **防回歸測試** `tests/test_release_notes_extraction.py`（4 個）：
   - 每個 `## vX.Y.Z` 標題必須被 CI regex 匹配（提取再壞先紅）
   - 提取煙霧：v0.1.8 區段含「空殼模型誤報 401」、不含下一版標題
   - v 前綴變體參數化（帶 v／不帶 v 都匹配）
3. **現況補救**：`gh release edit v0.1.8 --notes "$(awk 修正版提取)"`——677 字元完整 notes 補回

## 教訓（發布流程）

1. **Release 確認 = 資產＋body 雙查**：紀律 12「Release notes 更新並重複確認 2 次」
   之前只驗了資產與 zip 內手冊——**Release 頁面 body 本身也要查**（`gh release
   view <tag> --json body`，非空且含新版本關鍵字）
2. **文件與 CI regex 的契約測試**：CI 內嵌 awk 讀取文件格式——格式漂移或 regex
   改動都會靜默失敗（fallback 不報錯）。防回歸測試從 CI 檔**讀出** regex 驗證
   一致性——文件格式一改，測試立刻紅
3. **fallback 是壞味道**：`if [ -z "${NOTES}" ]` 的 fallback 吞掉提取失敗——
   寧可 CI 紅（提取失敗即報錯）也不要靜默出空 notes；現階段以測試補防，改硬
   失敗會影響歷史 tag 重發布，列為未來候選

## 驗證

- 修復後 awk 提取 v0.1.8：**17 行**（原邏輯 0 行）
- `gh release view v0.1.8` body = 677 字元完整 notes（含「空殼模型誤報 401」）
- 全套件 **705 passed**（701＋4 新）
- 監督三 repo 全綠（Paper_Kit `74d2819`）

## 防再犯檢查清單（每次發布）

- [ ] `gh release view <tag> --json body` 非空（>100 字元）且含本版關鍵字
- [ ] `pytest tests/test_release_notes_extraction.py` 綠（CI 已含）
- [ ] RELEASE_NOTES.md 新區段標題 `## vX.Y.Z`（帶 v，與 regex 相容）
