# NVIDIA NIM google/gemma-4-31b-it 實測評估（2026-08-14）

> 目的：評估 NVIDIA NIM 免費端點上的 `google/gemma-4-31b-it`（與 Paper_Kit 預設引擎
> SiliconFlow 上的同一模型）——品質／速度／節流／視覺能力，判斷可否作為替代引擎。

## 結論（TL;DR）

**同一模型、同一權重——翻譯品質與視覺能力一致；NIM 側的最大差異是「免費＋40 RPM 節流」與「thinking 陷阱」。**

| 維度 | NVIDIA NIM | SiliconFlow（付費層） |
|---|---|---|
| 價格 | **免費**（無點數、RPD 無限、免綁卡） | 0.0012 USD / 1K in + 0.0012 USD / 1K out |
| 速率限制 | **40 RPM**／並發 2-5（503 風險）→ 需節流 | 無公開硬性 RPM（共享額度有 QPS 節流） |
| 品質（翻譯） | 實測優秀（見下） | 歷史基線：T1（預設引擎） |
| 速度 | thinking 關：25–37 tok/s、TTFT <1s | 同級（同模型） |
| 視覺（圖像輸入） | 實測支援 | 支援（預設視覺引擎） |
| 機密文件 | 不可用（送 NVIDIA 雲端） | 不可用（送第三方雲端） |
| SLA | 免費無 SLA（429 需退避） | 付費較穩 |

## 實測方法

- 端點：`https://integrate.api.nvidia.com/v1`（OpenAI 相容）
- 2026-08-14 凌晨實測（臺灣時間）
- 測試內容：學術論文段落英→繁中、繁中→英、圖像輸入（形狀辨識）、端到端 pdf2zh 管線（真實 PDF 第 1 頁）

## 實測數據

| 測試 | thinking | 牆鐘 | 輸出 tok/s | 結果 |
|---|---|---|---|---|
| 英→繁中（學術段落） | **開** | **116.3s** | 7.6 | ⚠️ 輸出變成逐句草稿格式（Source/Draft 批註） |
| 英→繁中（學術段落） | 關 | 10.8s | 17.5 | ✅ 優質學術翻譯 |
| 繁中→英 | 開 | 40.6s | 38.9 | ⚠️ 同上格式問題 |
| 速度複測 ×3 | 關 | 4.1–6.9s | 25.6–36.7 | ✅ 穩定 |
| 圖像輸入（形狀辨識） | — | 2.5s | — | ✅ 正確辨識「2 形狀：藍色方形＋紅色圓形」 |
| pdf2zh 端到端（真實 PDF p1） | — | 完整管線 | — | ✅ mono+dual PDF 產出、標題翻譯正確 |

## 關鍵發現

### 1. thinking 陷阱（重要）

`chat_template_kwargs.enable_thinking=True` 時：
- **慢 10 倍**（116s vs 11s）
- 輸出變成「逐句草稿＋批註」格式（`*Source:*` / `*Keywords:*` / `*Draft:*`），**不適合直接當翻譯結果**

→ 翻譯管線必須確保 thinking 關閉。pdf2zh 端到端實測正常（未傳 enable_thinking 時行為正常）。

### 2. 翻譯品質（thinking 關）

學術段落英→繁中實測樣本（節錄）：

> 視覺語言模型（Vision-language models）在近年取得了顯著進展。然而，其在細粒度視覺推理任務（fine-grained visual reasoning tasks）——例如文件版面分析（document layout analysis）、圖表解讀（chart interpretation）及公式提取（formula extraction）——上的表現仍然有限……

- 學術語氣正確、專有名詞雙語對照、繁體用語標準（「解讀」非「解釋」、「範式」）
- 與 SiliconFlow 版歷史品質基線一致（同模型同權重）

### 3. 節流

- NIM 免費層：40 RPM／並發 2-5 → 503 排隊。Paper_Kit 已內建節流（`--qps 0.6`＝每 1.67 秒一發＝36 RPM 留餘裕、`--pool-max-workers 1`）
- 100 頁論文估算：請求間隔 1.5–3 分＋生成 2–4 分＋版面排版 8–25 分 ≈ **15–30 分鐘**（可接受）

## 建議

1. **NIM 的 gemma-4-31b-it 可作為 SiliconFlow 的免費替代**——品質一致、零成本
2. **不要開 thinking**（10× 慢＋格式破壞）——pdf2zh 管線預設行為正確
3. 機密文件仍維持 DeepSeek 專用（兩邊視覺雲端都不行）
4. 若在意 SLA／穩定，付費 SiliconFlow 仍是保險選項（每月數百頁才約 NT$10–30 級）

## 待補測

- SiliconFlow 側即時對比：本機無 SF API key，無法實測——品質基線引用既有歷史紀錄（同模型）。取得 key 後可補跑同段落對比。
