---
title: NVIDIA NIM Free Endpoint 模型翻譯品質評測與推薦
date: 2026-08-14
tags: [paper_kit, research, llm, nvidia-nim, translation, model-selection]
status: active
---

# NVIDIA NIM Free Endpoint 模型翻譯品質評測與推薦（論文翻譯用）

> 2026-08-14。針對 build.nvidia.com「Free Endpoint」模型清單（`filters=nimType%3Anim_type_preview` 頁面 48 個＋API 目錄 102 個），評估哪些適合「英→繁中論文翻譯」（pdf2zh 引擎、NVIDIA NIM OpenAI 相容端點 `https://integrate.api.nvidia.com/v1`）。本報告為 Paper_Kit 選模型決策的查證依據。

## TL;DR 結論

1. **47 個候選中，適合翻譯的生成式 LLM 約 21 個**；其餘 26 個為嵌入／檢索／多模態視覺／音訊／影片／生物／量子／安全分類等專用模型，**不適用翻譯**（已逐項標示排除理由）。
2. **唯一有「機器翻譯排行榜第一名」實證的是 Nemotron 3 Super 120B**：WMT24++（55 語種）en→xx 綜合 0.867 居冠、Nemotron 3 Nano 30B 0.862 居次——兩個都是 NIM Free Endpoint，且是 NIM 上少數直接以翻譯基準為評分的模型。
3. **glm-5.2 是 NIM 上「智慧度」最高的開源模型**（Artificial Analysis 智力指數 v4.1 = 51，開源第一，勝 MiniMax-M3 44、DeepSeek V4 Pro 44），中文原生、1M context、MIT 授權——中文語感與長文一致性預期最佳，但**無直接翻譯基準成績**。
4. **使用者漏掉的高價值模型**：`moonshotai/kimi-k2.6`（LMArena 文本 1466、開源陣營前段；已確認掛 Free Endpoint，但有帳號 404 供裝問題）與 `nvidia/nemotron-3.5-lightning-30b-a3b`（08-11 剛發布，worker 級，快但無翻譯證據）。使用者現用預設 `deepseek-ai/deepseek-v4-flash-0731` **只在 API 上、不在網站頁面**，且原 `deepseek-v4-flash` 已於 2026-08-07 EOL（HTTP 410）。
5. **EOL 風險最高的是 DeepSeek 家族**（08-07 整族下架、0731 屬「測試中」且社群回報不穩）；NVIDIA 免費層官方明言「無 SLA、模型隨時可能變更或移除」。

## 資料來源與方法（查證優先序）

| 層級 | 來源 | 用途 |
|---|---|---|
| 一手 | NVIDIA NIM API 實測 `GET https://integrate.api.nvidia.com/v1/models`（免 key，2026-08-14 實抓 102 個模型 id） | 確認可用模型清單（含頁面漏掉者） |
| 一手 | NVIDIA Developer Forums（deepseek-v4 EOL、kimi-k2.6/minimax-m3 404、速率上限） | EOL 與可用性查證 |
| 一手 | 官方模型卡（HuggingFace / NVIDIA build / docs.api.nvidia.com）：WMT24++、RULER、MMLU-multilingual | 翻譯與長文證據 |
| 一手 | WMT24++ 論文（arXiv:2502.12404，55 語種） | 翻譯基準定位 |
| 一/二手 | LMArena（arena.ai/text）＋AITNT 中文/專家/消費分榜（2026-08 同步） | 人類偏好 Elo（中文子集） |
| 二手 | Artificial Analysis（智力指數、RULER、速度）、XSCT Bench 多語種翻譯（257 模型） | 綜合品質＋翻譯實測 |
| 二手 | WMT25 新聞彙整（Marco-MT、Hunyuan-MT-7B） | 翻譯專用模型現況（NIM 上無） |

> 註：build.nvidia.com 前端為 Next.js SPA，`backend/api/models` 無法直接抓 JSON（回傳 HTML 殼）；Free Endpoint 判定以使用者提供頁面清單為主、第三方追蹤站（ayautomate 等）＋論壇為輔。

