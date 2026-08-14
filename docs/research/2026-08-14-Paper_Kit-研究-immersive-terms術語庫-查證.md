# immersive-translate/terms 術語庫實地查證報告（Paper_Kit #84 前置研究）

- 查證日期：2026-08-14
- 查證方法：GitHub REST API + raw.githubusercontent.com 直接抓取原始檔統計（全部為一手資料，無二手轉述）
- 目標 repo：https://github.com/immersive-translate/terms

---

## 摘要（一頁結論）

本報告針對「immersive-translate/terms 術語庫整合進 Paper_Kit 自研 glossary 庫」構想進行實地查證。**關鍵結論：構想中的資料結構與實際完全不符，且存在授權紅線，整合方案必須重擬。**

| # | 項目 | 查證結果 | 對 Paper_Kit 的意義 |
|---|------|---------|-------------------|
| 1 | 目錄結構 | 不是 `locales/`＋JSON，而是 **`glossaries/`（65 個 CSV）＋ `meta/`（35 個 JSON）**；僅 zh-CN、zh-TW 兩語系＋5 個無語系後綴的「auto」檔 | 轉換器要解析 CSV，不是 JSON |
| 2 | 詞條格式 | CSV 三欄 `source,target,tgt_lng`（表頭行），**無備註／優先級／上下文欄位**；meta JSON 管分類 metadata（含 `matches` 網站限定） | 格式極簡，轉換成本低 |
| 3 | 規模 | **共 4,906 詞條**（資料列）：zh-CN 檔 3,102、zh-TW 檔 1,753、auto 檔 51；全部約 150KB，token 成本極低可整表注入 | 規模遠小於預期，可直接處理 |
| 4 | 授權（紅線） | **repo 內沒有任何 LICENSE 檔**（GitHub API `license: null`，完整 tree 108 檔掃描無 LICENSE/COPYING），README 亦無授權聲明 | **依著作權法預設為「保留所有權利」——不得直接複製、不得生成子集嵌入** |
| 5 | 維護狀態 | 最後 push 2026-07-21（約 3.5 週前）；社群 PR 合併集中在 6–7 月，8 月後停滯；open PR 3 個排隊逾月、真實 issue 僅 1 個 | 活躍度中低；「社群每天提交 PR」之宣稱不屬實 |
| 6 | 同類掃描 | PDFMathTranslate（pdf2zh）**無內建術語表**——術語表為使用者自訂 CSV 以 `--glossaries` 載入（無表頭、2 欄）；其 repo 授權 AGPL-3.0 | 兩套 CSV 格式可寫一個轉換器吃兩邊 |

**整合建議一句話**：在取得上游書面授權（或上游補上 LICENSE）之前，只做「格式參考＋自行撰寫詞條」；CSV 解析邏輯與「強制對齊注入」機制可以照常開發，詞條內容來源暫以自研／開放授權替代資料。

---

## 查證明細

### 1. 專案結構

來源：https://api.github.com/repos/immersive-translate/terms 、https://api.github.com/repos/immersive-translate/terms/git/trees/main?recursive=1

**Repo 基本資料（2026-08-14 查證）**

| 欄位 | 值 |
|------|-----|
| 建立時間 | 2025-03-28 |
| 最後 push（pushed_at） | 2026-07-21T09:01:24Z |
| default branch | main |
| stars / forks | 45 / 40 |
| open issues（含 open PR） | 4 |
| size | 244 KB |
| 全 repo 檔案數 | 108（含 65 CSV、35 JSON、4 JS、1 TS、1 YML、README、Makefile） |

**完整檔案樹（108 檔）**

- `glossaries/` — 65 個 CSV（詞條本體）
- `meta/` — 35 個 JSON（34 個分類 metadata + index.json 索引）
- `scripts/` — 4 個 Node.js（splitGlossaries.js 拆分 CSV、addLangsHash.js 生成哈希、overrideIndex.js 重寫索引、removeLangsHash.js）
- `test/` — 1 個 Deno TypeScript 效能測試
- `.github/workflows/trigger.yml` — push 到 main 後通知 immersive-translate/dash 執行 deploy-terms
- `README.md`（貢獻指南）、`Makefile`（測試/發布指令）

**語系目錄（不是目錄，是檔名後綴）**

- **zh-CN：33 個分類檔**（`[meta_name]_zh-CN.csv`）
- **zh-TW：27 個分類檔**（`[meta_name]_zh-TW.csv`）
- **auto（無後綴）：5 個**（`default.csv`、`game.csv`、`programming.csv`、`tech.csv`、`web3.csv`）
- 僅 zh-CN、zh-TW 兩種中文化；無其他語系、無 .xlsx/.txt/.tsv 等其他格式

