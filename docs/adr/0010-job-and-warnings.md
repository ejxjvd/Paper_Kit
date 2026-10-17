# ADR 0010：結果同時攜帶 job 與 warnings

- 狀態：已採納
- 日期：2026-08-19
- 來源：`Paper_Kit_journal/2026-08-19-Paper_Kit-工作紀錄.md`〈架構審查：13 項設計決策〉（Q10）
- 決策方式：`/improve-codebase-architecture` 產出候選 → `/grilling` 兩輪 → 使用者裁決

## 背景

掃描件偵測、OCR 旗標無效等情況屬「警告但繼續」。

## 決策

回傳結果同時帶 job 與 warnings 清單。

## 替代方案與否決理由

只用例外或只回 job：前者把可繼續的情況當失敗，後者讓警告遺失。

## 後果

警告屬**領域判斷**而非 UI 判斷，任何前端都能一致呈現。