---

## 1. 候選分類：適用翻譯 vs 不適用（全部 47 個逐一標示）

### 1.1 生成式 LLM（適合翻譯）— 21 個

| 模型（Free Endpoint） | 判讀 |
|---|---|
| nemotron-3-super-120b-a12b | ✅ 文本 LLM，WMT24++ #1 |
| nemotron-3-ultra-550b-a55b | ✅ 文本推理 LLM |
| nemotron-3-nano-30b-a3b | ✅ 文本 LLM，WMT24++ #2 |
| nemotron-3-nano-omni-30b-a3b-reasoning | ⚠️ 文本可輸出，但屬 omni 多模態＋預設 CoT，翻譯證據無 |
| llama-3.3-nemotron-super-49b-v1.5 | ✅ 推理型文本 LLM |
| llama-3.1-nemotron-nano-8b-v1 | ⚠️ 小型 |
| nemotron-mini-4b-instruct | ⚠️ 過小 |
| nvidia-nemotron-nano-9b-v2 | ⚠️ 小型 |
| gpt-oss-120b | ✅ |
| gpt-oss-20b | ✅ 快速、省成本 |
| llama-3.3-70b-instruct | ✅ 成熟主力 |
| llama-3.1-8b-instruct | ⚠️ 小型（WMT25 社群評為 8B 級最佳值） |
| llama-3.1-70b-instruct | ⚠️ 上一世代 |
| llama-3.2-90b-vision-instruct | ⚠️ 文本可輸出，視覺導向 |
| llama-3.2-11b-vision-instruct | ⚠️ 同上 |
| llama-3.2-3b-instruct | ⚠️ 過小 |
| llama-3.2-1b-instruct | ❌ 太小（略過） |
| minimax-m3 | ✅ |
| glm-5.2 | ✅ 最高優先 |
| step-3.7-flash | ✅ 快速 |
| gemma-4-31b-it | ✅ |
| mistral-nemotron | ✅ NVIDIA 模型卡明言定位含翻譯 |
| riva-translate-4b-instruct-v1_1 | ⚠️ 特殊類：**專用 NMT**（見 §4.6） |

### 1.2 專用任務模型（不適用翻譯）— 26 個

| 模型 | 類別 | 排除理由 |
|---|---|---|
| nv-embed-v1 | 嵌入 | 向量檢索，非生成 |
| nv-embedcode-7b-v1 | 程式碼嵌入 | 同上 |
| rerank-qa-mistral-4b | 重排序 | RAG 用，非生成 |
| nemotron-3.5-content-safety | 內容安全分類 | 分類器 |
| llama-3.1-nemotron-safety-guard-8b-v3 | 安全護欄 | 分類器 |
| llama-guard-4-12b | 安全護欄 | 分類器 |
| esmfold | 蛋白質摺疊 | 生物專用 |
| esm2-650m | 蛋白質語言模型 | 生物專用 |
| magpie-tts-zeroshot | 語音合成 | TTS |
| Studio Voice | 語音合成 | TTS |
| nemotron-voicechat | 語音對話 | 語音 |
| Active Speaker Detection | 發話者偵測 | 音訊 |
| Background Noise Removal | 降噪 | 音訊 |
| cosmos3-nano / cosmos3-nano-reasoner | 世界模型 | 影片生成 |
| cosmos-transfer1-7b | 影片生成 | 影片 |
| streampetr / bevformer | 3D 感知 | 自駕視覺 |
| ising-calibration-1-35b-a3b | Ising 量子校準 | 物理專用 |
| synthetic-video-detector | 影片偵假 | 分類器 |
| diffusiongemma-26b-a4b-it | 影像生成 | 非文本 |
| paligemma | 視覺語言 | 影像輸入 |
| llama-3.1-nemotron-nano-vl-8b-v1 | 視覺語言 | 8B 視覺模型，翻譯證據無 |
| nemotron-nano-12b-v2-vl | 視覺語言 | 同上 |

---