**34 個分類（meta/index.json 的完整順序）**

default、twitter、web3、tech、news、ao3、programming、education、finance、legal、car、ecommerce、fashion、food、gardening、medical、music、pet、sports、travel、chess、game、golf、movie、photography、stellar-blade-clothing、Shelter69-Slang、Vocaloid、access-control、hd2、bg3、biology、tennis、programming-contest

> 注意：其中 6 個分類（Shelter69-Slang、Vocaloid、access-control、biology、hd2、stellar-blade-clothing）**只有 zh-CN 沒有 zh-TW**；hd2（Helldivers 2）、bg3（博德之門 3）、stellar-blade-clothing（劍星服裝）、Shelter69-Slang 等是**遊戲／社群專用詞表**，非通用術語。

### 2. 詞條格式

**CSV 格式（實際檔案內容）**

`glossaries/tech_zh-TW.csv` 全文（23 詞條）：https://raw.githubusercontent.com/immersive-translate/terms/main/glossaries/tech_zh-TW.csv

```csv
source,target,tgt_lng
Algorithm,演算法,zh-TW
Avatar,頭像,zh-TW
IP Address,IP 位址,zh-TW
Cloud Computing,雲端運算,zh-TW
Machine Learning,機器學習,zh-TW
Neural Network,神經網路,zh-TW
Operating System,作業系統,zh-TW
...
```

- 表頭固定三欄：`source`（原文）、`target`（譯文）、`tgt_lng`（目標語系碼，恆等於檔名後綴）
- **沒有備註／說明／優先級／上下文／例句欄位**——README 貢獻規範明令「不要把章節標題、備註、待確認內容（如 `?`）或說明文字放進 CSV」（https://github.com/immersive-translate/terms/blob/main/README.md ）
- 同一 CSV 內 source 不可重複；同詞不同語境需拆成更精確的 source 或改以 `matches` 限定網站

**zh-TW 與 zh-CN 的對應關係（實例對照）**

同一分類兩檔案「逐條對應」：相同 `source` 集、不同 `target`、不同 `tgt_lng`。

| source | tech_zh-CN.csv | tech_zh-TW.csv |
|--------|---------------|----------------|
| Algorithm | 算法 | 演算法 |
| Operating System | 操作系统 | 作業系統 |
| Firmware | 固件 | 韌體 |
| Database | 数据库 | 資料庫 |
| Resolution | 分辨率 | 解析度 |

（來源：https://raw.githubusercontent.com/immersive-translate/terms/main/glossaries/tech_zh-CN.csv 、同路徑 tech_zh-TW.csv）

少數分類兩檔詞數不同（food：zh-CN 51／zh-TW 55；movie：76／77；web3：58／59），顯示兩語系偶爾各自增補。

**auto 檔格式（無語系後綴）**

`glossaries/tech.csv`：`target` 與 `tgt_lng` 皆為空——只列「不翻譯的專有名詞」（OpenAI、Anthropic、Google、DeepMind…），供翻譯引擎得知應保留原文。`default.csv` 僅 2 條（LLM、LLMs）。

**meta JSON（分類 metadata）**

`meta/tech.json`（https://raw.githubusercontent.com/immersive-translate/terms/main/meta/tech.json ）結構：

```json
{
  "id": "tech",
  "name": "Technology Expert",
  "description": "Focuses on general technology concepts...",
  "author": "immersive",
  "glossary": "tech",
  "langs": ["auto", "zh-CN", "zh-TW"],
  "i18ns": { "zh-CN": {...}, "zh-TW": {...}, "en": {...}, "ja": {...}, ... }
}
```

- `langs`：該分類支援的語系清單；`i18ns`：各語系的 name/description 在地化
- 可選欄位：`matches`（限定生效網站；`meta/twitter.json` 實例含 `"twitter.com"`、`"https://platform.twitter.com/embed*"` 等 10 條規則）、`suffix`
- `author` 為分類作者（如 hd2 為 `TWSFFTS_07007`、stellar-blade-clothing 為 `MaMihLaPiNaTaPaI0`——社群詞表作者身分混合，對授權評估是額外複雜度）

### 3. 規模統計

方法：以 GitHub tree API 取得 65 個 CSV 清單 → raw.githubusercontent.com 逐一抓取 → 逐行解析統計（2026-08-14）。**全部資料列（不含表頭）共 4,906 筆**；zh-CN 檔合計 3,102、zh-TW 檔合計 1,753、auto 檔合計 51。

