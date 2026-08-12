# LaTeX 路線操作手冊（Paper_Kit）

> 2026-08-12 真論文端到端實測定版（arXiv:1706.03762，「Attention Is All You Need」）
> 實測結果：**NT$0.34 / 14 頁中英 PDF / 2 分 13 秒**（DeepSeek，386 tests 全綠）

## 1. 安裝前置

```bash
# MiKTeX（Windows，xelatex 必備）——winget 裝 per-user
winget install MiKTeX.MiKTeX

# uv（pdf2zh 路線才需要；LaTeX 路線可跳過）
curl -LsSf https://astral.sh/uv/install.sh | sh   # 裝到 ~/.local/bin/
```

驗證：`xelatex --version` 有輸出、`wsl -e bash -c 'which xelatex'` 找得到
（本機：`AppData/Local/Programs/MiKTeX/miktex/bin/x64/xelatex.exe`）。
MiKTeX 編譯缺套件時會**自動安裝**（adapter 已帶 `--enable-installer`，不彈 GUI）。

## 2. API key 設定

key 存本機 SQLite `~/.paper_kit/paper_kit.db`（**不上雲、不入 Vault**），
引擎槽位 `latex`（缺則共用 `deepseek`，同端點）：

```bash
cd /mnt/c/Users/qaref/Code/Paper_Kit
.venv/bin/python -c "
from paper_kit.application.settings_service import SettingsService
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
import pathlib
svc = SettingsService(SqliteSettingsRepository(pathlib.Path.home()/'.paper_kit'/'paper_kit.db'))
svc.set_api_key('deepseek', 'sk-...')   # 回讀只顯示前 6 碼
"
```

## 3. UI 操作（NiceGUI）

```bash
cd /mnt/c/Users/qaref/Code/Paper_Kit
.venv/bin/paper-kit          # → http://localhost:8080
```

- 上傳 `.tex` 檔（或多檔論文：先自行合併，見 §4）
- 選目標語言（zh-TW 等）＋引擎（latex）
- 執行 → 產出編譯 PDF（mono）；tokens 自動記入成本歷史
- 取消鈕中途可停（分段迴圈檢查旗標）

## 4. 真論文翻譯流程（多檔 arXiv 源碼）

arXiv e-print 是 tar.gz（主檔 + 分章 `\input` + `.sty` + Figures/）：

```bash
# 1) 下載 e-print（源碼版）
curl -sL -o paper.tar.gz https://arxiv.org/e-print/1706.03762
tar xzf paper.tar.gz

# 2) 展開 \input 合併成單一 .tex（e2e 工具）
.venv/bin/python -c "
import sys; sys.path.insert(0, 'e2e/attention')
from merge_inputs import expand_inputs
open('ms_single.tex','w',encoding='utf-8').write(
    expand_inputs('paper_src_dir', 'ms.tex'))
"

# 3) 送 UI / adapter 翻譯（源碼目錄會自動當 cwd——sty/Figures 第一順位搜尋）
```

合併工具特性：遞迴展開、環偵測、註解感知（`%` 後的 `\input` 不展開）、
行內 `\input` 支援。合併後檢查：無 `\input` 殘留、`\begin{document}` 恰一對。

## 5. 管線內部（自動處理，免人工）

| 階段 | 處理 |
|---|---|
| 分段 | 環境（equation/figure/...）整段 keep；純文字合併成段翻譯 |
| 佔位 | 行內公式/`\cite`/`\ref` 抽成 `\PKP{n}`（LLM 不得改動）→ 譯後原樣還原 |
| 標題 | `\section{}` 等只翻花括號內文、指令字首原封 |
| 混合行 | `\paragraph{Decoder:}正文...` 整段送（短標題單獨送會 LLM 幻覺） |
| 圍欄剝離 | LLM 回傳 ` ```latex ` 圍欄自動剝除 |
| 幻覺防護 | 譯文殘留無效 `\PKP` → 自動重試一次，兩次異常才失敗 |
| CJK 注入 | 英文原文無 CJK 支援 → 自動加 xeCJK + Microsoft JhengHei |
| 編譯 | xelatex nonstopmode + MiKTeX 自動裝套件；cwd = 源碼目錄 |

## 6. 成本與效能（實測）

| 路線 | tokens（in/out） | 成本 | 耗時 |
|---|---|---|---|
| LaTeX 源碼 | 15,095 / 5,843 | **US$0.0105 ≈ NT$0.34** | 133s |
| PDF（pdf2zh） | 76,706 / 26,867 | **US$0.0503 ≈ NT$1.61** | 119s |

同篇論文實測：**LaTeX 源碼比 PDF 路線省 4.7×**（源碼只翻純文字段，
公式/環境整段 keep；PDF 每頁 OCR＋版面分析）。詳見成本比較報告
`docs/成本比較報告-LaTeX-vs-PDF.md`。

計價：deepseek-chat $0.00027 / 1K in、$0.0011 / 1K out、匯率 32。
估論文（~7K tokens）NT$2 內；本篇實測 NT$0.34。

## 7. 疑難排解

| 症狀 | 原因 | 解方 |
|---|---|---|
| `Undefined control sequence` + 譯文含 `\PKP` | LLM 幻覺/佔位未還原 | 已自動重試；再現即「佔位符未還原」錯誤——重跑一次 |
| `nips_2017.sty not found` | 附屬檔不在 cwd | 確保源碼目錄傳給 include_dirs（UI 自動） |
| 中文變 □□ / 未渲染 | 原文無 xeCJK | 已自動注入（含中文即觸發） |
| `\AND undefined` | author 區塊被 LLM 重排 | 已整段 keep（不送翻譯） |
| xelatex 讀 PDF 當輸入 | 誤把 mono_path 當 .tex | harness 已修（with_suffix(".tex")） |
| 缺套件彈 GUI 卡住 | MiKTeX 安裝提示 | `--enable-installer` 已內建 |

## 8. 相關

- 源碼：`src/paper_kit/infrastructure/{latex_adapter,latex_parser,latex_translator,tex_compiler}.py`
- e2e：`e2e/attention/`（合併工具、run_real_api.py、REPORT.json）
- 規格：docs/tickets/15-LaTeX源碼路線.md
