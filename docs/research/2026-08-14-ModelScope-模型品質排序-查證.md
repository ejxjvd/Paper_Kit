# ModelScope 免費 API 模型翻譯品質排序 — 查證報告

- **日期**：2026-08-14
- **用途**：Paper_Kit 翻譯應用之模型推薦依據（繁體中文翻譯場景優先）
- **範圍**：ModelScope 國際站（api-inference.modelscope.ai）免費可用、可生成之 **non-thinking chat 模型** 18 個
- **方法**：WebSearch / WebFetch 收集 2026 年公開評測（LMArena、MT 特化榜、WMT、FLORES、CSM-MTBench、JP-TL-Bench、HardMTBench、IFMTBench、通用能力榜），逐模型記錄來源、分數、日期

---

## 一、總排名（翻譯品質，Top 清單）

### T1 — 翻譯品質第一線（有直接翻譯評測證據或公認最強中文模型）

| 排名 | 模型 | 關鍵證據 | 建議定位 |
|---|---|---|---|
| 1 | **Qwen/Qwen3.5-397B-A17B** | **WMT25 en-zh 切片：GEMBA-DA 90.25 / xCOMET-XXL 65.21（nothink 版本）**，候選清單中唯一有 WMT25 官方測試集分數者；支援 201 語言（Qwen3 僅 119） | **首選**：最大參數量 + 最強直接證據 |
| 2 | **deepseek-ai/DeepSeek-V3.1** | LMArena Elo ~1418；JP-TL-Bench（日英）Terminus 版 9.85/9.93/9.89、勝率 90.9%；中文理解公認頂級 | 中文翻譯最強者之一；與 397B 並列第一線 |
| 3 | **Qwen/Qwen3-235B-A22B-Instruct-2507** | **CSM-MTBench（中文社群媒體翻譯）zh→es/fr/ja/ko/ru 平均 XCOMET 84.10**（zh→ja 86.57 最高）；LMArena Elo 1435±4.0 | 候選中唯一有 zh→X 翻譯專屬分數的模型 |

### T2 — 翻譯品質良好，但直接翻譯評測證據較弱（以通用能力推斷）

| 排名 | 模型 | 關鍵證據 | 備註 |
|---|---|---|---|
| 4 | **deepseek-ai/DeepSeek-V3.2-Exp** | V3.1 後繼（MMLU-Pro 85.0）；SemEval-2026 Task 7 跨 26 語言文化知識 MCQ 80.26；BrowseComp-zh 47.9 | 無直接翻譯評測，推斷為 T1 等級但誠實標註 |
| 5 | **Qwen/Qwen3.5-35B-A3B** | LMArena Elo 1396；同族新 Qwen3.6-35B-A3B 在 WMT25 en-zh 切片得 GEMBA-DA 90.03 / xCOMET 64.71（家族訊號強） | 參數小速度快，CP 值高 |
| 6 | **Qwen/Qwen3.5-27B** | LMArena Elo 1409（小模型最高）；GPQA 85.8、HLE 22.2、IFEval 95 | dense 27B，品質穩定但慢 |
| 7 | **PaddlePaddle/ERNIE-4.5-300B-A47B-PT** | CCBench（中文知識/文化）特強；LLM Kinship Arena 第 2（judge 準確率 83.0%）；第三方深測：語言生動性/資訊完整性四維度最佳 | 中文特化，但**無翻譯專屬分數**；長上下文弱（LCR 2.3%）不利長文翻譯 |
| 8 | **Qwen/Qwen3-Next-80B-A3B-Instruct** | RIKER 200K 長上下文第 1（82.7%）；RULER 1M 91.8%；GPQA 73.8 | 無翻譯評測；長上下文優勢利長文翻譯 |
| 9 | **stepfun-ai/Step-3.5-Flash** | AA 智能指數 38；AIME 2025 97.3%；LiveCodeBench v6 86.4% | 無翻譯評測；**注意：公開資料指其為推理型模型，翻譯時 max_tokens 耗盡風險需實測** |
| 10 | **Tencent-Hunyuan/Hy3** | 2026-07-06 發布，295B/21B active；GPQA 90.4、SWE-bench Verified 78.0、ClawEval 68.5 | 無翻譯評測；騰訊翻譯主力在 Hy-MT2（專用翻譯模型），Hy3 非翻譯特化 |
| 11 | **MiniMax/MiniMax-M1-80k** | MMLU-Pro 81.1–81.6；GPQA 69.7–70；1M 長上下文 | 無翻譯評測；**本身是推理型模型（hybrid-attention reasoning），max_tokens 耗盡風險需實測** |