## 2. 適合翻譯模型的品質證據（排序依據）

> LMArena Elo：人類偏好 A/B 投票；「中文分榜」＝中國語境子集，與英→繁中翻譯最相關。WMT24++：55 語種 en→xx 機器翻譯排行榜（LLM 為所有 55 語種最強 MT 系統，論文結論）。XSCT Bench l_trans_002：257 模型英→中翻譯，但**測試句僅一句 "Hello, how are you?"，滿分飽和（95–100 扎堆），鑑別力極弱**——僅當參考不當排他依據。

| 模型 | LMArena 文本 Elo | 中文分榜 Elo | 翻譯基準 | AA 智力指數 | Context | 速率/授權 |
|---|---|---|---|---|---|---|
| **nemotron-3-super-120b-a12b** | ~1361–1393（各家快照） | **1402**（NVIDIA org #2，08-04） | **WMT24++ 0.867（#1，55 語種）**、XSCT 97.8 | ~（n/a） | **1M**（預設 256K；RULER@128k 96.79、@1M 91.75） | NVFP4 高吞吐、OpenMDW |
| **glm-5.2** | **1483**（08-04，全榜 #58） | 5.2-max 1521；5.2 本體無中分榜 | 無直接 MT 成績 | **51（v4.1，開源最高）** | 1M | MIT |
| **nemotron-3-ultra-550b-a55b** | 不在 top-100 | **1463**（NVIDIA org #1，08-12） | 無直接 MT 成績 | 38 | 1M（NVIDIA）/260K（AA 實測）；RULER@1M 94.7 | 183–218 tok/s（AA 實測） |
| **minimax-m3** | **1445**（Style Control，07-12） | 1475（中文類目，07-12） | XSCT 97.2 | 44（v4.1） | **1M**（131K 輸出） | 原生多模態但文本輸出 |
| **gpt-oss-120b** | ~1354 | — | **XSCT 99.5（257 模型 #4）** | ~ | 128K（RULER @1M 崩至 22.3——超長文禁用） | Apache 2.0、MoE 5.1B active |
| **gpt-oss-20b** | — | — | **XSCT 99.5（與 120b 並列）** | ~ | 128K | 20B 稠密、快、Apache 2.0 |
| **gemma-4-31b-it** | **1452**（開源 #3） | — | XSCT 95.2 | ~ | 256K | 稠密 31B、Apache 2.0 |
| **step-3.7-flash** | 無公開 Elo | — | XSCT 98.0 | 42.6 | 256K | **~400 tok/s（AA 速度 #1）**、Apache 2.0、中文原生 |
| **kimi-k2.6**（使用者漏掉） | **1466**（08-04，全榜 #46） | — | 無 | ~（前段） | 256K | Modified MIT、1T MoE 32B active |
| **nemotron-3-nano-30b-a3b** | 1355（中文分榜 #3） | **1355** | **WMT24++ 0.862（#2）** | ~ | 262K | **成本極低**（AA $0.06/$0.24 級距，WMT 前段最便宜） |
| **llama-3.3-70b-instruct** | ~1250s（世代舊） | — | XSCT 99.0 | ~ | 128K | 成熟、穩定 |
| llama-3.3-nemotron-super-49b-v1.5 | — | 1307（v1 舊版） | 無 | GPQA 71.97–74.8、ArenaHard 92（自評） | 128K | 推理型；翻譯證據薄弱 |
| mistral-nemotron | — | — | NVIDIA 卡：定位含翻譯；MMLU 中文 80.54；XSCT（同源 Nemo）79.4 | ~ | 128K | 2025-06 世代，中規中矩 |
| deepseek-v4-flash（原版，**已 EOL**） | ~1100–1200 區帶 | — | XSCT 98.0 | 46.5 | 1M | EOL 2026-08-07 |
| deepseek-v4-flash-0731（現用預設） | — | — | 沿用 v4-flash 成績（不保證） | — | 1M | **僅 API 上線、社群回報不穩** |

---

## 3. 重點模型短評