**逐分類詞條數**

| 分類 | zh-CN | zh-TW | auto |
|------|------:|------:|-----:|
| default | - | - | 2 |
| twitter | 10 | 10 | - |
| web3 | 58 | 59 | 8 |
| tech | 23 | 23 | 21 |
| news | 16 | 16 | - |
| ao3 | 49 | 49 | - |
| programming | 45 | 45 | 15 |
| education | 115 | 115 | - |
| finance | 28 | 28 | - |
| legal | 99 | 99 | - |
| car | 72 | 72 | - |
| ecommerce | 74 | 74 | - |
| fashion | 11 | 11 | - |
| food | 51 | 55 | - |
| gardening | 63 | 63 | - |
| medical | 89 | 89 | - |
| music | 73 | 73 | - |
| pet | 47 | 47 | - |
| sports | 24 | 24 | - |
| travel | 56 | 56 | - |
| chess | 35 | 35 | - |
| game | 67 | 67 | 5 |
| golf | 54 | 54 | - |
| movie | 76 | 77 | - |
| photography | 44 | 44 | - |
| stellar-blade-clothing | 504 | - | - |
| Shelter69-Slang | 312 | - | - |
| Vocaloid | 38 | - | - |
| access-control | 8 | - | - |
| hd2 | 467 | - | - |
| bg3 | 327 | 327 | - |
| biology | 26 | - | - |
| tennis | 55 | 55 | - |
| programming-contest | 86 | 86 | - |
| **合計** | **3,102** | **1,753** | **51** |

**規模觀察**

- 詞條大頭是**遊戲／社群專詞**（stellar-blade-clothing 504、hd2 467、bg3 327、Shelter69-Slang 312 四者合占約 1/3），對 Paper_Kit 翻譯情境用途有限
- 通用領域分類都很小：tech 23、finance 28、legal 99、medical 89、education 115、web3 58——**Paper_Kit 常用領域合計約 400 條**
- 全部資料約 150KB（http 傳輸 byte 總和約 150K）、4,906 詞條粗估 15–20K token——**整表注入提示詞完全可行**

### 4. 授權狀態（關鍵）

查證方式（三路並行，結論一致）：

1. **GitHub API** `license` 欄位為 **null**：https://api.github.com/repos/immersive-translate/terms
2. **完整 repo tree**（108 blobs）掃描 `LICENSE`/`COPYING`/`LICENSE.*` 關鍵字：**0 個檔案**：https://api.github.com/repos/immersive-translate/terms/git/trees/main?recursive=1
3. **README.md 全文**（9,358 bytes）無任何授權條款／聲明；repo 亦無 CONTRIBUTING、CODE_OF_CONDUCT、CLA/DCO 文件（tree 已確認）

**結論：該專案未附授權。** 依各國著作權法（含臺灣著作權法、美國 Copyright Act）「未授權即保留所有權利」原則：

- 不能安全地直接複製詞條內容進 Paper_Kit repo（公開與否皆同）
- 不能安全地「生成子集」後嵌入（子集複製仍是重製）
- 不能以「執行期遠端下載引用」規避（下載快取到磁碟即屬重製，且離線後仍需保存副本）
- GitHub ToS 對公開 repo 的 fork 權限（https://docs.github.com/en/site-policy/github-terms/github-terms-of-service  §D.5）僅涵蓋平台上 fork 與平台內使用之場景，**不等於授予「嵌入第三方專案再發布」的著作權再授權**

已知事實補充（不構成授權）：該專案 45 stars／40 forks，社群以 PR 形式自由貢獻；上游對詞條品質有檢核（README 規範 + Deno 效能測試 test/performance.test.ts），但**沒有任何授權管理機制**（無 LICENSE、無 CLA）。

### 5. 維護狀態

來源：https://api.github.com/repos/immersive-translate/terms/commits?per_page=30 、https://api.github.com/repos/immersive-translate/terms/pulls?state=all&per_page=15

- **最後 push：2026-07-21**（查證日 2026-08-14，靜止約 3.5 週）
- 近 30 筆 commits 時間分布：2026-03（2 筆）→ 6/5–6/16（約 13 筆，Shelter69-Slang 大量往返）→ 7/2–7/21（約 9 筆）→ **7/21 之後 0 commit**
- 已合併 PR（近 30 天）：
  - #30「增加網球與算法競賽術語庫」merged 2026-07-21（Tabris-ZX）
  - #28「新增生物學 zh-CN 術語庫」merged 2026-07-07（mmlet）
  - #26「Shelter69 玩家社群黑話」merged 2026-07-07
  - #22「博德之門 3 術語庫」merged 2026-07-02（Au3C2）