### T3 — 翻譯品質低或證據不足（不建議優先）

| 排名 | 模型 | 關鍵證據 | 原因 |
|---|---|---|---|
| 12 | **Qwen/Qwen3.5-122B-A10B** | BenchAlign 多語言類別 36.8/100（13 個候選中第 9，33 百分位） | 多語言能力訊號偏弱；無翻譯專屬評測 |
| 13 | **PaddlePaddle/ERNIE-4.5-21B-A3B-PT** | **JP-TL-Bench（日英）：6.28/7.69/7.07、勝率僅 57.2%** | 候選中唯一有「直接翻譯弱勢」證據者；21B 小模型翻譯品質有限 |
| 14 | **Qwen/Qwen3-14B** | CEVAL 83.06；回譯研究顯示其對翻譯敏感（back-translated 中文邏輯推理反降 70.07→66.27） | 翻譯穩定性疑慮 |
| 15 | **Qwen/Qwen3-Coder-30B-A3B-Instruct** | SWE-bench Verified 51.9、LCB V6 77.2 | 程式碼特化模型，非翻譯用途；無翻譯評測 |
| 16 | **Qwen/Qwen3-8B** | CEVAL 79.27、MMLU 74.78；模型合併研究證實具低資源語言翻譯能力 | 參數最小，zh-en 無專屬證據 |
| 17 | **Shanghai_AI_Laboratory/Intern-S1** | 科學特化（AI4S，Qwen3-235B 基礎續訓 5T 科學 token）；無翻譯評測 | **科學模型，非通用對話/翻譯用途** |
| 18 | **Shanghai_AI_Laboratory/Intern-S1-mini** | 8B 科學模型：MMLU-Pro 74.8、GPQA 65.2、ChemBench 76.5；無翻譯評測 | 同上 |

---

## 二、各模型查證明細（來源、分數、日期）

### 1. deepseek-ai/DeepSeek-V3.1

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| LMArena Elo | ~1418 | llm-explorer.com（unsloth 開源版） | 2026 |
| LMArena 資料集（V3 系列） | 1354–1399 | huggingface.co/datasets/lmarena-ai/leaderboard-dataset | 2026-07-21 |
| JP-TL-Bench（日英翻譯）Terminus 版 | 9.85 / 9.93 / 9.89，勝率 90.9% | arXiv 2601.00223 | 2026-01 |
| 來回翻譯語意保留（8 模型排第 6） | 8.298 | github.com/lechmazur/translation | 2026 |
| MT-Bench（V3，Q1 2026） | 8.8 | LLM Model Comparison 2026 dataset | 2026-02 |

- 結論：**候選中中文能力公認最強之一**。JP-TL-Bench 顯示其翻譯品質位於頂級水準（勝率 90.9%），雖是日英方向，但對中英有高參考價值。WMT25 初步結果中 DeepSeek-V3 屬第二梯隊（緊隨 GPT-4.1 / Gemini-2.5-Pro）。無 zh-en 專屬官方分數。

### 2. deepseek-ai/DeepSeek-V3.2-Exp

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| MMLU-Pro | 85.0 | 官方 model card（aichina.news 轉載） | 2025-09 發布 |
| GPQA-Diamond | 79.9 | 同上 | 同上 |
| BrowseComp-zh | 47.9（V3.1-Terminus 45.0） | 同上 | 同上 |
| SWE-bench Multilingual | 57.9 | 同上 | 同上 |
| SemEval-2026 Task 7（26 語言/30 國文化知識） | SAQ 51.47 / MCQ 80.26 | aclanthology.org 2026.semeval-1.36 | 2026 |
| LEXam（社群提交） | 56.53 | huggingface.co 討論區 #38 | 2026 |

- 結論：**無任何直接翻譯評測**。多語言/跨文化能力訊號良好（SemEval-2026、BrowseComp-zh），與 V3.1 品質相當。誠實標註：翻譯品質為推斷，非實測。

### 3. Qwen/Qwen3-235B-A22B-Instruct-2507

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| **CSM-MTBench（中文社群媒體翻譯）** | zh→es 85.33 / zh→fr 82.39 / zh→ja 86.57 / zh→ko 84.63 / zh→ru 81.59，**平均 XCOMET 84.10** | arXiv 2601.22931 | 2026-01 |
| LMArena Elo（instruct-2507） | 1435±4.0（25.6K 票） | aitntnews.com / LMArena | 2026-08-04 |
| LMArena Elo（base） | ~1378 | 同上 | 同上 |
| GPQA-Diamond / MMLU-Pro / AIME 2025 | 70.0 / 82.8 / 82.0 | designforonline.com | 2026-04-23 |

