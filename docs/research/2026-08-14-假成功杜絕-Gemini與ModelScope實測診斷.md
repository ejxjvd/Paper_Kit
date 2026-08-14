# 假成功杜絕：Gemini 與 ModelScope 實測診斷（#78）

> 2026-08-14 實測。常駐問題解決包：使用者 ≥3 次回報同症狀「引擎未產出任何 PDF
> (log 無 MonoPDF/DualPDF 行) ── 上游可能失敗但回傳成功」，「測試 API」卻 200 OK。

## 症狀

```
錯誤：引擎未產出任何 PDF (log 無 MonoPDF/DualPDF 行) ── 上游可能失敗但回傳成功
```
任務建立後 9-10s 即失敗（真翻譯該花 30s+）；「測試 API」按鈕顯示連線成功（HTTP 200）。

## 根因 1：Gemini 模型 ID 404

`gemini-3-pro-latest`（無 `models/` 前綴）在 OpenAI 相容端點
`https://generativelanguage.googleapis.com/v1beta/openai` 回 **404 NOT_FOUND**
（「not supported for generateContent」）——**ListModels 有顯示但不可生成**。

pdf2zh_next 對 HTTP 錯誤**吞錯 rc=0 退出**（log 只有「Subprocess initialization
error: Error code: 404」）→ parse_output 找不到 MonoPDF/DualPDF 行 → 假成功。

### Gemini 28 模型可用性（curl chat/completions 實測）

| 群 | 模型 | 結果 |
|----|------|------|
| ✅ 200（7） | models/gemini-2.5-flash、2.5-flash-lite、3.1-flash-lite-preview、3.5-flash、3.5-flash-lite、3.6-flash、gemini-flash-latest | 全帶 `models/` 前綴可生成 |
| ⏳ 429（數個） | gemini-3.1-pro-preview 等 | 免費層限流（重試仍 429） |
| ❌ 400 | antigravity / deep-research / tts | 非 chat 用法 |
| ❌ 404 | aqa / audio / live / embedding | 不存在 |
| ❌ 404 | **gemini-3-pro-latest**（有/無前綴皆） | 不存在於該端點 |

### 8 模型 pdf2zh 真翻譯（帶 `--openai` 旗標）

gemini-3-pro-latest ❌ 5s rc=0 無產出（404 重現）；**7 個帶前綴全成功**：
2.5-flash 43s／2.5-flash-lite 24s／3.1-flash-lite-preview 24s／3.5-flash 38s／
3.5-flash-lite 22s／3.6-flash 39s／gemini-flash-latest 40s（皆產出 2 PDF）。

## 根因 2：ModelScope 跨站 key 401

使用者管道全為國際站——在 **modelscope.ai（國際站）** 申請 key，但 Paper_Kit 原連
**中國站** `api-inference.modelscope.cn`。**兩站 key 不互通**：國際站 key 對中國站
回 401「Authentication failed」→ pdf2zh 吞錯 → 假成功。

陷阱：**GET /models 不驗 key**（假 key `ms-FAKE` 也回 200 清單）——「測試 API」
按鈕只打 GET /models，所以顯示成功。實測：國際站 `api-inference.modelscope.ai`
同一 key GET 200（key 有效），但生成前須**綁阿里雲帳號**（401「Please bind your
Alibaba Cloud account before use. You can bind it at:
https://modelscope.ai/my/settings/account」）。

另：網路流傳「去 `ms-` 前綴即可」——實測剝離前綴後仍 401（那是中國站另一種坑；
本例是站別問題）。

### ModelScope 兩站模型清單

- 中國站（.cn）42 個：deepseek-ai/DeepSeek-V4-Flash-0731、DeepSeek-V4-Pro、
  ZhipuAI/GLM-4.7-Flash、GLM-5.2、stepfun-ai/Step-3.7-Flash 等。
- 國際站（.ai）39 個：deepseek-ai/DeepSeek-V3.1、V3.2-Exp、V4-Pro、
  Qwen-Ambassador/Qwen3.7-Max、3.8-Max、zai-org/GLM-4.7-Flash、GLM-5.2 等。
- 國際站生成前置：綁阿里雲帳號；未綁定所有模型 POST 都 401。

## 修復（v0.1.6，三層杜絕假成功）

| 層 | 變更 |
|----|------|
| spec | gemini-pro model → `models/gemini-3.5-flash`（實測可生成） |
| spec | modelscope base_url → `api-inference.modelscope.ai`（國際站）；移除 bigmodel（中國站死卡：免費 GLM 需中國手機＋實名，國際站用戶拿不到 key；Z.AI 免費模型未驗證） |
| 測試 API | `_probe_api(base_url, key, model)` 加 POST /chat/completions（max_tokens=1 零成本）驗證「模型可生成」——GET /models 只驗 key 活性的盲區補上 |
| 錯誤訊息 | `_diagnose_no_output` 掃引擎 log：404→「模型不存在」、429→「限流」、401/authentication→「key 無效」（ModelScope 錯誤訊息不含 401 字樣，regex 補 authentication） |
| **preflight** | `Pdf2zhNextAdapter.translate()` 覆寫：openai provider＋有 key 引擎翻譯前 POST 驗證 key＋模型，非 200 直接 EngineError 帶診斷、**引擎根本不上**——吞錯假成功從根杜絕 |