### 3.1 nemotron-3-super-120b-a12b —— 翻譯實證第一名
- **WMT24++ en→xx 綜合 0.867、55 語種排行榜 #1**（NVIDIA 模型卡＋WMT24++ 論文），NIM 免費層唯一有 MT 排行榜第一名的模型；Nano 30B 0.862 居次、Qwen3.7 Max 0.858 第三。
- 中文 LMArena 1402（NVIDIA org 內僅次於 Ultra）。RULER 長文 128K→1M 均 >91，長論文整篇進 context 沒問題。
- MoE 12B active＋LatentMoE 混合架構，吞吐高；免費端點 40 RPM 下批次翻譯可接受。
- 注意：Elo 快照各家落差（1361–1402）、標「volatile」；無獨立 WMT 複測（數據為 NVIDIA 自評＋論文複現）。

### 3.2 glm-5.2 —— 開源智慧度天花板、中文原生
- AA 智力指數 v4.1 = 51，**開源第一**（勝 MiniMax-M3 44、DeepSeek V4 Pro 44、Kimi K2.6 43；與 Gemini 3.5 Flash 50 同級）。LMArena 文本 1483（全榜 #58，勝過多數閉源）。
- 智譜原生中文模型，中文語感、術語繁中化預期最佳（5.2-max 中文分榜 1521）。1M context、MIT 授權無商用風險。
- **注意：無直接 MT 基準成績**——「英語→繁中」需自行小樣本驗證（pdf2zh「測試 API」＋試譯一段）；另一風險是免費層新模型偶發供裝問題。

### 3.3 nemotron-3-ultra-550b-a55b —— 中文偏好最高、但缺翻譯實證
- 中文分榜 1463＝NVIDIA org 內第一，且是 2026-06 新旗艦；RULER@1M 94.7 長文最強；183–218 tok/s 極快。
- **但 550B MoE（55B active）**：免費端點並行/延遲未公開，批次翻譯排隊感未知；無任何 MT 基準成績。適合「品質優先、量大排隊可接受」的場合；注意 AA 實測 context 僅 260K（NVIDIA 宣稱 1M）。

### 3.4 gpt-oss-120b / 20b —— 翻譯實測高分、Apache 授權乾淨
- XSCT 257 模型英→中 #4/#5（99.5，僅次 Grok 4.6/GPT-5.6-sol/doubao-seed-2-1-pro），為測試句飽和區的頂標；Apache 2.0 授權最乾淨。
- **注意：RULER 長文衰減極快（1M 僅 22.3）**——context 上限 128K，論文必須走 pdf2zh 分塊（現行架構已是分塊，無影響）；Elo ~1354 屬中段，複雜語感（繁體慣用語）不如中文原生模型。

### 3.5 kimi-k2.6（使用者漏掉）—— 高 Elo、開源前段
- 文本 Elo 1466（全榜 #46）、中文/多語能力佳、256K context、1T MoE 32B active、成本低。**已掛 Free Endpoint**（ayautomate 追蹤站＋論壇佐證）。
- **注意：免費端點有 404「Function not found for account」供裝問題**（與 minimax-m3 同批回報，部分帳號可用、部分不可；gemma-4-31b-it 曾被修復、kimi 當時未修）——加入引擎後必須實測端點活性。

### 3.6 step-3.7-flash —— 最快、但幻覺指標警訊
- XSCT 98.0、AA 智力 42.6、**400 tok/s 速度第一**、中文原生、Apache 2.0、256K。
- **注意：AA-Omniscience 幻覺率 84.4%**——對翻譯（忠實轉寫）屬風險訊號；知識類任務弱。若走「快速初翻＋人工校對」路線可考慮。

### 3.7 mistral-nemotron —— 官方定位「含翻譯」但實測中段
- NVIDIA 模型卡明言設計定位含翻譯；MMLU 多語知識中文 80.54（五語後段）、法德西義 82–84。XSCT 同源（Mistral Nemo）實測僅 79.4、缺重音符等瑕疵——**品質定位 T3 中段**，不作主力推薦。