- 結論：**候選中唯一有 zh→X（中文出發）翻譯專屬評測者**，平均 XCOMET 84.10 為 22 個受測系統中的中上水準。繁體中文場景高度相關（輸出方向為外文；若輸入繁體亦為其強項）。**T1 最有力候選之一**。

### 4. Qwen/Qwen3-Next-80B-A3B-Instruct

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| GPQA-Diamond | 73.8% | designforonline.com | 2026-03-14 |
| RIKER 長上下文 200K | 第 1（82.7%，幻覺率 10.2%） | Kamiwaza 部落格（RIKER，2026-01） | 2026-01 |
| RULER 1M | 91.8% | 同上 | 同上 |
| MoE 壓縮研究 IFeval / AIME25 | 93.4 / 80.0 | REAM/REAP 論文 | 2026 |

- 結論：**無翻譯專屬評測**。定位為長上下文冠軍（200K/1M），適合長文件翻譯；翻譯品質為推斷。

### 5. Qwen/Qwen3.5-122B-A10B

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| BenchAlign 多語言類別 | 36.8/100（13 個中第 9、33 百分位） | benchlm.ai | 2026-08 |
| BenchAlign 總榜 | #59/216（59.55/100） | 同上 | 2026-08 |
| qwen3.5-flash 中英互譯基礎測試（同族小模型） | 92/100 通過 | xsctbench.com l_multi_001 | 2026 |
| 詞表/語言支援 | 248K 詞表、201 語言 | SC117 model card | 2026 |

- 結論：多語言類別分數在候選中偏弱（第 9/13），與其宣傳的 201 語言支援有落差。同族 flash 的中英互譯 92 分只測基礎句。**翻譯定位 T3，誠實標註**。

### 6. Qwen/Qwen3.5-397B-A17B

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| **WMT25 en-zh 切片（nothink）** | **GEMBA-DA 90.25 / xCOMET-XXL 65.21** | HardMTBench，arXiv 2605.28315（22 系統對照） | 2026-05 |
| WMT25 en-zh 切片（think） | 87.05 / 62.71（反而較低，支援不開思考） | 同上 | 同上 |
| GPQA-Diamond | 88.4（官方）/ 89.3（Artificial Analysis） | Qwen model card / OpenRouter AA | 2026-02 發布 |
| AIME 2026 / SWE-bench Verified | 91.3 / 76.4 | 官方 | 2026-02 |
| 語言支援 | 201 語言（Qwen3 的 119 → 201） | Alibaba / SGLang docs | 2026-02 |

- 結論：**候選中翻譯直接證據最強者**。WMT25 en-zh 官方測試集上 nothink 版本 GEMBA-DA 90.25、xCOMET 65.21——xCOMET 高於 GPT-5.5 nothink（62.83），GEMBA 僅次於 Gemini 3.1 Pro（90.66）與 Qwen-MT-Plus（90.49）。**且 nothink（= non-thinking）版本分數高於 think 版本**，完美契合 ModelScope 非思考型用法。Hy-MT2 技術報告亦證實其 FLORES-200 表現僅次於騰訊專用翻譯模型。**翻譯品質首選**。

### 7. Qwen/Qwen3.5-35B-A3B

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| LMArena Elo | 1396 | lmmarketcap.com | 2026 |
| MMLU-Pro / GPQA | 85.3% / 84.5% | 同上 | 同上 |
| IFEval | 91.9% | phaseo.app | 2026 |
| 同族 Qwen3.6-35B-A3B WMT25 en-zh | GEMBA-DA 90.03 / xCOMET 64.71 | HardMTBench，arXiv 2605.28315 | 2026-05 |

- 結論：無本體翻譯評測，但**同族後繼 Qwen3.6-35B-A3B 在 WMT25 en-zh 表現優秀**（家族品質訊號）。35B-A3B 僅 3B active，速度極快、成本低，適合 Paper_Kit 大量翻譯場景。

### 8. Qwen/Qwen3.5-27B

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| LMArena Elo | 1409（小模型最高） | lmmarketcap.com | 2026 |
| GPQA / HLE | 85.8% / 22.2% | 同上 | 同上 |
| IFEval | 95（榜單領先） | phaseo.app | 2026 |
| TerminalBench Hard | 32.6% | 同上 | 同上 |

- 結論：dense 27B，小模型中通用品質最高（LMArena 1409 高於 35B-A3B 的 1396），但無翻譯專屬評測、生成速度慢（3.57 t/s @8GB 量化環境）。

