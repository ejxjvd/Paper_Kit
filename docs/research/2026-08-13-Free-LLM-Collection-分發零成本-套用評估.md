# Free-LLM-Collection 分發零成本套用評估（Paper_Kit 交付他人使用）

> 撰寫日期：**2026-08-13**。資料來源：[for-the-zero/Free-LLM-Collection](https://github.com/for-the-zero/Free-LLM-Collection)（25 個免費 LLM API 清單）。
> 問題：**「能不能套用在 Paper_Kit 上，給其他人使用，而不消耗我自己的金錢？」**
> 與既有報告的關係：《[免費LLM-API-分析與套用評估.md](./免費LLM-API-分析與套用評估.md)》（#28）回答「省我自己的錢」；
> 《[2026-08-13-Free-LLM-Collection-查證與品質優先序.md](./2026-08-13-Free-LLM-Collection-查證與品質優先序.md)》回答「免費層存在性＋品質排序」。
> 本報告專注第三視角：**交付他人情境下的零成本套用可行性與實用性**。測試中 session 的未提交修改未動。

---

## TL;DR（結論先行）

1. **能套用，而且已經內建**：Paper_Kit 目前已登記 **6 支「BYOK 免費 key」引擎**（NVIDIA NIM／ModelScope／Groq／OpenRouter／智譜／Gemini）＋ **3 支「免 key」引擎**（siliconflowfree／google／bing）。加引擎＝`engine_registry.py` 單點（每支一行 spec），adapter 已支援 OpenAI 相容端點。
2. **「不消耗我的錢」的關鍵不是「免費 API」，而是「key 不共享」**：Free-LLM-Collection 全部是**註冊即送的個人免費額度**——每個人自己註冊、自己填自己的 key，你的帳號、你的 $10 餘額**完全不參與**。這是唯一同時滿足「零成本＋零風險」的路線。
3. **免費額度本質**：$0 單價（免費模型）不扣任何餘額——連使用者自己的錢也不扣，只受**限流**（RPM/RPD）約束。免費層的「成本」不是錢，是速率與品質。
4. **交付他人的注意事項**：①每人註冊門檻不同（中國平台要實名＋手機；國際平台免卡）②免費層無 SLA、429 是常態（系統已有重試）③機密文件不可用（`sensitive_ok=False` 已內建）④Gemini 免費層有資料訓練條款——未發表論文不可走。
5. **不要做的事**：把**你的**付費 key 放進去（燒你的錢）、集中共用單一免費 key（限流＋政策風險）、任何轉發中介（三重紅線，#28 §三）。

---

## 一、問題拆解：什麼是「不消耗我的金錢」

### 1.1 免費 API key 的真實本質

Free-LLM-Collection 收錄的每一家都是「註冊 → 拿 key → 用個人免費額度」：

| 特性 | 說明 |
|---|---|
| key 綁帳號 | 免費額度掛在**你的帳號**上，限流（RPM/RPD）以帳號/key 為單位計算 |
| 免費模型 = $0 單價 | 標「免費」的模型價格為 0，**不扣任何餘額**——包括你自己的充值餘額（你存的 $10 只會在你用**付費模型**時被扣） |
| 限流是唯一約束 | 免費層的瓶頸是「每天/每分鐘 N 次」，不是金額 |
| 額度隨時可變 | 免費政策是贈品，供應商可隨時調整（Gemini 2025-12 砍 50–80%、2026-04 Pro 全撤免費層即前例） |

### 1.2 三種「讓別人用」的模式對比

| 模式 | 你的錢 | 你的 key | 適用性 |
|---|---|---|---|
| **A. BYOK（每人各註冊各填 key）** | 0 消耗 | 不外流 | ✅ **推薦、已內建**——manga-translator-ui 等成熟工具標準做法 |
| **B. 集中共用你的免費 key** | 0 消耗 | ⚠️ 外流 | ❌ 限流共享（一群人共用一份額度）＋key 若公開＝被人拿去亂用／觸發封鎖 |
| **C. 集中共用你的付費 key** | 💰 消耗 | ⚠️ 外流 | ❌ 每筆呼叫都燒你的餘額＋風險同上 |

**結論：模式 A 是唯一正確答案**。問句「總不可能放我個人的 key」的答案不是「找免費 API」，而是「**key 根本不該進交付物**」——這正是 Paper_Kit 自票 20 起的設計（每引擎獨立 key、遮罩回顯、未填攔截）。

---

## 二、Paper_Kit 現況盤點（套用面已完成度）

| 面向 | 現況 | 狀態 |
|---|---|---|
| 免費 key 引擎（BYOK） | `engine_registry.py` 登記 6 支：`nvidia`／`modelscope`／`groq`／`openrouter`／`bigmodel`／`gemini`（全 `provider=openai`、`needs_key=True`、`sensitive_ok=False`） | ✅ 已加（測試中 session，未提交） |
| 免 key 引擎 | `siliconflowfree`（GLM-4-9B，上游代理＋QPS 節流）／`google`／`bing`（上游已棄用，保留不推薦） | ✅ 已提交 |
| Adapter 支援 | `pdf2zh_next_adapter.build_command` 新增 `provider=openai` 分支（`--openai` 三旗標：model/key/base-url 全由 spec 提供，`pdf2zh_next_adapter.py:69-77`） | ✅ 已加（未提交） |
| UI 分區 | 主頁三區：主引擎卡＋「免費翻譯（不需 key）」＋「免費 LLM（自備免費 key）」；app.py 只迭代 tuple（`UI_FREE_KEY_ENGINE_IDS`） | ✅ 已加（未提交） |
| 端點活性探測 | `scripts/free_llm_probe.py`：25 提供者假 key 探測全測——本區 6 家全部存活（401/400 認證流程正常） | ✅ 已實測 |
| 品質優先序 | `2026-08-13-Free-LLM-Collection-查證與品質優先序.md` §3：NVIDIA NIM 居首（T1/T2 品質＋40 RPM＋無日總量） | ✅ 已查證 |
| 成本顯示 | 免費引擎 0 成本條目＋`CostService` 已支持（siliconflowfree 先例，#28 §四） | ✅ 零改動 |
| 限流對策 | `CliAdapterBase` 暫時性簽名重試（2s/4s 退避共 2 次）；免費層 429 較頻繁，若實測不足再強化 | ⚠️ 夠用、可強化 |

> 註：以上「已加」欄目為 2026-08-13 測試中 session 的未提交變更（`git status` 顯示 6 檔 M＋探測 scripts 未追蹤）。**本報告不修改任何既有檔案**；該 session 提交後本表即為現況。

---

## 三、6 支免費 key 引擎——他人使用情境實用性評估

基準（沿用 #28 §一）：單本論文 300–600 次 API 呼叫、單日多本可達 1,200+ 次；未發表論文不得進「資料訓練」條款免費層。

| 引擎 | 品質（查證） | 額度 | 使用者註冊門檻 | 他人使用適合度 | 備註 |
|---|---|---|---|---|---|
| **NVIDIA NIM**（`deepseek-v4-flash` 等） | T1/T2（AA 52–54） | ~40 RPM、無日總量 | 開發者帳號即可、免卡、**無實名要求** | ★★★★★ 國際用戶首選 | 無 SLA；429 退避；模型可能輪換 |
| **ModelScope**（`DeepSeek-V4-Pro` 等） | T1（AA 52–53） | 2,000 RPD（熱門模型實測 ~500/日、可能 insuff. quota） | **需阿里雲實名＋綁定** | ★★★★ 中國用戶品質天花板 | 額度動態分配、不穩 |
| **Groq**（`gpt-oss-120b`） | T2（GPQA 80.1%） | 30 RPM／6,000 TPM／14,400 RPD | 免卡、無實名 | ★★★★ 國際用戶高品質備援 | TPM 小→長文分塊易 429 |
| **OpenRouter**（`nemotron-3-super:free`） | T2（翻譯 WMT24++ 86.7%，免費群最佳） | 20 RPM／50 RPD（$10 終身 → 1,000 RPD） | 註冊即得、免卡 | ★★★ 試用入口 | 50 RPD 遠不夠批次——**別期待用它翻整本** |
| **智譜 BigModel**（`glm-4.7-flash`） | T3（第三方實測大幅退步警訊） | 無 token 上限、併發 2 | 手機＋實名 | ★★★ 中國用戶跑量源 | 併發 2 對批次是天然限流；品質先試譯再定 |
| **Gemini**（`gemma-4-31b-it`） | T2（Elo 1,451、262K 長文） | 15 RPM／1,500 RPD | 免卡、**EU 不可用免費層** | ★★★ 非敏感文件高日額度 | **免費層資料訓練＝未發表論文紅線** |

**給他人的選用指引（可寫進交付 README）**：
- 國際用戶（無中國手機）：NVIDIA NIM（主力）→ Groq（備援）→ OpenRouter（試用）
- 中國用戶：ModelScope（品質）→ NVIDIA NIM（穩定）→ 智譜（跑量）
- 任何人的第一步：用免 key 的 `siliconflowfree` 先跑通流程，滿意再申請免費 key

---

## 四、驗證：你的 $10 到底會不會動

| 情境 | 你的餘額 | 說明 |
|---|---|---|
| 別人用**自己的**免費 key（6 支任一） | ✅ 零影響 | key 綁他人帳號，帳單歸他人 |
| 別人用免 key 引擎（siliconflowfree） | ✅ 零影響 | 上游代理（pdf2zh-next 維護者伺服器）免費轉發，QPS 節流 |
| 別人用你的 key 翻付費模型 | ❌ 每筆扣錢 | 唯一會燒錢的用法——BYOK 設計已排除 |
| 你自己在 Paper_Kit 用 gemma-4-31B-it（付費模型） | ⚠️ 微量扣款 | 你的 paste-vision 主模型同款：$0.13/$0.40 per M tokens，單頁翻譯約 $0.001 級（#23 實測整本 NT$5–8） |

---

## 五、風險與紅線（交付情境更嚴）

1. **資料訓練條款**：Gemini 免費層（「用於改進產品」）、Mistral（同意訓練）——**別人的未發表論文**送進去比自用更不可接受。已內建 `sensitive_ok=False` 防止機密模式誤用，但一般模式仍靠使用者判斷——交付文件要寫清楚。
2. **轉發中介**（chatanywhere 類、`siliconflowfree` 的上游代理本質同類）：檔案經第三方轉手。`siliconflowfree` 已列入卡面警告（「檔案會上第三方伺服器——機密文件禁用」）。
3. **免費政策隨時變**：額度/模型輪換是常態——引擎 spec 是資料不是程式，改一行即換。
4. **無 SLA**：免費層不保證可用性——批次任務失敗靠重試兜底；重要文件建議用付費引擎。
5. **商用條款**：多數免費層明示「僅供評估/非商業」——若交付對象是商業用途，需自行確認條款。

---

## 六、若要再加新免費提供者（給未來的自己）

`engine_registry.py` 單點：複製一支 `provider="openai"` 的 spec（填 `base_url`／`model`／`card_desc`／`info`）＋加入 `UI_FREE_KEY_ENGINE_IDS` 對應位置即可；adapter 已通用（`pdf2zh_next_adapter.py:69-77` 三旗標）。落地前照既有紀律：`scripts/free_llm_probe.py` 假 key 探測存活 → `free_llm_quality.py` 試譯一段 → 品質符合再上 UI。

---

## 七、結論

| 問題 | 答案 |
|---|---|
| 免費 API key 能套用到 Paper_Kit 嗎？ | **能**——6 支 BYOK 免費引擎＋3 支免 key 引擎已內建 |
| 給其他人用會消耗我的錢嗎？ | **不會**——BYOK 讓每個人用各自的免費額度，你的帳號完全不參與；唯一會燒錢的用法（共享你的付費 key）已被架構排除 |
| 品質夠嗎？ | 免費層天花板＝NVIDIA NIM 的 DeepSeek-V4-Flash（T1/T2）——**學術級堪用**；9B 級（siliconflowfree）只適合試用 |
| 交付時要注意什麼？ | 每人自己註冊（國際用戶選 NVIDIA/Groq/OpenRouter）；機密文件紅線；免費層無 SLA |
| 現在能交付嗎？ | 功能已就緒（測試中 session 收尾中）——交付文件只需加一段「免費引擎選用指引」（§三表格） |

**一句話**：你要的不是「免費 API」，而是「每個使用者自己的 API」——Paper_Kit 的 BYOK 架構已經把這件事做好了，Free-LLM-Collection 補上的是「每人註冊免費額度的入口選單」。

---

## 附：資料來源

- [for-the-zero/Free-LLM-Collection](https://github.com/for-the-zero/Free-LLM-Collection)（2026-08-13 查證）
- 《[2026-08-13-Free-LLM-Collection-查證與品質優先序.md](./2026-08-13-Free-LLM-Collection-查證與品質優先序.md)》§2/§3（提供者逐項查證、品質優先序、來源彙整）
- 《[免費LLM-API-分析與套用評估.md](./免費LLM-API-分析與套用評估.md)》（#28）§三/§四（chatanywhere 三重紅線、工程套用影響）
- `src/paper_kit/infrastructure/engine_registry.py`（引擎 spec 現況，2026-08-13）
- `src/paper_kit/infrastructure/pdf2zh_next_adapter.py:69-77`（`provider=openai` 分支）
- SiliconFlow 官方：[Rate Limits 文件](https://docs.siliconflow.cn/cn/userguide/rate-limits/rate-limit-and-upgradation)、[限流 FAQ](https://docs.siliconflow.cn/cn/faqs/misc_rate)