### 3.8 deepseek-v4-flash-0731（現用預設）—— 高危
- 原 `deepseek-v4-flash` 2026-08-07T09:00Z EOL（HTTP 410），v4-pro 同批下架（論壇 2 串＋社群 router 全移除；原版曾是「NIM 免費層最後一個 1M context 模型」）。
- `0731` 是 API 上的接續版本，**未上網站頁面**（NVIDIA 論壇稱「還在測試」）；社群回報 2–3 例隨機輸出/幻覺，1 例正常。**翻譯工具作預設有整批翻壞風險**——建議把預設移往 §5 推薦前段模型，0731 保留為選項＋實測監控。

---

## 4. 使用者可能漏掉的模型（API 目錄 102 個 vs 頁面 48 個）

> 2026-08-14 實抓 `GET /v1/models`：102 個模型。注意：**API 目錄＝付費＋免費全集合，出現不代表 Free Endpoint**；下列只列「生成式 LLM＋值得翻譯評估」者。

| 模型 id（API） | 是否 Free Endpoint | 評語 |
|---|---|---|
| **moonshotai/kimi-k2.6** | ✅ 已證實（追蹤站＋論壇） | **最高價值遺漏**：Elo 1466、256K；注意 404 供裝問題 |
| **nvidia/nemotron-3.5-lightning-30b-a3b** | 未知（08-11 剛發布，NVIDIA 自家新品，極可能進免費預覽） | worker 級（AA 24）、670 tok/s、1M ctx；無翻譯證據——「新、快、便宜」但非品質主力 |
| **deepseek-ai/deepseek-v4-flash-0731** | ✅（API 可用） | 現用預設，見 §3.8 |
| nvidia/nemotron-nano-3-30b-a3b | 未知 | 疑為 Nano v3 同名另部署（WMT24++ 0.862 證據共用）；頁面只有 nemotron-3-nano-30b-a3b 一個 id，API 兩者並存，注意別重複配置 |
| google/gemma-3-12b-it | 未知 | 12B 中段，Elo ~1350s；可作輕量備援 |
| nvidia/llama-3.1-nemotron-51b/70b-instruct、ultra-253b-v1 | 未知（多半付費） | 舊世代，中文分榜 1276/1304；不及 Super/Nano v3 |
| nvidia/nemotron-4-340b-instruct | 未知 | 中文 1287；舊旗艦 |
| mistralai/mistral-large、mistral-large-2-instruct | 未知 | 2024 世代，落後 |
| 其餘（yi-large、jamba-1.5、sea-lion、dbrx、starcoder2、zamba2、phi-3.5-moe、granite-3.0-8b、codegemma、mixtral-8x22b、llama2-70b、phi-3-vision、kosmos-2、palmyra-*、laguna-xs、inkling、muse-glimmer、deplot…） | 未知 | 程式碼/小模型/舊世代/專用——**對論文翻譯無增量價值**，不建議新增 |

**DeepSeek 家族查證**：API 上僅 `deepseek-coder-6.7b-instruct`（程式碼）與 `deepseek-v4-flash-0731`——**無 v4-pro、無 v3.2、無 r1**，DeepSeek 免費生成模型的唯一可用入口就是 0731。

---

## 5. 推薦清單（論文翻譯 top 8）