### 9. Qwen/Qwen3-14B / Qwen3-8B

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| Qwen3-14B CEVAL / MMLU（BF16） | 83.06 / 78.90 | Tencent/AngelSlim GitHub | 2026 |
| Qwen3-8B CEVAL / MMLU（BF16） | 79.27 / 74.78 | 同上 | 同上 |
| Qwen3-8B 模型合併（低資源語種翻譯） | 具翻譯能力，方法依存 | arXiv 2603.28263 | 2026-03 |
| 回譯敏感度研究（Qwen3-14B） | 中文邏輯推理 70.07→66.27（回譯後反降） | arXiv 2606.17905 | 2026-06 |

- 結論：無 zh-en 翻譯專屬評測。Qwen3-14B 對「翻譯過程」敏感的研究結果值得注意（翻譯場景穩定性疑慮）。**T3**。

### 10. Qwen/Qwen3-Coder-30B-A3B-Instruct

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| SWE-bench Verified | 51.9 | InCoder-32B 論文（arXiv 2603.16790） | 2026-03 |
| LiveCodeBench V6 | 77.2（同論文另一表 36.0） | 同上 | 同上 |
| Multi-LCB 多語言程式 Pass@1 平均 | 30.6（低於非 Coder 版 Qwen3-30B-A3B 的 59.6 Pass@5） | arXiv 2606.20517 | 2026-06 |

- 結論：程式碼特化，**無翻譯評測且非翻譯用途**；多語言程式表現反而不如通用版 Qwen3-30B-A3B，翻譯品質不建議期待。**T3**。

### 11. PaddlePaddle/ERNIE-4.5-300B-A47B-PT

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| CCBench（中文知識/文化） | 特強（百度技術報告宣稱） | ERNIE Technical Report PDF | 2025-06 發布 |
| LLM Kinship Arena（中文親屬推理） | 第 2，39/47，judge 準確率 83.0% | github.com/matchyc/LLM-kinship-arena | 2026 |
| GPQA-Diamond / MMLU-Pro | 81.1% / 77.6% | benchmarklist.com | 2026 |
| LCR（長上下文） | 2.3%（#298–350，明顯弱） | datalearner.com / Design for Online | 2026 |
| 中文深測（Zeeklog，vs DeepSeek-R1/Qwen3-30B-A3B） | 語言生動性、資訊完整性、邏輯推理效率、生物醫學深度四維度最高 | zeeklog.com | 2026 |

- 結論：**中文特化明顯**（中文知識文化、生動性），翻譯風格可能較佳；但**無翻譯專屬分數**，且長上下文極弱（LCR 2.3%）——長文/論文翻譯（Paper_Kit 核心場景）風險高。**T2 邊緣**。

### 12. PaddlePaddle/ERNIE-4.5-21B-A3B-PT

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| **JP-TL-Bench（日英翻譯）** | **6.28 / 7.69 / 7.07，勝率 57.2%** | arXiv 2601.00223 | 2026-01 |
| MMLU / GSM8K / MATH-500 | 73.9 / 82.9 / 78.0 | EvoESAP 論文（arXiv 2603.06003） | 2026-03 |
| 函式呼叫 | 不支援 | 同上 | 同上 |

- 結論：**候選中唯一有「直接翻譯弱勢」量化證據者**——JP-TL-Bench 勝率 57.2%，遠低於 DeepSeek-V3.1-Terminus 的 90.9%。小參數（3B active）翻譯品質有限。**T3**。

### 13. stepfun-ai/Step-3.5-Flash

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| AA 智能指數 | 38（開源中位數 27） | artificialanalysis.ai | 2026 |
| AIME 2025 | 97.3% | 同上 | 2026-02 發布 |
| LiveCodeBench v6 / SWE-bench Verified | 86.4% / 74.4% | 同上 | 同上 |
| 推理冗長度 | 評測耗 200M reasoning tokens（對照中位數 17M） | 同上 | 同上 |

- 結論：品質頂級但**無翻譯評測**；196B/11B active 大模型。**重要警示**：公開資料稱其為「reasoning model」且極度冗長——ModelScope 上若走思考模式會重演 max_tokens 耗盡問題，需實測 non-thinking 端點。**T2**。

