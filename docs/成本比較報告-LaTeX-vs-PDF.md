# 成本比較報告：LaTeX 源碼 vs PDF 路線（票 15 驗證）

> 2026-08-12 實測。同一篇論文、同一 DeepSeek 端點（deepseek-chat）、同一計價基準，
> 自動化 harness 量測（`e2e/attention/run_real_api.py` vs `e2e/cost_compare/run_pdf_route.py`）。

## 實驗設定

| 項目 | LaTeX 源碼路線 | PDF 路線（pdf2zh_next） |
|---|---|---|
| 論文 | Attention Is All You Need（arXiv:1706.03762） | 同左 |
| 輸入 | `ms_single.tex`（7 個 \input 展開合併，73,907 字元） | `original.pdf`（arXiv 原 PDF，8 頁） |
| 引擎 | LatexAdapter → deepseek-chat | Pdf2zhNextAdapter（`uv tool run pdf2zh_next`）→ deepseek-chat |
| 目標語言 | zh-TW | zh-TW（--lang-out zh-TW） |

計價：deepseek-chat $0.00027/1K in、$0.0011/1K out、匯率 32。

## 結果

| 指標 | LaTeX 源碼 | PDF（pdf2zh） | 倍率 |
|---|---|---|---|
| tokens in | 15,095 | 76,706 | **5.1×** |
| tokens out | 5,843 | 26,867 | **4.6×** |
| 成本 | **US$0.0105 ≈ NT$0.34** | **US$0.0503 ≈ NT$1.61** | **4.7×** |
| 耗時 | 133s（翻譯） | 119.0s（全程） | — |
| 產出 | 14 頁中英 PDF | mono 16 頁 / dual 16 頁 | — |

## 結論

1. **票 15「源碼路線 3-5× 省」論證成立**：本篇實測 **4.7×**（input 5.1×／output 4.6×），
   落在論證區間上緣。源碼路線把 token 花在「純文字段」上——公式/環境/引用整段 keep
   （`\PKP{n}` 佔位還原），而 PDF 路線每頁都要 OCR＋版面分析＋全頁重排，token 耗用高 5 倍。
2. 兩條路線都極便宜：NT$0.34 vs NT$1.61，皆遠低於付費平台（DeepL ~NT$470/百頁）。
   PDF 路線的優勢是**零前置**（不用找源碼）；LaTeX 路線的優勢是**公式 100% 原樣**＋更省。
3. 頁數差異（14 vs 16）來自排版引擎差異，非資訊量差異。

## 註記（安全觀察）

- pdf2zh_next CLI 以 `--deepseek-api-key` 旗標接收 key → **process list 明文可見**
  （harness 運作中確認）。本測試未將 key 寫入任何 log/檔案（REPORT.json 不含 key），
  但此為該 CLI 介面的固有限制——日後 adapter 改進方向：改餵環境變數或設定檔。

## 產出

- `e2e/attention/REPORT.json`（LaTeX 路線）
- `e2e/cost_compare/PDF_ROUTE.json`（PDF 路線）
- `e2e/attention/original.zh-TW.{mono,dual}.pdf`（PDF 路線產物）

## 相關

- 手冊：`docs/LaTeX路線操作手冊.md` §6
- harness：`e2e/attention/run_real_api.py`、`e2e/cost_compare/run_pdf_route.py`
- 規格：`docs/tickets/15-LaTeX源碼路線.md`