## 驗證（真 runner、真 API、產出存在）

- 691 tests 全綠（+7 新測試：spec model／國際站端點／無 .cn 不變式／404/429/
  authentication 診斷／probe 生成驗證／preflight 4 件）。
- Gemini 真翻譯：修復後 gemini-pro spec 走 adapter 真跑 fixture PDF（2 頁）
  → 84s 產出 mono.pdf (484KB)＋dual.pdf (870KB)。使用者 9s 假成功 → 真成功。

## 教訓

1. 「測試 API」只驗 key 活性（GET /models）不夠——**必須驗「模型可生成」**
   （POST 一次 max_tokens=1，零成本）。ListModels 有顯示 ≠ 可生成。
2. **國際站與中國站 key 不互通**（ModelScope 實證；智譜 bigmodel.cn vs z.ai 亦同）。
3. 引擎吞錯（HTTP 錯誤 rc=0）是假成功的根源——Paper_Kit 側補 preflight +
   錯誤診斷雙層，不依賴上游修正。

## 補測（2026-08-14 下午，三平台新 key）

### Z.AI（智譜國際站）——免費模型查證完成 ✅

| 模型 ID | 結果 |
|---------|------|
| `glm-4.7-flash`（小寫） | ✅ 200 可生成（**思考型**）；真翻譯 275s 產出 mono 482KB＋dual 868KB |
| `glm-4.5-flash`（小寫） | ✅ 200 可生成（非思考）；真翻譯 11min 未產出（免費層疑似限速）——主推 4.7-flash |
| `GLM-4.7`／`GLM-4.5-air`（大寫） | ❌ 429 code 1113「餘額不足」（付費模型） |
| `GLM-4.7-Flash`（大寫） | ❌ 429 code 1305 過載／或 400 |

**陷阱**：GET /models 清單只列大寫付費版（glm-4.5/4.6/4.7/glm-5/5.1/5.2），**免費模型小寫 ID 不在清單**——直接打小寫可生成。v0.1.7 回補 bigmodel 卡為 zai（api.z.ai，model=glm-4.7-flash 小寫）。

### 阿里雲 DashScope 國際站——key 有效但模型未開通 ⏳

`sk-ws-` key GET /models 200（清單完整：qwen3.7/3.8-max、deepseek-v4、glm-5.2…），但**所有模型 POST 403 `AccessDenied.Unpurchased`**（含 qwen-flash 免費款）——Model Studio 國際站需先在控制台**開通模型**（API 無法代辦）。待使用者開通後全測。

### ModelScope 國際站——仍待綁阿里雲 ⏳

重測仍 401「Please bind your Alibaba Cloud account」——需瀏覽器登入綁定，API 無法代辦。39 模型全測待綁定。

## 補測二（2026-08-14 晚，ModelScope 綁阿里雲後全測）✅

使用者綁定阿里雲（UI「Bind Alibabacloud: ejxjvdbk1837@gmail.com ✓」）後立即重測。

### 全模型可用性（42 模型，串行 1.5s 間隔）

- **36/42 可生成**（POST chat/completions 200）。
- 403 無權限（3）：`Qwen-Ambassador`／`Qwen3.7-Max`／`Qwen3.7-Plus`／`Qwen3.8-Max`（領先模型要付費）。
- 400 無 provider（3）：`Jan-nano`／`MiniMax-M3`／`Qwen3-4B`。
- 502 非 chat（2）：`Qwen-Image-Edit`×2（生圖模型，名稱無生圖字樣——另一個「清單有顯示≠可用」變體）。
- 並行（xargs -P 8）大量 429——**限流以模型/帳號為單位**，串行才可信。

### ⚠️ 思考型模型陷阱（本次最重要發現）

| 模型 | 結果 |
|------|------|
| `deepseek-ai/DeepSeek-V3.1` | ✅ 200 真翻譯 **40.9s** 產出 mono 484KB＋dual 869KB（non-thinking） |
| `deepseek-ai/DeepSeek-V4-Pro` | ⚠️ HTTP 200 但 **`message.content=None`**（thinking 模型，reasoning 耗盡 max_tokens；max_tokens=2000 時正常，=200 時 completion_tokens=201、content=None） |
| `zai-org/GLM-5.2` | ⚠️ 同上（思考型） |
| `zai-org/GLM-4.7-Flash` | ❌ HTTP 200 但 **`choices=null` 空殼**（usage 全 0；非思考型陷阱，是該模型在 ModelScope 上不可用） |

- **機制**：pdf2zh 請求的 max_tokens 被 thinking 模型的 `reasoning_content` 耗盡 →
  `response.choices[0].message.content` = None → pdf2zh `content.strip()` TypeError 崩潰。
  **HTTP 200 但內容不可用**——「清單有顯示≠可生成」的新變體：**HTTP 200 ≠ 可用**。
- **修復**：registry 預設 model 換 non-thinking `deepseek-ai/DeepSeek-V3.1`
  （card_desc/info 註明陷阱；測試加不變式：預設模型不得含 V4/GLM）。