### 14. Tencent-Hunyuan/Hy3

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| 發布 | 2026-07-06（295B 總參數 / 21B active，Apache 2.0，256K context） | pandaily.com | 2026-07 |
| GPQA-Diamond | 90.4 | pandaily / 騰訊官方 | 2026-07 |
| SWE-bench Verified | 78.0 | 同上 | 同上 |
| ClawEval pass³ / BrowseComp / DeepSearchQA | 68.5 / 84.2 / 91.0 | 同上 | 同上 |
| OpenRouter 週呼叫量 | 第 1 | stock.finance.sina.com.cn | 2026-07-13 |

- 結論：通用能力 T1 等級（GPQA 90.4、SWE-bench 78.0），但**完全沒有翻譯評測**。騰訊翻譯能力集中在 **Hy-MT2**（專用 MT 模型，WMT25 XCOMET-XXL 73.60、FLORES-200 87.47，2026-05-21 開源）——Hy3 本體非翻譯特化。**T2，翻譯品質為純推斷**。

### 15. Shanghai_AI_Laboratory/Intern-S1 / Intern-S1-mini

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| Intern-S1 定位 | 科學多模態模型（Qwen3-235B 基礎 + 6B 視覺編碼器，5T token 科學續訓） | Intern-S1 論文 arXiv 2508.15763 | 2025-07-26 發布 |
| Intern-S1-mini MMLU-Pro / GPQA / IFEval | 74.8 / 65.2 / 81.2 | shlab.org.cn / 論文 | 2025-08-21 發布 |
| Intern-S1-mini ChemBench（化學） | 76.5（開源最佳，+14.1） | 同上 | 同上 |
| Intern-S1-Pro（2026-02 萬億版） | MMLU-Pro 86.6、AIME-2025 93.1 | shlab.org.cn / pandaily | 2026-02-04 |

- 結論：**科學（AI4S）特化模型**，非通用對話模型。查無任何翻譯評測；通用 MMLU-Pro 分數（mini 74.8）屬中下。ModelScope 上的 Intern-S1 若為科學特化版，翻譯品質不建議期待。**T3，查無翻譯資料**。

### 16. MiniMax/MiniMax-M1-80k

| 項目 | 分數 | 來源 | 日期 |
|---|---|---|---|
| MMLU-Pro | 81.1–81.6% | benchmarklist.com / llm-stats | 2025-06-16 發布 |
| GPQA-Diamond | 69.7–70% | 同上 | 同上 |
| MATH-500 / AIME 2025 | 96.8–98% / 61.0–76.9% | 同上 | 同上 |
| 長上下文 | 1M context（官方宣稱全球第二，僅次 Gemini 2.5 Pro） | minimax.io | 2025-06 |

- 結論：**無翻譯評測**。**重要警示**：M1 官方定位為「hybrid-attention reasoning model」——與其他思考型模型同類，ModelScope 版若保留思考行為，max_tokens 耗盡風險高；且作為 2025-06 舊模型，品質已被同代 2026 模型超越（MiniMax M2 全面勝出）。**T2 邊緣，誠實標註**。

---

## 三、查無可靠評測資料的模型（誠實標註）

| 模型 | 狀態 |
|---|---|
| **DeepSeek-V3.2-Exp** | 有通用/多語言評測，**無任何直接翻譯評測** |
| **Qwen3-Next-80B-A3B-Instruct** | 無翻譯評測（僅長上下文/通用） |
| **Qwen3.5-35B-A3B** | 本體無翻譯評測（僅同族 Qwen3.6-35B-A3B 有 WMT25 分數） |
| **Qwen3.5-27B** | 無翻譯評測 |
| **Qwen3-14B / Qwen3-8B** | 無 zh-en 翻譯評測 |
| **Qwen3-Coder-30B-A3B-Instruct** | 無翻譯評測（且非翻譯用途） |
| **ERNIE-4.5-300B-A47B-PT** | 無翻譯專屬評測（中文品質訊號強） |
| **Step-3.5-Flash** | 無翻譯評測 |
| **Tencent-Hunyuan/Hy3** | 無翻譯評測（騰訊翻譯能力在 Hy-MT2 專用模型） |
| **Intern-S1 / Intern-S1-mini** | 無翻譯評測（科學特化） |
| **MiniMax-M1-80k** | 無翻譯評測 |

**FuguMT 評測**：2026 年公開網域查無 FuguMT 榜單資料（搜尋 4 組關鍵字皆無結果）——無法引用，已列入本報告方法限制。

**LMArena 翻譯類別榜**：LMArena 確有語言別榜單（含中文），但 2026-08 抓取到的公開資料無 zh-en 翻譯類別 Elo 明細；step-3.5-flash、qwen3.5-35b-a3b 等僅出現在 text_style_control 等非翻譯類別（Elo 1365–1390 區間）。

---