- **open PR 3 個排隊逾月**：#31 原神詞表（7/29 開）、#29 電氣工程（7/7 開）、#27 內科（6/29 開）——審核節奏慢
- **真實 open issue 僅 1 個**：#15「術語庫是否嚴格區分大小寫」（2025-12-19 提出，擱置 8 個月無回覆）；另 3 個 open 是上述 PR
- 「社群每天提交 PR」宣稱：**不屬實**。實證：社群提交集中在 6 月中–7 月中（約每週 1–3 筆），7/21 後完全停滯；維護者合併節奏為「累積一批審一次」
- 發布機制：push main → GitHub Actions trigger.yml → 向 immersive-translate/dash repo 派發 `deploy-terms` 事件（https://raw.githubusercontent.com/immersive-translate/terms/main/.github/workflows/trigger.yml ）——詞表實際消費方是 Immersive Translate 擴充套件的 dash 服務，本地無獨立工具鏈

### 6. 同類掃描：PDFMathTranslate（pdf2zh）術語表

來源：https://api.github.com/repos/Byaidu/PDFMathTranslate 、https://deepwiki.com/PDFMathTranslate-next/PDFMathTranslate-next/7.1-glossary-support 、https://github.com/PDFMathTranslate-next/PDFMathTranslate-next

- **官方 repo（Byaidu/PDFMathTranslate，36K stars）沒有內建術語表檔案**——完整 tree 76 檔掃描無任何 glossary/term/dict 檔，translator.py 亦無 glossary 程式碼；術語表是**使用者自訂 CSV**，經 CLI `--glossaries glossary1.csv,glossary2.csv`（或 TOML `glossaries` 設定）載入
- pdf2zh_next（PDFMathTranslate-next）擴充：CSV 術語表要求 **UTF-8、無表頭、每行一個詞對（source,target）、大小寫敏感、多檔合併去重**；另有 LLM 引擎專屬的自動術語提取（`--save-auto-extracted-glossary`）；非 LLM 引擎（Google/Bing/DeepL）使用術語表會報錯
- **格式對比**：pdf2zh 系「無表頭 2 欄」vs immersive terms「有表頭 3 欄（source,target,tgt_lng）」——差異小，一個轉換函式即可互吃
- **授權**：PDFMathTranslate repo 為 **AGPL-3.0**（https://api.github.com/repos/Byaidu/PDFMathTranslate license 欄位）——注意若 Paper_Kit 整合 pdf2zh 之程式碼，AGPL 的 copyleft 義務須另行評估（此處僅記錄，非本報告主題）

### 7. 資料品質／解析注意事項（實測）

對 65 個 CSV 全部 4,906 列逐行解析檢驗（2026-08-14）：

- **無任何欄位含逗號或換行**；僅 hd2 有 6 列含英文引號字元（如 `AX/LAS-5 "Guard Dog" Rover`）——上游自己的 splitGlossaries.js 就是 `line.split(',')` 的 naive 解析，Paper_Kit 轉換器用 Python csv 模組即可安全處理
- auto 檔只有 2 欄（target 空缺）為預期格式，解析器需容錯
- 同 source 跨分類重複常見（例如 Fund、Regulation 同時存在於 finance/legal 等），Paper_Kit 匯入時需自訂去重策略（按分類保留優先或採白名單覆蓋）

---

## 授權結論（紅線）

1. **紅線：不得直接複製、嵌入、或生成子集後內嵌 immersive-translate/terms 的詞條資料**（無論放進 repo、打包進 binary、或執行期下載快取）。該專案無 LICENSE 檔，法律上「保留所有權利」；詞條雖是短語翻譯（原創性主張空間有限），但其中含品牌名（OpenAI/Anthropic 等）與遊戲專名翻譯（Helldivers 等），且上游作者身分混雜（部分詞表作者欄為個人），個別授權協商亦不可行。**此紅線適用於 Paper_Kit 公開 repo 的一切整合形式。**

2. 若專案負責人評估後仍想合法整合，**唯一安全路徑是先取得授權**：
   - 於 https://github.com/immersive-translate/terms/issues 開 issue 詢問授權（建議一併請求上游補上 LICENSE 檔）
   - 或聯繫 Immersive Translate 團隊（immersive-translate org 下有主專案 immersive-translate/immersive-translate）取得書面同意並要求其開立 LICENSE
   - 獲得的授權（如 MIT／CC-BY-4.0）要「白紙黑字」寫進 Paper_Kit 的 LICENSE 與 NOTICE

