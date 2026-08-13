# Free-LLM-Collection 統整查證與實作報告（PDF 翻譯免費方案）

> 日期：**2026-08-13**。範圍：GitHub [for-the-zero/Free-LLM-Collection](https://github.com/for-the-zero/Free-LLM-Collection) 所列 25 個免費 LLM API 提供者的**可用性查證**（每個都測試過）、**品質優先序**、**免費專區實作**（Paper_Kit）。
> 需求原文：「你必須每個都測試過」「對比免費API的模型品質優劣後按照優先序排列，並增設免費專區」「預設無填入API_KEY時，4個付費卡片必須顯示灰色並無法點選」「填入API_KEY項目必須多一個測試API按紐確認是否成功啟用」「所有資料以及查證比對報告必須做成一份統整詳盡報告，並同步obsidian」。
> 紅線（既有約束）：**絕不動用個人 API key 替他人翻譯**（免費方案全部獨立額度）；未發表論文不得進「資料訓練」條款免費層（Gemini/Mistral）；ChatAnywhere 排除（禁商用＋轉發中介＋機密）。

---

## 1. 執行摘要

| 項目 | 結果 |
|---|---|
| 端點活性探測 | **25/25 提供者全測**：22 個存活（認證流程正常）、1 個 DNS 死亡（Celebras）、1 個逾時待定（G4F）、1 個政策排除（ChatAnywhere） |
| 免費層政策查證 | 研究代理查證（官方文件優先）——**HuggingFace「300 RPH 免費大模型」宣稱不實**（實為 $0.10/月 credit）；OpenRouter 實際 50 RPD 非 repo 所載 200 |
| 深度品質真測 | SiliconFlow 免費 Qwen3-8B vs 付費 DeepSeek 同段對譯（樣本存檔）——**9B 免費模型術語瑕疵實證**（「點-wise」vs「逐點」） |
| 新增免費 LLM 引擎 | **6 個**（依品質優先序）：NVIDIA NIM ＞ ModelScope ＞ Groq ＞ OpenRouter ＞ 智譜 ＞ Gemini |
| 付費卡灰化 | 無 API key → 4 付費卡灰色不可點（+BYOK 免費 LLM 卡無 key 也灰） |
| 測試 API 按鈕 | 設定頁每張 key 引擎卡（10 張）加「測試 API」按鈕——GET /models 零成本驗證 |
| 測試 | 新增 20 個測試（registry 不變式 7＋主頁 11＋設定頁 3＋adapter 1 前已加） |

## 2. 查證方法（三層，缺一不可）

1. **文獻查證**（研究代理）：官方文件優先（SiliconFlow/OpenRouter/HF/ModelScope/NVIDIA/Bigmodel 官方 docs）＋第三方評測（Artificial Analysis、LMArena、WMT25、JP-TL-Bench）。產出《[查證與品質優先序.md](./2026-08-13-Free-LLM-Collection-查證與品質優先序.md)》。
2. **端點活性探測**（本 session 實測）：對 25 個提供者的 OpenAI 相容端點以假 key POST `/chat/completions`（＋UA 對抗 Cloudflare 1010、GET /models 校正 nvidia）——**每個都測試過**（工具：`scripts/free_llm_probe.py`、`probe_retest.py`、`dns_check.py`）。
3. **深度真測**（本 session 實測）：SiliconFlow 免費模型實際翻譯一段 Transformer 論文技術文本（`scripts/free_llm_quality.py`、`sf_free_models.py`）——樣本存 `docs/research/free_llm_samples/`。

## 3. 端點活性探測結果（25 提供者全測，2026-08-13）

方法：POST `{base}/chat/completions`（假 key `test-probe-key`）→ 401/403/400 = 端點存活且認證流程正常；404 = 路徑待校正；連線失敗 = 端點死亡。

| 提供者 | 結果 | 判定 | 備註 |
|---|---|---|---|
| SiliconFlow | 401 Token is invalid | ✅ 存活 | 國際站 api.siliconflow.com（帳號實測） |
| OpenRouter | 401 Missing Authentication | ✅ 存活 | |
| Intern AI 書生 | 401 user authenticate failed | ✅ 存活 | |
| Gemini | 400 Please pass a valid API key | ✅ 存活 | OpenAI 相容端點實測存在（報告疑慮排除） |
| Cohere | 401 Incorrect API key | ✅ 存活 | |
| 智譜 Bigmodel | 401 令牌已過期 | ✅ 存活 | |
| NVIDIA NIM | GET /v1/models 200（POST 404） | ✅ 存活 | 官方端點確認（模型清單含 yi-large 等） |
| LLM7 | 400 Model 'test' unavailable | ✅ 存活 | |
| ModelScope | 400 Invalid model id | ✅ 存活 | |
| Kilo | 401 PAID_MODEL_AUTH_REQUIRED | ✅ 存活 | |
| HuggingFace | 401 Invalid username or password | ✅ 存活 | 但免費層政策查證不實（見 §4） |
| Groq | 401 Invalid API Key（UA 修正後） | ✅ 存活 | 初探 403/1010＝Cloudflare 機器人防護，瀏覽器 UA 即通 |
| Celebras | **DNS 不存在** | ❌ 死亡 | api.celebras.ai Name or service not known（域名疑似失效） |
| Mistral | 401 Invalid API Key | ✅ 存活 | 但資料訓練條款排除（紅線） |
| OpenCode Zen | 401 Model test is not supported | ✅ 存活 | |
| DXNT | 401 invalid_api_key | ✅ 存活 | |
| Agens AI | 401 無效的令牌 | ✅ 存活 | |
| Cloudflare | 401 Authentication error | ✅ 存活 | 需帳號 ID（路徑含 <ACCT>） |
| SenseNova 商湯 | 401 Forbidden | ✅ 存活 | |
| G4F | 25s 逾時（DNS 正常） | ⚠️ 待定 | 域名解析 OK（Cloudflare IP）但 API 無回應——慢/掛待複測 |
| 訊飛星火 | 401 apikey not found | ✅ 存活 | HMAC 簽章（非純 Bearer） |
| InceptionLab | 400 model value_error | ✅ 存活 | |
| Poolside | 403 please check the api-key | ✅ 存活 | |
| ChatAnywhere | 401 wrong api key | ✅ 存活 | **政策排除**（#28 三重紅線） |
| 肖恩AI | 401 Invalid token | ✅ 存活 | 簽到制不適合自動化 |

**結論：25 個中 22 個端點存活、1 個死亡（Celebras）、1 個待定（G4F）、1 個政策排除（ChatAnywhere）。**

## 4. 免費層政策查證摘要（詳見研究報告）

| 提供者 | 免費層 | 關鍵數字 | 判定 |
|---|---|---|---|
| NVIDIA NIM | ✅ 免卡 | ~40 RPM、無日總量 | **落地** |
| ModelScope | ✅ 需阿里雲實名 | 2,000 RPD（熱門模型實測 ~500/日） | **落地** |
| Groq | ✅ 免卡 | 30 RPM / 6,000 TPM / 14,400 RPD | **落地** |
| OpenRouter | ✅ 免卡 | 20 RPM / **50 RPD**（$10 終身升 1,000）——repo 的「200 RPD」查無來源 | **落地** |
| 智譜 Bigmodel | ✅ 需實名 | GLM-4-Flash/4.7-Flash 無 token 上限、併發 2 | **落地** |
| Gemini | ✅ 免卡 | gemma-4-31b 15 RPM / 1,500 RPD | **落地＋資料訓練警語** |
| SiliconFlow | ✅ 免卡 | 每模型 1,000 RPM / 50K TPM | 已在（siliconflowfree） |
| HuggingFace | ❌ 宣稱不實 | 官方僅 $0.10/月 credit | **排除** |
| Mistral | ✅ 但資料訓練 | — | **排除**（紅線） |
| ChatAnywhere | ✅ 但轉發中介 | 30 req/day | **排除**（三重紅線） |
| Celebras | ❌ DNS 死亡 | — | **排除** |

## 5. 品質優先序與落地 6 引擎

品質依據（研究報告 §1）：AA Index（Kimi-K2.6 54 為開放 #1）、WMT24++ 翻譯分（nemotron-3-super 86.7% 免費群最佳）、Elo（gemma-4 1,451）等。

| 優先序 | 引擎 id | 模型 | 品質定位 | 免費額度 | 端點 |
|---|---|---|---|---|---|
| **1** | nvidia | deepseek-ai/deepseek-v4-flash | T1/T2（AA ≈52） | 40 RPM、無日總量 | integrate.api.nvidia.com/v1 |
| **2** | modelscope | deepseek-ai/DeepSeek-V4-Pro | T1（AA 52–53） | 2,000 RPD | api-inference.modelscope.cn/v1 |
| **3** | groq | openai/gpt-oss-120b | T2（GPQA 80.1%） | 30 RPM、14,400 RPD | api.groq.com/openai/v1 |
| **4** | openrouter | nvidia/nemotron-3-super-120b-a12b:free | T2（翻譯 86.7%） | 20 RPM、50 RPD | openrouter.ai/api/v1 |
| **5** | bigmodel | glm-4.7-flash | T3（實測退步警訊） | 無 token 上限 | open.bigmodel.cn/api/paas/v4 |
| **6** | gemini | gemma-4-31b-it | T2（Elo 1,451、262K） | 15 RPM、1,500 RPD | generativelanguage.googleapis.com/v1beta/openai |

架構：6 引擎全走 **provider=openai**（pdf2zh-next `--openai` 三旗標共用——base-url/model/key 由 spec 提供，不需新 adapter；`pdf2zh_next_adapter.py` openai 分支已 TDD 完成）。

## 6. 深度品質真測（同段文本對譯）

源文本：Transformer 論文（Attention Is All You Need）§3.1 節 1,200 字（`free_llm_samples/source-text.txt`）。

### 6.1 實測發現：GLM-4-9B-0414 已停用

SiliconFlow 的 `THUDM/GLM-4-9B-0414` 回 `403 Model disabled`——**研究報告列出的免費模型與現況脫節**（免費模型會輪換）。改用現行免費 `Qwen/Qwen3-8B` 實測成功（首跑逾時＝免費佇列壅塞，重試即通）。

### 6.2 品質對比（Qwen3-8B 免費 vs DeepSeek 付費）

| 面向 | Qwen3-8B（免費） | DeepSeek deepseek-chat（付費） |
|---|---|---|
| 術語翻譯 | 「點-wise」「位置-wise」——**中英混雜** | 「逐點全連接層」——精確 |
| 格式 | 無段落、擠成一塊 | 完整分段（編碼器/解碼器分節） |
| 語意正確性 | ✅ 整體正確 | ✅ 整體正確 |
| 評析 | T4 定位實證：短段落可用、複雜技術長文吃力 | 專業級 |

**結論：免費 9B 級模型適合一般文件；技術論文建議 NVIDIA/ModelScope 的旗艦免費模型（研究報告 T1/T2 定位）或付費引擎。** 樣本全文：`free_llm_samples/Qwen3-8B.txt`（註：檔案名沿用 GLM 命名——內容為 Qwen3-8B 實測）、`free_llm_samples/deepseek-chat.txt`。

## 7. 實作清單（本 session 變更）

| 檔案 | 變更 |
|---|---|
| `src/paper_kit/infrastructure/engine_registry.py` | +6 免費 LLM spec（openai provider、各異 base_url/model、card_desc/info 含隱私警語）；+`UI_FREE_KEY_ENGINE_IDS` tuple（優先序）；deepseek spec 補 base_url（測試 API 探測用） |
| `src/paper_kit/infrastructure/pdf2zh_next_adapter.py` | +`elif cfg.provider == "openai"` 分支（--openai 三旗標） |
| `src/paper_kit/presentation/app.py` | 主頁 +「免費 LLM（自備免費 key）」區（6 卡進 engine_cards dict）；付費卡/BYOK 卡灰化（統一 `_card_disabled` 判定：機密＋key 兩層）；`_pick_engine` key 阻擋；設定頁 key 迴圈 +6 引擎；+「測試 API」按鈕（`_probe_api` GET /models，10s timeout，async） |
| `scripts/free_llm_probe.py` / `probe_retest.py` / `dns_check.py` | 端點活性探測工具（可重跑） |
| `scripts/free_llm_quality.py` / `sf_free_models.py` / `sf_models_structure.py` / `db_keys.py` | 深度真測與 DB 檢查工具 |

## 8. 測試矩陣（「每個都測試過」逐項狀態）

| 層級 | 項目 | 狀態 |
|---|---|---|
| ✅ 端點活性 | 25/25 提供者 | **全測**（§3）——22 存活、1 DNS 死、1 逾時、1 排除 |
| ✅ 認證流程 | SiliconFlow 真 key | 實測（免費模型 403 disabled 發現→換 Qwen3-8B） |
| ✅ OpenAI 相容端點 | Gemini 端點 | curl 實測（400 valid key＝端點通） |
| ✅ 品質真測 | SiliconFlow Qwen3-8B vs DeepSeek | 實測（§6） |
| ✅ 翻譯端到端 | siliconflowfree 通道 | 切片 6 冒煙已測（599 passed 時代） |
| ⏳ 深度真測（需註冊） | NVIDIA/ModelScope/Groq/OpenRouter/智譜/Gemini | **待免費 key**——端點已實測存活＋政策已查證；品質數據引用第三方評測（研究報告 §1）；落地前各平台申請 key 後以「測試 API」按鈕逐個驗證 |
| ❌ 不適用 | HF/Mistral/ChatAnywhere/Celebras | 政策排除或端點死亡（查證完畢，非疏漏） |

**誠實標記**：6 個落地引擎的**翻譯品質深度真測需要各自平台的免費 key**（本機只有 SiliconFlow key）——端點活性已全測、政策已全查證、品質已文獻定位；深度真測列為「待 key」並提供測試按鈕讓使用者/他人拿到 key 後一鍵驗證。任何「已全部真測」的宣稱都是假的——本報告以三層測試矩陣誠實分層。

## 9. 使用說明（拿到工具的人）

1. 主頁「免費翻譯（不需 API key）」：零 key 直接翻（上游代理轉發，品質低）。
2. 主頁「免費 LLM（自備免費 key）」：品質接近付費——NVIDIA/ModelScope 等官方免費 key 填入設定頁即可（各平台註冊均免綁卡；ModelScope/智譜需實名）。
3. 設定頁：每引擎「測試 API」按鈕——填 key 後一鍵驗證（GET /models，零成本）。
4. 無 key 的付費卡灰色不可點——**不會誤觸收費**。
5. 機密文件（R18/隱私/未發表）：只有 DeepSeek 純文字可用；Gemini 免費層資料訓練條款——未發表論文禁用（卡片 ⓘ 已標註）。

## 10. 待辦

- [ ] NVIDIA/ModelScope/Groq/OpenRouter/智譜/Gemini 免費 key 申請後深度真測（品質樣本補入本報告）
- [ ] G4F 端點複測（25s 逾時——疑似掛或極慢）
- [ ] 免費 LLM 引擎端到端冒煙（有 key 後跑 1 頁 PDF 實譯）

## 參考

- [Free-LLM-Collection repo](https://github.com/for-the-zero/Free-LLM-Collection)
- [查證與品質優先序報告](./2026-08-13-Free-LLM-Collection-查證與品質優先序.md)（文獻查證詳版）
- 品質樣本：`docs/research/free_llm_samples/`（source-text / Qwen3-8B / deepseek-chat）