## 四、方法限制與注意事項

1. **繁體中文（zh-TW）缺口**：所有找到的評測均為簡體中文或 zh-en 對譯，**無任何模型有 zh-TW（繁體）輸出品質專屬評測**。Qwen 系（明確支援繁體）、DeepSeek 系通常能正確輸出繁體，但推薦前建議 Paper_Kit 做 20 句抽樣實測。
2. **思考型風險**：Step-3.5-Flash 與 MiniMax-M1-80k 公開資料均標為 reasoning 模型——若 ModelScope 端點保留思考行為，會重演 max_tokens 耗盡。需以實際 API 測試確認 non-thinking 行為（與 DeepSeek-V4-Pro、GLM-5.2、Qwen3-*-Thinking 同類處理）。
3. **WMT25 en-zh 切片注意**：HardMTBench（arXiv 2605.28315）為獨立研究論文之 WMT25 切片評測（GEMBA-DA + xCOMET-XXL），非 WMT 官方人類評測；官方 WMT25 human 評測結果未見 zh-en 對外分數細目。xCOMET 對 Hy-MT2 系有利的偏差（term accuracy 低但 xCOMET 高）亦須留意。
4. **供應商自報分數**：Qwen3.5-397B、Hy3 等官方分數（AIME、GPQA）多為自家 scaffold 測量，獨立複現有限——翻譯結論主要依賴翻譯專屬評測（CSM-MTBench、JP-TL-Bench、HardMTBench/WMT25），通用分數僅作輔證。
5. **模型發布時間**：Hy3（2026-07-06）為最新；Qwen3.5 系列（2026-02）、DeepSeek-V3.2-Exp（2025-09）次之；MiniMax-M1（2025-06）與 Intern-S1 系列偏舊。翻譯品質排序已隱含時間加權。

---

## 五、來源清單（含日期）

### 翻譯專屬評測
1. HardMTBench: Stress-Testing Chinese-English Translation on Knowledge-Intensive Domains — arXiv 2605.28315（2026-05）。WMT25 en-zh 切片：GEMBA-DA / xCOMET-XXL 22 系統對照。https://ar5iv.labs.arxiv.org/html/2605.28315
2. Benchmarking Machine Translation on Chinese Social Media Texts（CSM-MTBench）— arXiv 2601.22931（2026-01）。Qwen3-235B-A22B zh→5 語 XCOMET。https://ar5iv.labs.arxiv.org/html/2601.22931
3. JP-TL-Bench: Anchored Pairwise LLM Evaluation for Bidirectional Japanese-English Translation — arXiv 2601.00223（2026-01）。DeepSeek-V3.1-Terminus 90.9% 勝率；ERNIE-4.5-21B-A3B-PT 57.2%。https://ar5iv.labs.arxiv.org/html/2601.00223
4. Hy-MT2 Technical Report — arXiv 2605.22064 相關報導（2026-05-21）。FLORES-200 / WMT25 XCOMET-XXL 對照（Hy-MT2-30B-A3B 73.60 居首，勝過 DeepSeek-V4-Pro、Qwen3.5-397B-A17B）。https://github.com/Tencent-Hunyuan/Hy-MT2
5. IFMTBench — arXiv 2605.28218（2026-05）。多語言翻譯指令遵循評測。https://arxiv-org.ezproxy.obspm.fr/html/2605.28218
6. WMT25 General MT Shared Task Findings（2025-11）＋ Slator 初步結果（2025-08）。Gemini-2.5-Pro / GPT-4.1 領先；DeepSeek-V3 第二梯隊。https://slator.com/wmt25-preliminary-results-gemini-2-5-pro-gpt-4-1-lead-ai-translation/
7. WMT24++ 55 語言擴展（arXiv 2502.12404）：LLM 為所有 55 語言最佳 MT 系統。https://arxiv.deeppaper.ai/papers/2502.12404v1/similar

### 通用評測 / Arena
8. LMArena leaderboard dataset（Elo 1354–1435 區間）— huggingface.co/datasets/lmarena-ai/leaderboard-dataset（2026-07-21 版）。
9. AITNT LMArena 長文本問答排行榜（qwen3-235b-a22b-instruct-2507 Elo 1435±4.0；2026-08-04）。https://www.aitntnews.com/arena/org/alibaba/longer_query/
10. LLM Explorer（DeepSeek V3.1 Elo 1418）。https://llm-explorer.com/model/unsloth%2FDeepSeek-V3.1,1dCbcPaCmvt1Zzj4yAhvxd
11. LMMarketCap Qwen3.5-27B vs 35B-A3B 對比（Elo 1409 vs 1396；2026）。https://lmmarketcap.com/compare/qwen-qwen3-5-27b/vs/qwen-qwen3-5-35b-a3b
12. BenchLM / BenchAlign（Qwen3.5-122B-A10B 多語言 36.8/100；2026-08）。https://benchlm.ai/models/qwen3-5-122b-a10b
13. Artificial Analysis（Step-3.5-Flash 智能指數 38；2026）。https://artificialanalysis.ai/models/step-3-5-flash/providers

