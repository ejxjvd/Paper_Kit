# 15 — Phase 2：LaTeX 源碼路線

**What to build:** 有 .tex 源碼的論文走殺手級路線：翻 .tex（公式指令原封保留）→ xelatex 編譯 → 100% 公式與排版保真、token 最省。

**Blocked by:** 04

**Status:** ✅ done（2026-08-12，370 測試全綠，兩軸 review 全部套用）

- [x] .tex 上傳→翻譯（公式指令保留）→ xelatex 產出 PDF（fixture .tex 驗證）
- [x] 公式 100% 原樣、中文可編譯（xeCJK）
- [x] 成本記錄（應低於 PDF 路線）

## 實作

### 管線（Ports & Adapters，第四支引擎插頭）

1. **分段（latex_parser）**：環境狀態機——`equation/align/figure/table/tabular/algorithm/lstlisting/verbatim/tikzpicture/thebibliography/minipage` 等內容環境（含巢狀）整段 keep；`document` 容器內文可譯；前置指令/註解/`\label` 等 keep；標題型指令（section/caption/title...）與 `\item` 行獨立成段（指令字首原封、內文可譯）；連續純文字行合併成一段（一次 API 呼叫，段落上下文完整）
2. **佔位保護（latex_parser）**：行內公式 `$...$`/`\(...\)`/`\[...\]`/`$$...$$` 與 `\cite/\ref/\eqref/\label` 抽成 `\PKP{n}` 佔位符（LLM 不會改動），翻譯後原樣還原——**AC2「公式 100% 原樣」的關鍵**
3. **翻譯（latex_translator）**：模型鏈照 §8（Vault CLAUDE.md 強制）——主 `deepseek-chat`（40s）＋備援 `deepseek-reasoner`（40s，同端點雙模型防模型級事件；reasoner 官方不支援 temperature → 備援 payload 不送，否則備援會死）；prompt 硬規則「\PKP{數字} 佔位符原樣保留、位置不變」；401/無效 key → 友善錯誤；缺 key 早期檢查（`MISSING_API_KEY_MESSAGE`，不白跑讀檔/編譯）
4. **編譯（tex_compiler）**：xelatex headless（`-interaction=nonstopmode -halt-on-error`——headless 不能被錯誤中斷等輸入）；**MiKTeX 專屬 `--enable-installer`：缺 xeCJK 等套件自動安裝，不彈「Package Installation」GUI 等確認**（smoke 實測：彈窗阻塞到逾時 180s；TeX Live 不認此旗標，只在 .exe 加）；wslpath -w 轉 Windows 路徑（xelatex.exe 是 Windows 程式）；缺 xelatex → 友善錯誤含 MiKTeX 安裝指引
5. **組裝（latex_adapter）**：譯文回填 → 寫 `{stem}-{lang}.tex`（UTF-8）→ 編譯 → JobResult（mono = 編譯 PDF、dual = None）；tokens 累加 → 既有 CostService 路徑（JobService 零改動，AC3 守證）；cancel 旗標分段檢查

### 設計決策

- **模型鏈 = deepseek-chat 主 → deepseek-reasoner 備援（同端點雙模型）**：latex 引擎只有單一 api_key 槽位（build_engine 單 key），跨供應商備援需第二 key——同端點雙模型無 key 問題且防模型級整顆掛事件（§8）；備援罕見觸發，reasoner 較貴可忽略
- **registry-driven**：`"latex": EngineSpec(provider="latex", needs_key=True, sensitive_ok=True)` → UI 引擎下拉自動出現；build_engine 以 provider 分派 LatexAdapter
- **紅線 sensitive_ok=True**：純文字源碼（不上圖、不上第三方）——機密模式可用（票 10 合規）
- **成本**：DEFAULT_PRICING 加 latex（0.00027/0.0011/5000，deepseek-chat 同價）；**「應低於 PDF 路線」論證**：單價相同但 token 量級不同——LaTeX 源碼是論文最精簡形式（一篇 ~10-30K tokens），pdf2zh 路線按頁計（5000/page，20 頁論文 ≈ 100K+）——源碼路線通常省 3-5×；真比較需跑真實 API（無自動化測試，屬已知取捨）
- **缺 key 早期檢查**：translate 開頭（同 PptVisionAdapter 模式）
- **共用收攏（standards review）**：`_windowsify`/`_default_runner`（180s 逾時執行）跨模組偷私有違規 → 收攏為 `process_utils.windowsify/run_command`（PPT/LaTeX 兩引擎共用）；`llm_client.chat_completion`（siliconflow_vision 遷移共用）

### POC 驗證（2026-08-12）

真 xelatex 編譯 fixture（xeCJK＋`\setCJKmainfont{Microsoft JhengHei}`＋equation 公式）→ PDF 中文渲染成文字層（pymupdf 提取「論文翻譯測試/引言」）；全鏈 Fake 譯文（含中文前綴）→ 佔位還原 → 真編譯 → PDF 含中文譯文。slow 冒煙 2 passed（~3s，套件快取後）。

## 兩軸 review 紀錄

**Standards 軸**（1 硬違規＋5 判斷調全收）：
- 硬違規：`tex_compiler` 跨模組偷 `ppt_converter._windowsify`（`_` = module-private 慣例）→ `process_utils.py` 公開收攏（含同形 `_default_runner`）
- `LatexConfig.model` 死欄位（adapter 未傳 translator）→ 接上
- `LATEX_TIMEOUTS` 死 map（兩值皆 40）→ 單一 `LATEX_TIMEOUT`
- Data Clumps：`_translate_chunk/_translate_core` 解包 tuple → 回 TextTranslation 值物件
- docstring 宣稱實作「TeXCompilePort」但 ports.py 無宣告 → 補 `TeXCompilePort` Protocol（對齊 PptToImagePort/VisionTranslatorPort 慣例）
- 接受現狀：text_translation vs vision_translation 同形（票 14 review 已豁免同形模型鏈）；build_engine if 鏈（registry-driven 明文模式）

**Spec 軸**（3 AC 全過＋3 修正）：
- AC1 ✓ fixture 端到端（真 xelatex）；真實 LLM 以 FakeTranslator 取代（同票 14 模式，屬已知取捨）
- AC2 ✓ **缺口①修復**：`\[...\]`/`$$...$$` 段落間公式不在 `_INLINE_RE` 會裸送 LLM → 補上（`$$` 優先於 `$`，避免拆錯）＋roundtrip 測試；**缺口②修復**：itemize 內 `\item` 行被「\ 開頭 keep」擋住永不翻譯 → `\item ` 字首原封、內文可譯（同標題機制）
- AC3 ✓ 結構齊備（JobService 零改動）；「應低於 PDF 路線」以 token 量級論證（見設計決策）
- **reasoner 備援風險修復**：備援送 `temperature=0.1`——reasoner 官方不支援，送參數可能被拒＝備援鏈死 → 依 model 條件組裝＋測試
- 已知取捨：figure 環境整段 keep 含 caption（保守安全側，caption 常含 \ref/\cite 混合）；MiKTeX 首次編譯自動裝套件需網路

## 測試

370 passed（367→370，+3 spec review 守證），23.30s；slow 5 passed（含真 xelatex 冒煙 2，~3s）。新增：test_latex_parser.py（11）、test_llm_client.py（2）、test_latex_translator.py（7）、test_tex_compiler.py（9）、test_latex_adapter.py（7）、test_latex_smoke.py（2 slow）、test_engine_registry.py（+3）、test_cost_service.py（+1）。

**commit:** `d2c01a0`（票 15 完成：LaTeX 源碼路線（370 tests green），20 files，+1390/-42）
