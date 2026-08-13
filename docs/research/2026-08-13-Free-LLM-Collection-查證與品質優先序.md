# Free-LLM-Collection 查證與品質優先序（PDF 翻譯用途）

> 查證日期：**2026-08-13**。對象：GitHub [for-the-zero/Free-LLM-Collection](https://github.com/for-the-zero/Free-LLM-Collection) README 所列 25 個免費 LLM API 提供者（重點為候選 1–8，其餘速覽）。
> 目的：為 Paper_Kit（pdf2zh-next `--openai` + 自訂 base-url）挑選**真正可用的免費 LLM 引擎**，並依翻譯品質排出優先序。
> 方法：WebSearch/WebFetch，優先官方文件（docs.siliconflow.cn、huggingface.co/docs、build.nvidia.com、docs.bigmodel.cn）與可信評測源（Artificial Analysis、LMArena/DataLearner 鏡像、llm-stats、WMT25 人工評測、JP-TL-Bench、Alconost MQM）。所有額度數字為 2026-08 當下可得版本；生態變動極快，落地前以各平台控制台為準。

**與既有報告的銜接**：本報告為《[免費LLM-API-分析與套用評估.md](./免費LLM-API-分析與套用評估.md)》（#28，同日）的互補——#28 從「省錢價值」角度否決多數方案；本報告從「免費層是否真的存在＋品質排序」角度補足查證，並沿用其工作負載基準：

- 58 頁論文：**300–600 次 API 呼叫／本**，input 165k–310k tokens、output 51k–87k tokens（#28 §一）
- 每日多本作業：可達 **1,200+ 次呼叫／天**
- 紅線（#28 §三、§四）：未發表論文**不可**送入有「資料訓練」條款的免費層（Gemini 免費層、Mistral 等）

---

## 1. 模型品質總定位（先給結論）

各免費端可用模型以 2026-08 可得評測數據排位。數據來源於 [Artificial Analysis Intelligence Index](https://artificialanalysis.ai/)（v4.0/v4.1，版本不可跨比）、[LMArena 文字生成榜](https://www.datalearner.com/en/leaderboards/external/text-generation?isChina=1)（2026-08-01 數據）、[llm-stats](https://llm-stats.com/)、[WMT25 人工評測](https://awesomeagents.ai/leaderboards/translation-benchmarks-leaderboard/)與 [JP-TL-Bench](https://benchmarklist.com/benchmarks/jp_tl_bench_anchored_pairwise_llm_evaluation_for_bidirectional_japanese_english_translation/)。

### 翻譯/多語言/長文本相關定位

| 排名 | 模型 | 品質依據（2026-08） | 翻譯/多語言/長文註記 | 免費端點 |
|---|---|---|---|---|
| T1 | **Kimi-K2.6** | AA Index **54**，開放模型 **#1** | 開放模型品質天花板 | NVIDIA NIM、HF router |
| T1 | **DeepSeek-V4-Pro** | AA Index **52–53**（0813 build 53），開放模型 **#2**；LMArena 文字第 47 名 Elo 1,458；GPQA-Diamond 89.6%（開放 #2）；SimpleQA 57%（開放 #1）；1M context | 中文能力第一梯隊，長上下文 | **ModelScope**、HF router（付費） |
| T1 | **GLM-5.1** | AA Index **51.4**（與 V4 Pro 幾近持平）；GPQA 85.5%；Tau-2 工具使用 97.7%（開放頂尖）；203K context | 中文輸出強、速度快（57.9 vs 30.5 tok/s） | **ModelScope**、HF router（付費） |
| T1 | **Qwen3-235B-A22B** | GPQA 80%（開放 #9）；**JP-TL-Bench 9.93**（僅次 Gemini 家族）；SimpleQA 50.1%（開放 #2） | 多語言（含日文）實測最佳開放模型之一 | **ModelScope** |
| T2 | **GLM-5.2** | AA Index 53（與 V4 Pro 0813 併列） | 旗艦級 | NVIDIA NIM（免費端！） |
| T2 | **DeepSeek-V4-Flash** | AA Index 較 V4-Pro 低約 1 分；LMArena coding 84 名 | 1M context、284B/13B active，專為 agent/長文設計 | **NVIDIA NIM（免費端）**、ModelScope |
| T2 | **gpt-oss-120b** | GPQA 80.1%、MMLU 89.7%、SWE-bench 63.2%（[llm-stats](https://llm-stats.com/models/compare/gpt-oss-120b-vs-gpt-oss-20b)）；131K context | 單 GPU 級最強開放推理模型；LMArena 無大樣本數據 | **Groq**、OpenRouter 付費 |
| T2 | **gemma-4-31b-it** | LMArena Elo ~1,451（綜合第 54/55 名）；**262K context** | 長文友好；Gemini 免費端 1,500 RPD | **Gemini 免費端**、OpenRouter :free |
| T2 | **nemotron-3-super-120b-a12b** | AA Index 25（同尺寸開放中上）；GPQA 80–82.7%；RULER 長文 91.8%；**WMT24++ 翻譯 86.7%**（[AA 頁面](https://artificialanalysis.ai/models/nvidia-nemotron-3-super-120b-a12b)） | 免費模型群中**翻譯分數最好**的一支；262K context | **OpenRouter :free** |
| T3 | **gpt-oss-20b** | GPQA 71.5%；整體較 120B 低 5–10% | 快、省電；輸出上限 32K | OpenRouter :free、Groq |
| T3 | **GLM-4.7-Flash**（30B/3B） | 官方宣稱同尺寸 SOTA（[發布稿](https://www.donews.com/news/detail/1/6383822.html)）；但第三方 ReLE 實測**大幅退步**（63.0%→55.5%，語言與指令遵從 -16.6%，回應時間 63s→1,238s，見 [NoneLinear 實測](https://blogs.nonelinear.com/blog/glm-4-7-flash-performance-5968f36df545)） | 翻譯用途**須先實測**；官方免費、無 token 上限 | **Bigmodel** |
| T4 | **GLM-4-9B / Qwen3-8B / DeepSeek-R1-0528-Qwen3-8B** | 9B 級；2026-04 的 95 語言評測 qwen3:8b 約 5.5/10（[futureagi](https://futureagi.com/blog/evaluating-llm-translation-quality-2026/)） | 短段落中英可、複雜技術長文吃力 | **SiliconFlow** |

**翻譯情境速評**：WMT25 人工評測前四為 Gemini 2.5 Pro > GPT-4.1 > … > DeepSeek-V3（第 4）（[來源](https://awesomeagents.ai/tools/best-ai-translation-tools-2026/)）；開放模型中最接近該水準的免費可達組合為 **NVIDIA 免費端的 DeepSeek-V4-Flash / GLM-5.2 / Kimi-K2.6** 與 **ModelScope 的 V4-Pro / GLM-5.1**。

---

## 2. 提供者逐項查證（1–8）

### 2.1 SiliconFlow 硅基流動 — ★★★☆☆

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。**9B 以下模型永久免費、無 token 費用**；新用戶註冊贈 2,000 萬 token（永久有效）（[yangmao.ai 免費模型清單](https://yangmao.ai/zh/blog/siliconflow-free-models-list/)） |
| Key 取得 | 手機號/Google/GitHub 註冊，**需實名認證**才能用全部免費模型；控制台 cloud.siliconflow.cn 建 key（[官方 FAQ](https://docs.siliconflow.cn/cn/faqs/misc_rate)） |
| 額度 | **L0 級別（月消費 <¥50）＝每模型 RPM 1,000 / TPM 50,000**，與 repo 一致；免費模型限流為固定值、不隨等級提升（[官方 Rate Limits 文件](https://docs.siliconflow.cn/cn/userguide/rate-limits/rate-limit-and-upgradation)）；第三方另載免費用戶約 60 RPM，以控制台為準 |
| 綁卡 | ❌ 不需要 |
| 可用免費模型 | `Qwen/Qwen3-8B`、`Qwen/Qwen3.5-4B`、`THUDM/GLM-4-9B-0414`、`THUDM/GLM-Z1-9B-0414`、`deepseek-ai/DeepSeek-R1-0528-Qwen3-8B`、`THUDM/GLM-4.1V-9B-Thinking` 等 |
| 品質定位 | T4 小模型層級；單次生成 max_tokens 常見上限 4,096（第三方），靠 pdf2zh 分塊可繞 |
| 推薦理由/風險 | 速率最慷慨、中文平台穩定；**瓶頸是模型品質**——9B 級翻技術論文易出錯，只宜做次要/實驗引擎 |

### 2.2 OpenRouter — ★★★★☆

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。`:free` 後綴模型免費、免綁卡；目前約 28–29 個免費模型（[OpenRouter 官方比較文](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)） |
| Key 取得 | openrouter.ai 註冊即得，無需卡 |
| 額度 | **20 RPM 固定**；每日額度＝**50 req/day（帳戶消費 <$10）**，**一次性充值 $10 → 1,000 req/day**（[pricepertoken](https://pricepertoken.com/endpoints/openrouter/free)、[NanoGPT 429 分析](https://nano-gpt.com/blog/openrouter-429-rate-limits-recovery)）。⚠️ **repo 宣稱的「200 RPD」未被任何來源支持**，極可能是舊數據 |
| 可用免費模型 | `openai/gpt-oss-20b:free`、`google/gemma-4-31b-it:free`、`google/gemma-4-26b-a4b-it:free`、`nvidia/nemotron-3-super-120b-a12b:free`、`nvidia/nemotron-3-ultra-550b-a55b:free` 等 |
| 品質定位 | T2：**nemotron-3-super 的 WMT24++ 86.7% 是免費群最佳翻譯數據**；gemma-4-31b Elo 1,451；gpt-oss-20b 中上 |
| 推薦理由/風險 | 一站多模型、官方聚合商無資料訓練爭議、OpenAI 相容最成熟；**限流緊（50/day）**，$10 終身升級後（1,000/day）才符合 #28 單日需求；免費模型頻 429 |

### 2.3 Google Gemini（OpenAI 相容端點） — ★★★★☆

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。ai.google.dev 免費層、**免綁卡**；但 **EU/EEA/UK/CH 用戶依法不可用免費層**，且免費層資料「用於改進產品」（[使用條款；Murat Karakaya 指南](https://www.muratkarakaya.net/2026/05/gemini-free-tier-llm-apis-for-developers.html)）→ 未發表論文紅線 |
| 額度變動史 | 2025-12-07 免費層配額砍 50–80%（未預告）；2026-04-01 **Pro 級模型全部移出免費層**（[yingtu.ai 指南](https://yingtu.ai/en/blog/google-gemini-api-free-tier-limits-2026)、[gemini-cli issue #22576](https://github.com/google-gemini/gemini-cli/issues/22576)） |
| 額度（2026-08） | `gemini-3.1-flash-lite-preview`：**15 RPM / 500 RPD**；`gemma-4-31b-it`：**15 RPM / 1,500 RPD**（repo 數據與第三方一致）；額度 per-project 非 per-key；**開啟計費即失去免費層**（[usagebox](https://usagebox.com/articles/gemini-api-billing-free-tier-confusion)） |
| OpenAI 相容 | ✅ `https://generativelanguage.googleapis.com/v1beta/openai` 存在（repo 記載＋[theplusaddons](https://theplusaddons.com/blog/gemini-api-wordpress/) 佐證）；⚠️ 一份 2026-04 第三方研究稱「不相容需自家 SDK」（[kestrel 研究](https://github.com/pleasedodisturb/kestrel/blob/main/docs/research/free-model-landscape-2026.md)）——可能過時，**落地前先 curl 實測** |
| 品質定位 | flash-lite 系列是 Gemini 家族（WMT25 冠軍家族）的輕量版，一般文本翻譯足夠；gemma-4-31b T2 級、262K 長文 |
| 推薦理由/風險 | 品質/額度平衡佳、gemma-4 的 1,500 RPD 是候選中單模型最高日額度；**資料訓練條款＝未發表論文不可用**；額度政策近一年頻繁緊縮 |

### 2.4 Groq — ★★★★☆

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。免綁卡、全模型共用免費額度（[klymentiev.com Groq 定價](https://klymentiev.com/blog/groq-pricing)、[ianlpaterson 實測](https://ianlpaterson.com/blog/free-llm-api-2026/)） |
| 額度 | **30 RPM / 6,000 TPM / 14,400 RPD**（組織層級、加 key 不放大）；加卡解鎖 Developer tier（約 10 倍） |
| 可用免費模型 | `openai/gpt-oss-120b`、`openai/gpt-oss-20b`、`qwen/qwen3-32b`（repo 記載） |
| 品質定位 | T2：gpt-oss-120b 是單 GPU 級最強開放推理模型（GPQA 80.1%）；qwen3-32b 中文佳 |
| 推薦理由/風險 | 品質高、RPD 充裕（14,400）；**關鍵瓶頸＝6,000 TPM**——單次長文呼叫（pdf2zh 分塊後每塊數千 token）容易直接撞 TPM 而 429，翻譯整本會頻繁降速；**建議搭配短分塊/重試** |

### 2.5 HuggingFace — ★☆☆☆☆（repo 宣稱與官方文件重大出入）

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ⚠️ **僅形式存在**。[官方 Pricing 文件](https://huggingface.co/docs/inference-providers/en/pricing)：免費用戶每月 **$0.10 credit**（PRO $2.00），用罄即需購買 credit；大模型（DeepSeek-V4-Pro、GLM-5.1 等）為**轉發付費（pass-through）**，非免費 |
| **repo 宣稱「300 RPH 免費跑 DeepSeek-V4-Pro/GLM-5.1」** | ❌ **未獲官方文件支持**。唯一接近的「每小時數百次」說法指的是舊 Serverless 免費層，且限 **<10B 參數模型**（[klymentiev.com HF 分析](https://klymentiev.com/blog/huggingface-inference-api)）。$0.10/月 ≈ 一兩個大模型請求即耗盡 |
| Key 取得 | 免費 HF 帳號即可，fine-grained token（官方文件） |
| 品質定位 | 若能付費：DeepSeek-V4-Pro / GLM-5.1 / Kimi-K2.6 全是 T1；但免費額度下無實質可用性 |
| 推薦理由/風險 | **對 Paper_Kit 免費用途不成立**；除非驗證到特定 partner 對特定模型掛 free（例：`zai-org/GLM-5.1` 走 Z.ai partner），否則跳過。落地前可 `curl /v1/models` 看實際定價欄位 |

### 2.6 ModelScope 魔搭 — ★★★★☆

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。**每日 2,000 次 API 呼叫**（帳戶總額度、按請求數非 token），UTC+8 0 點重置、不累積（[Cherry Studio 文件](https://docs.cherryai.com.cn/pre-basic/providers/modelscope)、[CSDN 實測文](https://blog.csdn.net/static_coder/article/details/159907900)、[今日頭條實測](https://m.toutiao.com/article/7616924523018846771/)） |
| Key 取得 | 註冊後**須綁阿里雲帳號＋實名**；SDK Token（`ms-` 開頭）於控制台建 |
| 額度細節 | 模型級額度動態分配：實測 DeepSeek-V4-Pro/GLM-5.1 約 **500 次/日**、DeepSeek-V3.2 僅 20 次/日；**V4-Pro 常報 insufficient_quota**（實測文同源） |
| 可用免費模型 | `deepseek-ai/DeepSeek-V4-Pro`、`deepseek-ai/DeepSeek-V4-Flash`、`ZhipuAI/GLM-5.1`、`Qwen/Qwen3-235B-A22B-Instruct-2507`、`MiniMax/MiniMax-M2.5` 等 |
| 品質定位 | **T1 品質、免費渠道天花板**：V4-Pro（AA 52–53）、GLM-5.1（51.4）、Qwen3-235B（JP-TL 9.93） |
| 推薦理由/風險 | 唯一「旗艦模型免費」的可靠來源；**風險＝額度不穩（動態分配、熱門模型可能 insuff。quota）、需阿里雲實名**。翻譯整本 300–600 次呼叫 vs 2,000 RPD，理論上單日 3–6 本 |

### 2.7 NVIDIA NIM — ★★★★★（候選第一）

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。build.nvidia.com 全模型免費原型開發，**無計費、無 SLA、無數據駐留保證**（[官方 FAQ／gotchaa-lab 分析](https://gotchaa-lab.com/blog/2026-06-10-nvidia-free-ai-models-malaysian-businesses)）；2025 年初取消 credit 制、純限流制 |
| 額度 | **~40 RPM（多數模型）**、per-key；無官方每日總量說法；**無官方提高額度管道**（升級需付費部署；[NVIDIA 論壇](https://forums.developer.nvidia.com/t/request-to-increase-nvidia-nim-api-rate-limit-40-200-rpm/379653)）；40 RPM × 60 分 ≈ 2,400 次/小時理論值 |
| Key 取得 | build.nvidia.com 註冊（開發者帳號），`nvapi-` key |
| 可用免費模型 | `deepseek-ai/deepseek-v4-flash`（2026-04-23 上線、284B/13B active、**1M context**、近 30 天 1,700 萬次免費呼叫——[官方模型卡](https://build.nvidia.com/deepseek-ai/deepseek-v4-flash)）、`z-ai/glm5.2`、`moonshotai/kimi-k2.6`、`qwen/qwen3.5-122b-a10b`、`stepfun-ai/step-3.7-flash`、`nvidia/nemotron-3-ultra-550b-a55b` 等 |
| 品質定位 | **T1/T2 混合、候選中最高**：kimi-k2.6（AA 54）、glm5.2（53）、deepseek-v4-flash（≈52） |
| 推薦理由/風險 | 唯一同時具備「旗艦模型品質＋無日總量上限＋40 RPM」的免費源，單日理論 2,400 次符合 #28 需求；**風險＝429 需退避重試、無 SLA、模型輪換**。部分來源稱 40 RPM 為全模型共享（另一來源稱 per-model）——兩說並存，實測為準 |

### 2.8 智譜 Bigmodel — ★★★☆☆

| 項目 | 查證結果 |
|---|---|
| 免費層存在 | ✅ 是。**GLM-4-Flash 官方永久免費、無 token 上限**；GLM-4.7-Flash（2026-01-20 發布，[東財新聞](https://finance.eastmoney.com/a/202601203624430243.html)）亦免費；GLM-4.5-Flash 已於 2026-01-30 下線並自動路由（官方文件 [GLM-4-Flash-250414](https://docs.bigmodel.cn/cn/guide/models/free/glm-4-flash-250414)） |
| Key 取得 | 手機號註冊＋**實名認證**（否則無法建 key）；新用戶贈 2,000 萬 token |
| 額度 | 無 token 上限、以**併發數**計（repo：GLM-4.7-Flash/GLM-4-Flash-250414 併發 2；GLM-4V-Flash 併發 10）；128K（4-Flash）/200K（4.7-Flash）上下文 |
| 可用免費模型 | `glm-4-flash`（GLM-4-Flash-250414）、`glm-4.7-flash`、`glm-z1-flash`、`glm-4v-flash` |
| 品質定位 | T3：GLM-4.7-Flash 官方宣稱同尺寸 SOTA（SWE-bench 91.6 等），但**第三方 ReLE 實測全面退步**（63.0%→55.5%、回應 1,238s、token 翻倍，[NoneLinear](https://blogs.nonelinear.com/blog/glm-4-7-flash-performance-5968f36df545)）；GLM-4-Flash 為 9B 級 |
| 推薦理由/風險 | 無 token 上限適合跑量；**但品質與穩定性存疑（尤其 4.7-Flash 的第三方實測）**，翻譯需先 A/B 實測；併發 2 對批次翻譯是天然限流 |

### 2.9 其餘項目速覽（repo 第 9–25）

| 提供者 | 額度（repo） | 速評 |
|---|---|---|
| Intern AI 書生 | 10 RPM；key 6 個月有效 | 速率過低，單本 300–600 次呼叫需 1 小時+ |
| Cohere | 20 RPM | 需綁卡才解 Production key；#28 判 1,000 req/月 一本吃 60% |
| LLM7 | 2 RPS/20 RPM/100 RPH | 品質未查證 |
| Kilo Gateway | 200 RPH | 中轉聚合，模型多為其他平台免費模型 |
| Celebras | gpt-oss-120b 30 RPM/900 RPH/1,440 RPD | 與 Groq 同級但額度更緊 |
| Mistral | 不明 | **同意資料訓練**（#28 一票否決） |
| OpenCode Zen / DXNT / Agens AI / G4F | 不明 | 小平台、無官方文件，品質未查證 |
| Cloudflare Workers AI | 10k neurons/日 | 計算單位制，成本換算不明 |
| SenseNova 商湯 | 1,500 次/5hr（flash-lite） | 分時段配額，批次任務易中斷 |
| 訊飛星火 | 2 QPS（lite） | 速率高但品質未查證 |
| InceptionLab / Poolside | 1,000 RPM / 不明 | 品質未查證 |
| ChatAnywhere | 30 req/day（deepseek 系） | **轉發中介＋日額度極低**（#28 三重紅線） |
| 肖恩AI | 每日簽到 | 簽到制不適合自動化 |

---

## 3. 綜合優先序建議表（PDF 翻譯引擎候選）

基準：#28 工作負載（單本 300–600 呼叫；單日 1,200+；未發表論文不得進訓練條款免費層）。★＝品質×額度×門檻綜合。

| 優先序 | 引擎名 | base_url | 模型 | 免費額度 | 品質 | 推薦理由 | 風險 |
|---|---|---|---|---|---|---|---|
| **1** | NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `deepseek-ai/deepseek-v4-flash`（首選）、`z-ai/glm5.2`、`moonshotai/kimi-k2.6` | ~40 RPM、無日總量（官方無日限記載）；單日理論 ~2,400 次 | **T1/T2**（AA 52–54） | 唯一「旗艦品質＋無日總量＋40 RPM」；1M context 長文友好；無資料訓練爭議；免卡 | 429 需退避重試；無 SLA；模型可能輪換 |
| **2** | ModelScope | `https://api-inference.modelscope.cn/v1/` | `deepseek-ai/DeepSeek-V4-Pro`、`ZhipuAI/GLM-5.1` | 2,000 RPD（帳戶總額；熱門模型實測 ~500/日） | **T1**（AA 52–53） | 免費渠道品質天花板；中文最強；OpenAI 相容 | 額度動態分配、V4-Pro 常 insuff。quota；需阿里雲實名 |
| **3** | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemma-4-31b-it`（1,500 RPD）、`gemini-3.1-flash-lite-preview`（500 RPD） | 15 RPM／1,500 或 500 RPD | **T2**（gemma-4 Elo 1,451、262K） | gemma-4 日額度候選最高；長文友好；免卡 | **免費層資料訓練＝未發表論文紅線**；EU 不可用；額度政策頻繁緊縮 |
| **4** | Groq | `https://api.groq.com/openai/v1/` | `openai/gpt-oss-120b`、`qwen/qwen3-32b` | 30 RPM／**6,000 TPM**／14,400 RPD | **T2**（gpt-oss-120b GPQA 80.1%） | RPD 充裕、品質高、免卡 | **6,000 TPM 撞長文**——需小分塊＋重試；429 頻 |
| **5** | OpenRouter | `https://openrouter.ai/api/v1` | `nvidia/nemotron-3-super-120b-a12b:free`、`google/gemma-4-31b-it:free`、`openai/gpt-oss-20b:free` | 20 RPM／50 RPD（免卡）→ **$10 終身升級 1,000 RPD** | **T2**（nemotron 翻譯 WMT24++ 86.7%） | 一站多模型、官方聚合、無訓練爭議；nemotron 翻譯數據免費群最佳 | 50 RPD 遠不夠（升級後才過門檻）；免費模型頻 429 |
| **6** | SiliconFlow | `https://api.siliconflow.cn/v1` | `THUDM/GLM-4-9B-0414`、`Qwen/Qwen3-8B` | **每模型 1,000 RPM／50K TPM**（L0，官方） | **T4**（9B 級） | 速率最慷慨、中文平台穩定、免卡 | 9B 品質翻技術論文吃力；需實名 |
| **7** | 智譜 Bigmodel | `https://open.bigmodel.cn/api/paas/v4/` | `glm-4.7-flash`、`glm-4-flash` | 無 token 上限、併發 2 | **T3**（4.7-Flash 實測退步） | 唯一「無上限」跑量源；中文 | 4.7-Flash 第三方實測品質/延遲警訊；併發 2 卡批次 |
| **8** | HuggingFace | `https://router.huggingface.co/v1` | （無實質免費大模型） | $0.10/月 credit | T1（但要錢） | — | **repo 宣稱未獲官方支持**；不適用免費路線 |

### 建議落地組合

1. **主力引擎**：NVIDIA NIM `deepseek-v4-flash`（品質/額度平衡最佳），備援 `glm5.2`。
2. **品質優先備援**：ModelScope `DeepSeek-V4-Pro`（額度不穩時自動切換策略）。
3. **高頻日常（非敏感論文）**：Gemini `gemma-4-31b-it`（1,500 RPD）或 Groq `gpt-oss-120b`。
4. **敏感/未發表論文**：走 NVIDIA NIM、ModelScope、SiliconFlow、OpenRouter、智譜（無資料訓練條款）——**絕不走 Gemini 免費層與 Mistral**（#28 紅線）。
5. **實測清單（落地前）**：① Gemini OpenAI 相容端點 curl 實測；② NVIDIA 40 RPM 為 per-model 或共享；③ ModelScope 當日 V4-Pro 剩餘額度；④ 智譜 4.7-Flash 單段翻譯延遲。

---

## 4. 查證失敗／資訊不明清單（誠實標記）

| 項目 | 狀態 | 說明 |
|---|---|---|
| **HF「300 RPH 免費大模型」** | ❌ 與官方文件矛盾 | 官方文件僅 $0.10/月 credit；可能為 repo 過時資訊或特定 partner 特例，**需 `curl /v1/models` 實測定價欄位** |
| **OpenRouter 每日額度 200 RPD** | ❌ repo 數據未獲支持 | 多來源（2026-04~07）皆為 **50 RPD（<$10）／1,000 RPD（$10 終身）**；未直接抓到官方 limits 頁面，以 pricepertoken/官方 blog 為準 |
| **NVIDIA 40 RPM 共享或 per-model** | ⚠️ 兩說並存 | 官方 FAQ「up to 40 RPM for most models」；中文實測文稱共享、論壇稱 per-model |
| **Gemini OpenAI 相容端點** | ⚠️ 一來源衝突 | kestrel（2026-04）稱不相容，repo＋theplusaddons（2026 中）稱存在——**落地前 curl 實測** |
| **ModelScope 每模型每日額度** | ⚠️ 無官方固定數字 | 動態分配；實測 500/日（V4-Pro、GLM-5.1）～20/日（V3.2） |
| **GLM-4.7-Flash 品質** | ⚠️ 官方與第三方嚴重分歧 | 官方宣稱同尺寸 SOTA vs ReLE 實測大退步＋1,238s 延遲；BigModel 官方端實際行為需 A/B |
| **SiliconFlow 免費用戶實際 RPM** | ⚠️ 官方 L0=1,000 RPM 但有第三方稱 60 RPM | 以官方文件＋控制台為準 |
| **智譜併發數** | ⚠️ repo 記載 4-Flash/4.7-Flash 併發 2 | 官方另有「30 併發」說法，來源不一 |
| **小平台（DXNT、Agens AI、G4F、OpenCode Zen、InceptionLab、SenseNova 免費模型品質）** | ⚠️ 資訊不明 | 無官方文件或可靠評測；不建議採納 |
| **GLM-4-9B/Qwen3-8B 翻譯專項評測** | ⚠️ 無 2026-08 專項數據 | 僅 95 語言通用評測（qwen3:8b 5.5/10）；品質定位為推論 |
| **gpt-oss-120b LMArena 排名** | ⚠️ 查無大樣本數據 | 以 llm-stats/AA 子項評測替代 |

---

## 5. 關鍵來源彙整

**Repo**：[for-the-zero/Free-LLM-Collection](https://github.com/for-the-zero/Free-LLM-Collection)

**免費層政策（官方優先）**
- SiliconFlow：[Rate Limits 官方文件](https://docs.siliconflow.cn/cn/userguide/rate-limits/rate-limit-and-upgradation)、[限流 FAQ](https://docs.siliconflow.cn/cn/faqs/misc_rate)、[免費模型清單（yangmao.ai）](https://yangmao.ai/zh/blog/siliconflow-free-models-list/)
- OpenRouter：[官方免費 API 比較文](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)、[pricepertoken 免費層頁](https://pricepertoken.com/endpoints/openrouter/free)、[NanoGPT 429/額度分析](https://nano-gpt.com/blog/openrouter-429-rate-limits-recovery)
- Gemini：[Murat Karakaya 免費層指南（2026-05）](https://www.muratkarakaya.net/2026/05/gemini-free-tier-llm-apis-for-developers.html)、[yingtu.ai 免費層變動史](https://yingtu.ai/en/blog/google-gemini-api-free-tier-limits-2026)、[gemini-cli issue #22576](https://github.com/google-gemini/gemini-cli/issues/22576)、[開啟計費＝失去免費層](https://usagebox.com/articles/gemini-api-billing-free-tier-confusion)
- Groq：[klymentiev.com Groq 免費層](https://klymentiev.com/blog/groq-pricing)、[ianlpaterson 實測（2026-05-31）](https://ianlpaterson.com/blog/free-llm-api-2026/)、[pricepertoken Groq](https://pricepertoken.com/endpoints/groq/free)
- HuggingFace：[Inference Providers 官方文件](https://huggingface.co/docs/inference-providers/en/index)、[官方 Pricing（免費 $0.10/月）](https://huggingface.co/docs/inference-providers/en/pricing)、[klymentiev.com HF 分析](https://klymentiev.com/blog/huggingface-inference-api)
- ModelScope：[Cherry Studio 提供者文件](https://docs.cherryai.com.cn/pre-basic/providers/modelscope)、[CSDN 2,000 RPD 實測](https://blog.csdn.net/static_coder/article/details/159907900)
- NVIDIA NIM：[build.nvidia.com deepseek-v4-flash 頁](https://build.nvidia.com/deepseek-ai/deepseek-v4-flash)、[NVIDIA 論壇額度討論](https://forums.developer.nvidia.com/t/request-to-increase-nvidia-nim-api-rate-limit-40-200-rpm/379653)、[gotchaa-lab 免費政策分析](https://gotchaa-lab.com/blog/2026-06-10-nvidia-free-ai-models-malaysian-businesses)
- 智譜：[GLM-4-Flash-250414 官方文件](https://docs.bigmodel.cn/cn/guide/models/free/glm-4-flash-250414)、[GLM-4.7-Flash 發布（DoNews）](https://www.donews.com/news/detail/1/6383822.html)

**模型品質**
- [Artificial Analysis：DeepSeek-V4-Pro vs GLM-5.1](https://artificialanalysis.ai/models/comparisons/deepseek-v4-pro-high-vs-glm-5-1)、[AA：nemotron-3-super](https://artificialanalysis.ai/models/nvidia-nemotron-3-super-120b-a12b)、[officechai：V4-Pro AA Index 52 與 0813 build 53](https://officechai.com/ai/deepseek-v4-pro-becomes-second-highest-rated-open-model-on-artificial-analysis-index-with-score-of-52/)
- [LMArena 文字生成榜（DataLearner 鏡像 2026-08-01）](https://www.datalearner.com/en/leaderboards/external/text-generation?isChina=1)、[GPQA-Diamond 開放模型榜](https://llmrun.dev/benchmark/gpqa-diamond)
- [gpt-oss-120b vs 20b（llm-stats）](https://llm-stats.com/models/compare/gpt-oss-120b-vs-gpt-oss-20b)、[gpt-oss 學術評測（arXiv 2508.12461）](https://ar5iv.labs.arxiv.org/html/2508.12461)
- [GLM-4.7-Flash 第三方實測（NoneLinear）](https://blogs.nonelinear.com/blog/glm-4-7-flash-performance-5968f36df545)
- 翻譯專項：[WMT25 人工評測整理](https://awesomeagents.ai/tools/best-ai-translation-tools-2026/)、[JP-TL-Bench](https://benchmarklist.com/benchmarks/jp_tl_bench_anchored_pairwise_llm_evaluation_for_bidirectional_japanese_english_translation/)、[Alconost 2026 翻譯引擎分數榜](https://alconost.com/en/blog/best-llm-for-translation-2026)、[2026 LLM 翻譯品質評測](https://futureagi.com/blog/evaluating-llm-translation-quality-2026/)