| 優先序 | 模型 id | 品質依據 | 適合翻譯的理由 | 注意事項 | 推薦等級 |
|---|---|---|---|---|---|
| 1 | nvidia/nemotron-3-super-120b-a12b | WMT24++ 0.867 **#1**（55 語種）；中文 LMArena 1402；RULER@1M 91.75 | NIM 免費層唯一 MT 榜首實證；長文 1M 全論文直進；MoE 12B active 高吞吐 | Elo 快照波動（volatile）；WMT 成績為 NVIDIA 自評+論文複現 | ★★★★★ |
| 2 | z-ai/glm-5.2 | AA 智力 51 **開源第一**；LMArena 文本 1483；5.2-max 中文 1521 | 中文原生、語感最佳；1M ctx；MIT 商用無風險 | 無直接 MT 基準；需小樣本實測繁中輸出；新模型供裝偶發 | ★★★★★ |
| 3 | nvidia/nemotron-3-ultra-550b-a55b | 中文 LMArena **1463**（NVIDIA org #1）；RULER@1M 94.7 | 中文人類偏好最高；長文最強；速度 183–218 tok/s | 550B 免費端點並行未知；無翻譯基準；AA 實測 ctx 260K | ★★★★☆ |
| 4 | minimaxai/minimax-m3 | LMArena 文本 1445、中文類目 1475；XSCT 97.2 | 中文原生；1M ctx（131K 輸出） | **免費端點 404 供裝問題**（與 kimi 同批回報）；翻譯基準弱 | ★★★★☆ |
| 5 | openai/gpt-oss-120b | XSCT 99.5（257 模型 #4）；Apache 2.0 | 翻譯實測頂標；授權乾淨 | 128K ctx（RULER @1M 崩）——靠 pdf2zh 分塊；Elo 中段語感普通 | ★★★★☆ |
| 6 | google/gemma-4-31b-it | Elo **1452**（開源 #3）；XSCT 95.2 | 小體積高品質；256K；稠密 31B 免費端點穩定（論壇證實可用） | 無翻譯基準；繁中語感非原生 | ★★★★☆ |
| 7 | moonshotai/kimi-k2.6 | Elo **1466**（全榜 #46）；256K | 開源前段品質；多語強 | **404 供裝問題**需實測；無翻譯基準；免費層條款未明 | ★★★★☆ |
| 8 | nvidia/nemotron-3-nano-30b-a3b | WMT24++ 0.862 **#2**；中文分榜 1355 | MT 榜眼＋**成本極低**＋262K ctx——批次翻譯量大時最佳性價比 | 12B active 之下的極限：複雜長術語文本信心低於 Super；Elo 中段 | ★★★★☆ |

**候補（供替換/多引擎並存）**：llama-3.3-70b-instruct（XSCT 99.0 成熟主力）、step-3.7-flash（XSCT 98.0、400 tok/s、幻覺警訊）、gpt-oss-20b（快速省錢）、llama-3.3-nemotron-super-49b-v1.5（推理型、翻譯證據薄）。

**專用 NMT 備援**：riva-translate-4b-instruct-v1_1——支援 **en→zh-TW 語言對**（system message 打 `en-zh-tw` 標籤）、OpenAI 相容；但 8K ctx、4B NMT 品質（無上下文理解）**不適合論文長文**，僅可作低品質快速檔位。

---

## 6. EOL / deprecation 風險標註（deepseek-v4-flash 教訓）

| 模型/類別 | 風險 | 證據 |
|---|---|---|
| **deepseek-ai/deepseek-v4-flash（原版）** | **已 EOL**：2026-08-07T09:00Z 後 HTTP 410 | NVIDIA 論壇 2 串＋社群 router（BlockRun）公告；本機 08-07 事件 |
| **deepseek-ai/deepseek-v4-flash-0731** | **高**：API-only「測試中」，社群回報隨機輸出/幻覺；DeepSeek 家族 08-07 整批下架的前例 | NVIDIA 論壇 #379632 |
| kimi-k2.6 / minimax-m3 | 中：免費端點 404「Function not found」供裝未解（部分帳號） | NVIDIA 論壇 #378046、#379923 |
| nemotron-3.5-lightning-30b-a3b | 低（08-11 新品），但**無公開 Free 承諾**，若付費化即失效 | NVIDIA blog 08-11 |
| 所有 Free Endpoint | **共同風險**：官方明言免費層「for prototyping、無 SLA、模型可隨時變更或移除」；先例＝GLM-4-9B-0414 無預警停用（他平台同模式） | build.nvidia.com 政策＋NVIDIA 論壇 |
| llama-3.3-70b-instruct、llama-3.1-70b、gemma-4-31b-it | 低：上線久、社群多源（OpenRouter/SiliconFlow 並存），換平台成本低 | — |

