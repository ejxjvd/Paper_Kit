# 13 — Phase 2：BabelDOC 線上 adapter

**What to build:** Ports & Adapters 的「換插頭」證明：BabelDOC 引擎掛一支 adapter 進引擎註冊表，UI 可選——領域與 UI 零改動（FakeEngine 測試守住換引擎不破壞行為）。

**Blocked by:** 04

**Status:** ✅ done（2026-08-12，304 測試全綠，兩軸 review 全部套用）

- [x] BabelDOC 引擎 adapter 實作（key＋配額管理）
- [x] 引擎註冊表新增後 UI 立即可選
- [x] 既有 FakeEngine 測試全綠（證明換插頭不破壞）

## 實作

### 一手查證結論（2026-08-12，方向轉向）

BabelDOC 線上服務（Immersive Translate 託管 web app）**無公開程式化 API、無 API key 產品**——官方 README 明示「All APIs of BabelDOC should be considered as internal APIs」，`pdf2zh_next -h` 也無任何 cloud/account flag。→ 票 13 落地 = **BabelDOC 官方 CLI（AGPL v0.6.4）＋OpenAI 相容雲端後端**（README 唯一支援的程式化整合：「only OpenAI-compatible LLM is supported」，點名 deepseek-chat，實測源碼驗證 CLI 旗標）。

### 換插頭重構（expand-contract）

- `CliAdapterBase` 共用骨架：translate 循環（retry 退避 2^n、逾時樹殺、cancel 後雜訊處理、key 遮罩 redact、友善錯誤對映）——子類只提供 `_api_key` / `_build_command` / `_parse_output` 三個插頭
- `Pdf2zhNextAdapter` 遷移上骨架（既有 104 測試全綠證明重構安全；module-level API 保留 re-export 使測試 import 位置不變）
- `BabelDocAdapter` 第二支插頭繼承同一骨架——**領域與 UI 零改動**（app.py 引擎下拉由 `ENGINE_SPECS.items()` 生成，加 spec 即 UI 可選，AC2 零改動守證）

### AC1 key＋配額

- key 走既有 SettingsService api_key 機制（babeldoc 為新 engine 槽位）
- 配額＝既有 CostService；DEFAULT_PRICING 新增 babeldoc（0.00027 in / 0.0011 out / 5000 per-page，比照 DeepSeek 後端）

### 引擎註冊表

- `"babeldoc": EngineSpec(provider="babeldoc", model=DEFAULT_BABELDOC_MODEL, needs_key=True, sensitive_ok=False, base_url=DEFAULT_BABELDOC_BASE_URL)`
- `build_engine` 以 `if spec.provider == "babeldoc"` 分派到 BabelDocAdapter，其餘走 Pdf2zhNextAdapter
- **sensitive_ok=False 決策理由**：babeldoc 送雲端 LLM（deepseek-chat）→ 機密模式自動遮蔽。與 deepseek 引擎（sensitive_ok=True）同後端不同旗標，保守可辯：機密模式只放行經驗證的直連 DeepSeek 路徑

### 已知取捨（spec review 提示，記入）

1. **自動術語提取成本低估**：babeldoc 的 term-extraction tokens 另行 log（main.py 源碼實證）→ 開自動提取時總成本可能低估。預設關閉、影響面小，屬已知取捨
2. **sensitive_ok=False 保守**：如上，可辯但保守

## 兩軸 review 紀錄

**Standards 軸**（1 硬違規＋1 Divergent Change，全修）：
- `cli_adapter_base.py` 死 `import re` → 移除
- `_TRANSIENT_SIGNATURES` 寫死 50507（SiliconFlow 特有）＝Divergent Change → `_is_transient` 基底方法＋`_transient_signatures` class attr（子類可覆寫）；pdf2zh 移除無引用的私有 re-export

**Spec 軸**（3 AC 全過）：
- 旗標/token log/檔名慣例全部源碼逐字驗證（`--glossary-files`、`--only-include-translated-page` 僅 `--pages` 時有效、`{basename}.{lang_out}.mono/.dual.pdf`、`Total tokens: {value}`）
- 實測發現 bug：glossary_files 與 auto_extract 並存時 `--no-auto-extract-glossary` 衝突 → 統一兩插頭為 `if job.glossary_files and not job.auto_extract:` ＋新增守證測試
- 換插頭不破壞：settings_service 測試追加 babeldoc 走同一 resolve 路徑（isinstance BabelDocAdapter）

## 測試

304 passed（280→304，+24），22.05s。新增：test_babeldoc_adapter.py（18 tests）、engine_registry 3 tests、settings_service 1、cost_service 1、pdf2zh_next_adapter 1（統一旗標守證）。

**commit:** `c2af9c0`（票 13 完成：BabelDOC adapter（換插頭證明，304 tests green），10 files，+632/-141）