### 模型官方/技術報告
14. DeepSeek-V3.2-Exp model card 分數表（AICHINA.news 轉載，2025-09 發布）。https://aichina.news/models/deepseek-ai/DeepSeek-V3.2-Exp/
15. ERNIE Technical Report（CCBench 中文特強；2025-06）。https://ernie.baidu.com/blog/publication/ERNIE_Technical_Report.pdf
16. Intern-S1 論文（arXiv 2508.15763；2025-07-26）與 Intern-S1-mini 發布（shlab.org.cn，2025-08-21）、Intern-S1-Pro（shlab.org.cn，2026-02-04）。
17. MiniMax-M1 官方（2025-06-16）。https://www.minimax.io/news/minimaxm1
18. 騰訊 Hy3 發布報導 — pandaily（2026-07-06）。https://pandaily.com/tencent-hunyuan-hy3-launch-agent-90-percent-task-resolution-jul2026-v2
19. Qwen3.5 官方/多語支援（201 語言；2026-02）。https://www.morphllm.com/qwen-3-5

### 其他輔證
20. XSCT Bench 中英互譯（qwen3.5-flash 92/100；2026）。https://xsctbench.com/testcase/l_multi_001/qwen3.5-flash
21. Tencent/AngelSlim 量化基準（Qwen3-14B/8B CEVAL；2026）。https://github.com/Tencent/AngelSlim
22. 回譯與中文邏輯推理（arXiv 2606.17905；2026-06）。https://arxiv-org.ezproxy.obspm.fr/html/2606.17905
23. 多語合併翻譯（arXiv 2603.28263；2026-03）。https://huggingface.co/buckets/huggingchat/papers-content/tree/2603/2603.28263.md
24. LMArena Review（語言別榜單存在性佐證；2026-04 更新）。https://www.toolcenter.ai/en/articles/lmarena-review-2026
25. 來回翻譯語意保留基準（GitHub lechmazur/translation；2026）。https://github.com/lechmazur/translation
26. LLM Model Comparison 2026（DeepSeek V3 MT-Bench 8.8；2026-02-18）。https://huggingface.co/api/resolve-cache/datasets/salttechno/LLM-Model-Comparison-2026
27. Zeeklog 文心 4.5 中文深測（2026）。https://zeeklog.com/bai-du-kai-yuan-wen-xin-4-5-xi-lie-kai-yuan-da-mo-xing-gitcode-ben-di-hua-bu-shu-huo-ji-liu-dong-wen-xin-vs-deepseek-vs-qwen-3-0-shen-du-ce-ping-2

---

## 六、給 Paper_Kit 的推薦結論（一句版）

1. **預設首選 Qwen3.5-397B-A17B**：候選中唯一有 WMT25 en-zh 官方測試集分數者（GEMBA-DA 90.25 / xCOMET 65.21），且 nothink 版本勝過 think 版本——與 ModelScope 非思考型用法完全契合；201 語言支援含繁體中文。
2. **其次 DeepSeek-V3.1 / Qwen3-235B-A22B-Instruct-2507**：前者中文公認最強（JP-TL-Bench 90.9% 勝率），後者是唯一有 zh→X 專屬翻譯分數者（CSM-MTBench XCOMET 84.10）。
3. **成本敏感場景**：Qwen3.5-35B-A3B（3B active，速度快 2.4 倍、成本低 34%）為最佳折衷；Qwen3.5-27B 次之。
4. **避免**：ERNIE-4.5-21B-A3B-PT（JP-TL-Bench 勝率僅 57.2%）、Intern-S1 系列（科學特化）、Qwen3-Coder-30B（程式特化）。
5. **上線前必做**：20–50 句繁體中文樣本實測（含長文/論文段落），並確認 Step-3.5-Flash、MiniMax-M1-80k 在 ModelScope 端點無思考 token 行為。

---

## 七、實測補強（2026-08-14 晚，驗證紀律：真 runner、真 API、產出存在）

### 7.1 真翻譯全測（14 候選 × fixture paper_p34.pdf 2 頁 → zh-TW）