**防禦策略**：①引擎清單維持 ≥5 個並存（現行多引擎架構已符合）；②每引擎「測試 API」按鈕一鍵驗證活性；③batch 前對 deepseek 0731 輸出抽檢；④Free Endpoint 不寫死為唯一預設——品質檔位要有付費替代（BYOK）。

---

## 7. 誠實標記（限制）

1. **WMT24++/RULER 為 NVIDIA 官方模型卡自評**（Nemo 框架），有論文（arXiv:2502.12404）與複現指南（ns_wmt24pp）佐證，但非第三方獨立複測。
2. **XSCT l_trans_002 測試句僅一句**（"Hello, how are you?"），滿分飽和、鑑別力極弱——只用於「及格/不及格」判讀。
3. **Free Endpoint 資格**：kimi-k2.6 與 lightning 的免費資格為追蹤站/論壇間接證據（build.nvidia.com 前端無法程式化抓取），落地前以「測試 API」實測為準。
4. **繁中（zh-TW）專屬證據不存在於任何公開排行榜**（皆為中文簡繁混合語料）——繁中慣用語、術語翻譯品質只能靠 pdf2zh 真測（本報告以「中文分榜 Elo＋中文原生模型」作為替代代理指標）。
5. LMArena Elo 快照日期不一（2026-06～08-12）、多數標 volatile；分數差 <25 視為雜訊。

## 8. 參考來源

- NVIDIA NIM API 實測：`GET https://integrate.api.nvidia.com/v1/models`（2026-08-14，102 模型）
- NVIDIA 論壇：[deepseek-v4-pro/flash deprecated #379549](https://forums.developer.nvidia.com/t/why-were-deepseek-v4-pro-and-flash-deprecated/379549)、[deepseek removed #379558](https://forums.developer.nvidia.com/t/deepseek-v4-pro-flash-removed/379558)、[0731 模型 #379632](https://forums.developer.nvidia.com/t/nvdia-nim-deepseek-v4-flash-0731-model/379632)、[kimi-k2.6/minimax-m3 404 #378046](https://forums.developer.nvidia.com/t/function-not-found-for-account-kimi-k2-6-and-minimax-m3-return-404-on-free-endpoints/378046)
- WMT24++：arXiv:2502.12404；[llm-stats 榜](https://llm-stats.com/benchmarks/wmt24++)（人機驗證擋，數據取自模型卡與論文）
- NVIDIA 模型卡：Nemotron-3-Super/Nano（HuggingFace，WMT24++ 0.867/0.862、RULER）、[Nemotron-3-Ultra research 頁](https://research.nvidia.com/labs/nemotron/Nemotron-3-Ultra/)、[Riva-Translate HF](https://huggingface.co/nvidia/Riva-Translate-4B-Instruct)
- LMArena：arena.ai/leaderboard/text（2026-08-04 快照）；AITNT 中文分榜（NVIDIA [2026-08-04](https://www.aitntnews.com/arena/org/nvidia/chinese/)、ZAI [2026-08-12](https://www.aitntnews.com/arena/org/zai/chinese/)、MiniMax 專家榜）
- Artificial Analysis：nemotron-3-ultra [頁面](https://artificialanalysis.ai/models/nvidia-nemotron-3-ultra-550b-a55b)、glm-5.2/minimax-m3/step-3.7-flash 智力指數與速度
- XSCT Bench：[多語種翻譯 l_trans_002](https://www.xsctbench.com/testcase/l_trans_002)
- 免費層政策追蹤：[ayautomate kimi-k2.6](https://www.ayautomate.com/free-models/nvidia-nim-moonshotai-kimi-k2-6)、[40 RPM 論壇串 #377643](https://forums.developer.nvidia.com/t/nvidia-nim-api-rate-limit-increase-request-40-200-rpm/377643)
- WMT25 翻譯專用模型：Marco-MT（阿里國際，en-zh 人類評測 #1）、Hunyuan-MT-7B（騰訊，31 語對 30 冠）——**均不在 NIM 上**，僅供對照
