# 15 — Phase 2：LaTeX 源碼路線

**What to build:** 有 .tex 源碼的論文走殺手級路線：翻 .tex（公式指令原封保留）→ xelatex 編譯 → 100% 公式與排版保真、token 最省。

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] .tex 上傳→翻譯（公式指令保留）→ xelatex 產出 PDF（fixture .tex 驗證）
- [ ] 公式 100% 原樣、中文可編譯（xeCJK）
- [ ] 成本記錄（應低於 PDF 路線）