| 模型 | 真翻譯 | 產出（mono/dual） | 判定 |
|---|---|---|---|
| **deepseek-ai/DeepSeek-V3.1** | ✅ **23.1s** | 484KB/869KB | 可用 |
| **Qwen/Qwen3-235B-A22B-Instruct-2507** | ✅ 48.3s | 499KB/885KB | 可用 |
| **MiniMax/MiniMax-M1-80k** | ✅ 50.6s | 483KB/868KB | 可用（reasoning 風險未現） |
| **deepseek-ai/DeepSeek-V3.2-Exp** | ✅ 51.6s | 482KB/867KB | 可用 |
| Qwen/Qwen3-Next-80B-A3B-Instruct | ✅ 37.7s | 482KB/868KB | 可用 |
| Qwen/Qwen3.5-397B-A17B | ✅ 175.9s | 482KB/868KB | 可用但**冗長** |
| Qwen/Qwen3.5-122B-A10B | ✅ 206.2s | 483KB/868KB | 可用但**冗長** |
| Qwen/Qwen3.5-35B-A3B | ✅ 208.4s | 482KB/867KB | 可用但**冗長** |
| Qwen/Qwen3.5-27B | ❌ 445s 逾時 | — | **不可用**（dense 太慢） |
| stepfun-ai/Step-3.5-Flash | ❌ 327s 逾時 | — | **不可用**（reasoning 冗長） |
| PaddlePaddle/ERNIE-4.5-300B/21B、Hy3、Intern-S1 | ❌ 空殼 200 | — | **不可用**（未授權） |

### 7.2 標準化速度測量（固定長度英文摘要→繁中；量測總延遲、tokens/s、in/out tokens）

| 模型 | tok/s | 輸出 tokens（標準 prompt） | 冗長度 |
|---|---|---|---|
| Qwen3.5-397B-A17B | 110.6 | **4,948** | ⚠️ 冗長（23×） |
| Qwen3-Next-80B-A3B | 105.8 | 218 | ✅ 精簡 |
| Qwen3.5-122B-A10B | 102.0 | **5,465** | ⚠️ 冗長（26×） |
| Qwen3.5-35B-A3B | 101.8 | **6,778** | ⚠️ 冗長（32×） |
| Step-3.5-Flash | 97.6 | **2,000 截斷** | ❌ 極冗長 |
| MiniMax-M1-80k | 84.0 | 675 | ⚠️ 中等（3×） |
| DeepSeek-V3.1 | 42.2 | 168 | ✅ 精簡 |
| Qwen3-235B-2507 | 39.9 | 227 | ✅ 精簡 |
| DeepSeek-V3.2-Exp | 29.7 | 196 | ✅ 精簡 |

### 7.3 關鍵發現

1. **冗長度決定真翻譯時間**：Qwen3.5 系（397B/122B/35B）tok/s 高（100+）但**輸出量是正常模型 23–32 倍**（4.9K–6.8K tokens vs 精簡系 168–227）→ 真翻譯 176–208s。**「慢」的真相是話多，不是速度慢**——且 token 成本同比例放大（免費層無成本，但付費場景＝價格 ×25）。
2. **DeepSeek 系精簡王者**：tok/s 低（30–42）但輸出精簡（168–227）→ 真翻譯反而最快（23–52s）。
3. **Step-3.5-Flash 思考型陷阱實證**：標準化短翻譯輸出 2,000 tokens 被 max_tokens 截斷（reasoning 冗長）——真翻譯 327s 逾時原因確認。MiniMax-M1-80k 實測 675 tokens 無截斷（reasoning 風險未現，可用）。
4. **空殼群組確立**（「登錄但未提供服務」，HTTP 200 choices=null）：PaddlePaddle ERNIE×2、Tencent Hy3、上海 AI 實驗室 Intern-S1、zai-org/GLM-4.7-Flash 共 **5 個**。Paper_Kit preflight 誤將空殼診斷為 401——診斷邏輯待修正（見 [[待解問題]]）。
5. **綜合結論（品質>速度，速度不可太慢）**：**DeepSeek-V3.1 綜合最佳**（品質 T1 中文最強＋真翻譯最快 23.1s＋精簡）——registry 預設即此，**驗證正確**。次選 Qwen3-235B-2507（T1 zh→X 分數＋48.3s＋精簡）；速度敏感場景 Qwen3-Next-80B（105.8 tok/s 且精簡 218 tok）。Qwen3.5-397B 品質最高但冗長 23×——僅在「品質優先且可等 3 分鐘/2 頁」時選。