3. 「參考格式、自行撰寫詞條」**無授權風險**：CSV 結構（三欄）與 meta 設計屬於不受著作權保護的介面設計；自行彙編的詞條若有參考其內容，宜改寫而非抄錄，並在文件註明「格式參考 immersive-translate/terms」。

4. PDFMathTranslate 系：repo 授權 AGPL-3.0（程式碼層），但**術語表為使用者自訂檔案、不在 repo 內**——自行撰寫的術語表無 copyleft 問題；若要複製其 next 版詞表資料，同樣要逐個確認來源授權。

## 整合建議

**方案 A（推薦）：格式參考＋自研詞表**
- 依本報告第 2 節之 CSV 結構設計 Paper_Kit 自研 glossary 庫：`source,target,tgt_lng` 三欄＋分類 metadata（含可選 `matches` 語義，轉為 Paper_Kit 的領域標籤）
- 詞條初期來源：自研彙編（技術/財經/法律/醫療等通用詞），或改用確定開放授權的詞料（如 CC 授權的術語集，另案評估）
- 轉換器（raw 抓取→CSV 轉換）照開發，但 source 設為「自研」而非上游
- 優點：零法律風險、可即刻動工；缺點：初期詞條量小

**方案 B（取得授權後）：上游整合**
- 若上游補上寬鬆授權（MIT/CC-BY）：raw 抓取 `https://raw.githubusercontent.com/immersive-translate/terms/main/glossaries/[meta]_[lang].csv` → CSV 轉換入自研庫，取 zh-TW 27 分類 1,753 條＋zh-CN 3,102 條皆可用
- 建議先做通用領域子集（tech/finance/legal/medical/education/web3/legal ≈ 400 條）而非全量（遊戲/社群詞表占 1/3，對 Paper_Kit 情境價值低且含 R18 社群用語——Shelter69-Slang、hd2 等，須避開）
- 更新機制：因上游維護節奏慢（數週一更），**「抓取快照＋人工審核入庫」優於「執行期即時拉取」**（後者連線依賴＋上游未授權時仍是重製）

**方案 C（不建議）：執行期遠端引用**
- 執行期向 raw.githubusercontent.com 拉取即時詞表，本地不保存——看似規避，但（a）未授權時快取即侵權，（b）依賴第三方網路可用性。僅在取得授權後可作為自動更新機制。

**強制對齊注入的技術結論（與整合來源無關，可先行）**
- 規模實證：全部 4,906 條約 150KB／15–20K token，通用領域子集約 400 條／1.5K token——**注入提示詞的 token 成本可忽略**
- 詞條以「強制對齊」注入時需注意上游資料特性：同詞跨分類重複（去重策略）、大小寫區分（上游 issue #15 懸而未決）、無優先級欄位（Paper_Kit 需自訂覆蓋規則）
- Paper_Kit 的 glossary 庫格式建議直接採 `source,target` 2 欄＋分類 tag，與 pdf2zh 系格式相容（互轉零成本），日後兩邊資料皆可吃

---

## 來源清單

- Repo 首頁／README：https://github.com/immersive-translate/terms
- Repo metadata（license=null、pushed_at、stars）：https://api.github.com/repos/immersive-translate/terms
- 完整檔案樹：https://api.github.com/repos/immersive-translate/terms/git/trees/main?recursive=1
- glossaries 目錄：https://api.github.com/repos/immersive-translate/terms/contents/glossaries
- 詞條樣本（tech/finance/legal/web3/hd2 等）：https://raw.githubusercontent.com/immersive-translate/terms/main/glossaries/tech_zh-TW.csv （同模式）
- meta 樣本：https://raw.githubusercontent.com/immersive-translate/terms/main/meta/tech.json 、meta/twitter.json 、meta/hd2.json 、meta/index.json
- commits：https://api.github.com/repos/immersive-translate/terms/commits?per_page=30
- PRs：https://api.github.com/repos/immersive-translate/terms/pulls?state=all&per_page=15
- Issues：https://api.github.com/repos/immersive-translate/terms/issues?state=open
- CI 發布機制：https://raw.githubusercontent.com/immersive-translate/terms/main/.github/workflows/trigger.yml
- PDFMathTranslate metadata（AGPL-3.0）：https://api.github.com/repos/Byaidu/PDFMathTranslate
- pdf2zh_next glossary 文件：https://deepwiki.com/PDFMathTranslate-next/PDFMathTranslate-next/7.1-glossary-support 、https://github.com/PDFMathTranslate-next/PDFMathTranslate-next
