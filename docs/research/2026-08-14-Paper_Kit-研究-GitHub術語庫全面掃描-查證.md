# Paper_Kit 術語庫來源全面掃描與查證報告（zh-TW 合法整合候選）

- 查證日期：2026-08-14
- 查證方法：WebSearch／WebFetch 實地檢索 + GitHub REST API（經 WebFetch）直接查 repo metadata；全部宣稱附來源 URL
- 前置文件：`2026-08-14-Paper_Kit-研究-immersive-terms術語庫-查證.md`（本報告為其接續）
- 目標：為 Paper_Kit 自研 265 條繁中詞表尋找「可合法整合＋完整性高＋zh-TW 覆蓋」的替代或互補來源

---

## 摘要（一頁結論）

前研究已確認 immersive-translate/terms 無 LICENSE（保留所有權利，紅線不可嵌入）。本次全面掃描的結論：

| # | 來源 | 規模級 | 授權 | zh-TW 品質 | 推薦度 |
|---|------|--------|------|-----------|--------|
| 1 | **國家教育研究院樂詞網**（學術名詞 206 類約 193 萬則＋雙語詞彙 21 類約 2 萬則） | 極大 | 政府資料開放授權條款-第1版（無償、可重製改作商業、可再授權、註明出處） | 高（官方審譯會，臺灣正體） | **高（主來源）** |
| 2 | **Microsoft Terminology Collection**（近 100 語種，zh-TW 數萬條級） | 大 | Language Portal Materials License：明示允許「整合進其他術語集合／作為基礎 IT 詞庫」，惟非 OSI 開放授權，需審閱＋聲明 | 高（微軟官方 zh-TW 在地化） | 中高 |
| 3 | **microsoft/vscode-loc**（zh-hant 語言包） | 中（數千 UI 字串） | MIT（repo LICENSE.md） | 高 | 中高 |
| 4 | **香港律政司綜合法律詞彙**（60,000+ 條） | 大 | 官方許可條款（可下載複製，產品複製需聲明＋彌償；2025-11 版） | 中（繁體但為香港法律用語，需台灣化映射） | 中 |
| 5 | **金管會體系雙語詞彙**（金融監理＋銀行/保險/檢查/證期） | 小-中 | 金管會網站資料開放宣告＝政府資料開放授權條款-第1版 | 高 | 中 |
| 6 | **Wiktionary／Kaikki.org**（中文 dump） | 極大 | CC BY-SA 4.0＋GFDL | 中低（繁簡混存、社區內容，清洗成本高） | 中 |
| 7 | **OpenCC**（s2tw/s2twp 台灣用語轉換） | 工具 | MIT | ——（作為 zh-CN→zh-TW 轉換層） | 高（工具） |
| 8 | Mozilla zh-TW／LibreOffice zh_TW／Chromium/AOSP zh-TW | 中-大 | MPL-2.0／MPL-2.0＋多授權／BSD-3／Apache-2.0 | 高（但為 UI 字串非術語對，萃取需清洗） | 中 |
| 9 | CC-CEDICT | 大（12 萬條） | CC BY-SA 3.0 | 低（大陸用法為主；繁體欄多為簡轉繁） | 低-中 |
| 10 | g0v/moedict-data-terms | 工具 | MIT | ——（僅爬取腳本，詞條本體仍是樂詞網） | 低（工具） |
| 11 | OMW／COW／中研院 CWN | 大 | 組件各異；CWN 僅學術禁商業 | CWN 為臺灣正體但**禁止商用**；COW 為簡中 | 低（CWN 排除） |
| 12 | UNTERM、WIPO Pearl、Apple、Google、dict.cc、IMF、UMLS/SNOMED | —— | 未授權匯出／ToS 禁散布／付費 | —— | 排除或待申請 |

**一句話結論**：最優整合路徑是「樂詞網（政府開放授權）為主來源＋微軟術語庫（條款允許之用途）與 vscode-loc（MIT）補 IT 通用詞＋金管會/律政司深化法金領域＋OpenCC（MIT）作簡中源轉換層」。所有候選皆可在三欄 CSV（source,target,tgt_lng）格式落地，清洗成本以樂詞網與微軟 TBX 最低。

---

## 背景

- Paper_Kit 已有自研 265 條繁中詞表（AI／統計／通用技術／醫學／法學／金融）。
- 前研究（2026-08-14）實地查證 immersive-translate/terms：repo 無 LICENSE 檔（GitHub API `license: null`、完整 tree 掃描無授權檔），依著作權法預設「保留所有權利」；其社群授權請求 issue 停滯。**紅線：不得複製、不得生成子集嵌入、不得執行期快取。**（見前報告第 4 節）
- 本任務：不限 immersive 系，全面掃描 GitHub 與開源生態的術語庫/詞表/翻譯記憶，為自研詞表找替代或互補來源。
- 補充背景：國發會「雙語資料庫學習資源網」（bilingual.ndc.gov.tw，108 年上線）為英語學習資源入口；原行政院研考會「雙語詞彙資料庫」已於 2012 年併入國家教育研究院「雙語詞彙、學術名詞暨辭書資訊網」（現名樂詞網）——即下述樂詞網 21 類公告詞彙之來源（https://open2.idataiwan.com/info/663358 、https://open2.idataiwan.com/info/663362 ）。

## 方法

1. 檢索工具：WebSearch（多組中英關鍵字）、WebFetch（官方授權頁、GitHub REST API、HuggingFace dataset 卡、資料庫首頁）。
2. 查證原則：每個來源以「一手來源」確認——授權看 LICENSE 檔／官方授權頁／資料來源聲明；規模看官方敘述或實際下載統計；zh-TW 品質以台灣用語判準（打印→列印、激光→雷射、服務器→伺服器、鼠標→滑鼠、信息→資訊、網絡→網路、內存→記憶體）抽樣評估。
3. 授權紅線（沿用前研究）：無 LICENSE 檔＝保留所有權利，不可複製/嵌入/執行期快取；GitHub ToS 的 fork 權限不等於再授權；「官方說可下載」不等於「可再散布嵌入」，須找到授權依據。
4. 驗證限制：樂詞網官網部分頁面（about/2、download/）伺服器回應標頭異常致直接抓取失敗，改以政府公開資料目錄（open2.idataiwan.com、scidm.nchc.org.tw）與多來源交叉驗證；Microsoft 現行術語頁 2019 後結構變更（直接 URL 404），以 Wayback 存檔＋HuggingFace 官方資料卡交叉驗證。未取得一手確認的項目均標「待確認」。

---

## 來源清單

### A 組：GitHub 開源術語庫／翻譯記憶

#### A1. immersive-translate/terms — 排除（紅線）
前報告已詳查：4,906 條（zh-TW 27 分類 1,753 條）、無 LICENSE、維護停滯。本報告不再重複；紅線維持：**不得以任何形式整合**（https://github.com/immersive-translate/terms ，授權查證見前報告）。

#### A2. g0v/moedict-data-terms — 低（工具）
- 內容：g0v「開放語料庫專案」，含 `academic-terms/`（NAER 學術名詞爬取＋HTML→CSV 轉換腳本）與 `public-terms/`（雙語詞彙爬取腳本）；**實際詞條資料未提交 repo**（data/csv、data/html 僅 .gitkeep 佔位，由腳本執行時自樂詞網下載）。
- 條數／領域：repo 內唯一資料檔為 `categories.csv`（領域清單）；詞條本體＝樂詞網內容。
- zh-TW 品質：取決於樂詞網（高），但本 repo 無資料可直接嵌入。
- 授權：root LICENSE + academic-terms/LICENSE.md + LICENSE-DATA.md 三檔，GitHub API 標示 **MIT**（https://api.github.com/repos/g0v/moedict-data-terms ）——腳本層可自由使用；**詞條層仍回歸樂詞網授權**。
- 格式可匯入性：腳本是 Node/Python，可參考其下載與解析流程（MIT 無障礙）。
- 推薦度：低（工具層參考價值；資料來源直接取樂詞網更快）。

#### A3. openl-translate/ai-dictionary — 低
- 內容：OpenL（openl.io）的「AI 術語字典」，含定義與發音（LoRA、RAG、Prompt Engineering、Embedding 等）。
- 條數／領域：AI/ML 術語數十條級；以「英英定義＋多語 README」為主，未證實提供「EN→zh-TW 詞對」資料表（README 中文版為 zh-CN）。
- 授權：GitHub API `license: MIT`（https://api.github.com/repos/openl-translate/ai-dictionary ）。
- 推薦度：低（字典非詞對；zh-TW 覆蓋未證實；對自研 265 條增益有限）。

#### A4. python/python-docs-zh-tw — 低（僅參考用語）
- 內容：Python 官方文件臺灣繁體翻譯計畫（280 stars，活躍）；repo 內建 zh-TW 術語表（argument→引數、iterate→疊代、function→函式、object→物件、return→回傳、loop→迴圈等約 40 條，為高品質台灣技術用語）。
- 授權：GitHub API license 欄位 = **Other（NOASSERTION）**（https://api.github.com/repos/asdfghjkl123620/python-docs-zh-tw 查得父 repo 同）；Python 文件本體於 docs.python.org 以 **CC BY-NC-SA** 授權（含非商業限制）——**只可作用語對照參考，不可整表嵌入**。
- 推薦度：低（條數太少；授權未確立；可當自研詞表的品質校準樣本）。

#### A5. LCTT/TranslateProject（Dict.md）— 排除
- 中國 LCTT 翻譯團隊術語詞典（Fork→复刻、Live→立付、Pod→容器荚 等）；**簡體中文、無授權聲明** → 不符合 zh-TW 目標與授權紅線（https://github.com/LCTT/TranslateProject/blob/master/Dict.md ）。

#### A6. 開源軟體本地化翻譯記憶（UI 字串，非術語庫，可萃取）

| 專案 | 授權 | 證據 | zh-TW 品質 | 備註 |
|------|------|------|-----------|------|
| microsoft/vscode-loc（VS Code zh-hant 語言包） | **MIT** | LICENSE.md（https://github.com/microsoft/vscode-loc/blob/main/LICENSE.md ）；zh-hant 屬 Core 語言 | 高（微軟官方 zh-TW） | 數千條 UI 字串，JSON/XLIFF 需解析；PR 不接受翻譯修正（MLCP 為單一來源） |
| Mozilla zh-TW（Firefox l10n） | **MPL-2.0**（檔頭逐檔標示） | https://hg.mozilla.org/l10n-central/zh-TW/ （MozTW 維護，Pontoon 更新） | 高（台灣社群在地化） | UI 字串 TM；檔級 copyleft，萃取條目須保留 MPL 標示 |
| LibreOffice zh_TW | **MPL-2.0**（Weblate 專案頁標示；發行套件另混 Apache-2.0/LGPL-3/CC0/BSD） | https://translations.documentfoundation.org/projects/website/newdesign/zh_Hant/ | 高 | 辦公室/通用技術詞 |
| Chromium zh-TW | BSD-style（檔頭） | https://codereview.chromium.org/2280143002/ 等檔頭 | 高 | 需自行提取；工程量大 |
| AOSP zh-TW | Apache-2.0（AOSP 慣例） | 未逐一取證單檔，屬專案層慣例 | 高 | 同上 |

- 價值：通用技術領域的高品質 zh-TW 用語「語料」，可經高頻詞統計萃取成術語對；但這些是句子/字串層翻譯記憶，**不是術語表**，萃取＋清洗成本中高。
- 推薦度：中（vscode-loc 因 MIT＋微軟品質為其中最高）。

### B 組：政府／官方雙語詞彙

#### B1. 國家教育研究院樂詞網（terms.naer.edu.tw）— 高（主來源）
- 內容：學術名詞 **206 類約 193 萬則**、雙語詞彙 **21 類約 2 萬則**（原研考會/國發會政府雙語詞彙）、辭書 9 部約 6 萬則；每年新增修訂約 3 萬則（https://open2.idataiwan.com/info/691292 、https://terms.naer.edu.tw/mysite/about/2/ ）。
- 領域覆蓋（論文翻譯情境全命中）：統計學、數學、物理、化學、資訊與通訊、電機電子、機械工程、生命科學、醫學、法律、經濟、金融、教育、管理學、社會學等（206 類，下載專區依領域整批下載：https://terms.naer.edu.tw/download/ ）。
- zh-TW 品質：**高**。由國家教育研究院審譯會制度審定，以臺灣正體為準（如「演算法、資料庫、韌體、解析度」）；部分詞條可能並列簡體異名，匯入時抽樣人工檢核即可。
- 授權：**政府網站資料開放宣告**——「無償、非專屬、得再授權」提供公眾使用；得不限時間及地域重製、改作、編輯、公開傳輸或為其他方式利用，開發各種產品或服務（加值衍生物）；授權不會嗣後撤回、無須書面授權；使用時應註明出處；範圍不及於專利商標（https://terms.naer.edu.tw/mysite/about/2/ ）。data.gov.tw 上之 NAER 學術名詞資料集明確標示「**政府資料開放授權條款-第1版**」（如教育學學術名詞 2,198 筆 CSV、化學名詞-常見類 138 筆 CSV：https://open2.idataiwan.com/info/663358 、https://scidm.nchc.org.tw/dataset/insight_classification_dataset_5_3 之教育學資料集）。
- 格式可匯入性：**高**。data.gov.tw 提供 CSV（欄位「英文名稱、中文名稱」）即可直轉三欄 CSV；樂詞網下載專區依領域整批下載；另《中小學常用中英雙語詞彙彙編》電子書亦可下載（https://terms.naer.edu.tw/download/467/ 、https://terms.naer.edu.tw/publish/1/637/ ）。
- 推薦度：**高**。唯一同時滿足「條數極大＋領域全覆蓋＋臺灣正體官方品質＋明確開放授權＋CSV 可匯入」的來源。

#### B2. 金管會體系雙語詞彙 — 中
- 內容：金融監督管理委員會「雙語詞彙」專頁（金融檢查、聯合檢查、風險導向金融檢查等：https://www.fsc.gov.tw/ch/home.jsp?id=178&parentpath=0,6 ）＋各局處分類詞彙（金融業、銀行業、保險業、金融檢查、證券期貨業雙語詞彙）。
- 規模：網頁表格數百條級（未見整包資料檔公告）。
- zh-TW 品質：高（官方金融監理用語）。
- 授權：金管會網站資料開放宣告＝**政府資料開放授權條款-第1版**（無償、非專屬、得再授權、可重製改作、註明出處；宣告頁更新 2022-12-15：https://www.fsc.gov.tw/ch/main.jsp?websitelink=artsublink.jsp&dataserno=201604250004 ）。
- 格式：HTML 表格需爬取；清洗中等。
- 推薦度：中（量小但授權明確、金融術語權威，補自研金融類）。

#### B3. 衛福部體系醫療詞彙 — 低
- 國健署「雙語詞彙」頁（健康促進、健康識能、高齡友善城市等：https://210.241.78.32/Pages/Bilingual.aspx?nodeid=4411 ）；衛福部另以公文附件提供身心障礙類別英譯等。
- 授權：政府網站內容依政府網站資料開放宣告原則（未逐一確認該頁宣告）；格式為網頁表格需爬取。
- 推薦度：低（量小、無整包資料、無統一醫療術語開放庫）。

#### B4. 中央機關一般職稱雙語詞彙（data.gov.tw）— 低
- 中央機關一般職稱中英對照（2013 年建置，政府資料開放授權條款-第1版：https://scidm.nchc.org.tw/en/dataset/best_wish6320 ）。
- 領域為行政職稱，非論文翻譯情境；推薦度：低。

#### B5. 教育部／國教院《中小學常用中英雙語詞彙彙編》— 中
- NAER 2018-12 出版之電子書（terms.naer.edu.tw/download/467/ 下載；審譯委員會含數學/物理/化學/電機電子資訊等）：https://terms.naer.edu.tw/publish/1/637/ 。
- 授權同樂詞網開放宣告；條數數百條級（基礎詞彙）；推薦度：中（可作基礎教育詞彙補充，但樂詞網主庫已涵蓋）。

#### B6. 香港律政司綜合法律詞彙（glossary.doj.gov.hk）— 中
- 內容：英中＋中英雙向合併詞彙，六司處（民事、憲制、國際法律、法律草擬、法改會秘書處、刑事檢控）編製，**超過 60,000 條**，來源含香港法例、法庭案例（https://www.info.gov.hk/gia/general/202112/30/P2021123000239.htm 、https://www.glossary.doj.gov.hk/ ）。
- 下載：網站提供 XML／CSV／PDF／RTF 下載（每次下載超過 10,000 條會警告），含英中、中英及各司處分卷。
- zh-TW 品質：**中**——繁體中文但為**香港法律用語**（與臺灣用語有系統性差異，如申索/按金/檢控/聆訊等），嵌入前需「香港→台灣」映射表；法律領域覆蓋極廣（60K 條），遠勝其他法律詞源。
- 授權：**有正式許可條款**（政府擁有版權；一般使用可下載/列印/散布；大量複製或產品複製須遵從「Terms and Conditions for Mass Replication or Product Reproduction」——條目須準確複製、產品內載明聲明（政府擁有版權、依許可複製、政府不擔保準確性、詞彙網站免費公眾瀏覽）、不得暗示政府認可、使用者彌償義務、違約自動終止；條款 2025-11 版；洽詢 glossary_enquiry@doj.gov.hk）。詳見網站 Terms of Use／Copyright Policy 連結（https://www.glossary.doj.gov.hk/ ）。
- 格式可匯入性：高（XML/CSV 直轉）。
- 推薦度：中（授權可用但附產品聲明＋彌償義務，且用語須台灣化映射）。

#### B7. 授權基礎：《政府資料開放授權條款-第1版》
- 民國 104-07-27 訂定：授權不限目的（含商業）、時間、地域；非專屬、不可撤回、免授權金；可重製散布改作再授權；利用衍生資料須依「顯名聲明」標示原資料提供機關；不含專利商標（條文範例：https://data.nantou.gov.tw/pl/specification 、臺北市資料大平臺 https://data.taipei/rule/ ）。樂詞網、金管會、data.gov.tw 各資料集皆採此條款。

### C 組：大廠術語庫

#### C1. Microsoft Terminology Collection — 中高（條件式）
- 內容：微軟產品術語庫，近 100 語種（含 zh-TW）；每條含 Concept ID、定義、源語/目標語術語；官方 .tbx 下載（MicrosoftTermCollection.tbx，免註冊）：https://www.microsoft.com/en-us/language/terminology （2019 存檔頁：https://web.archive.org/web/20190328164030/https://www.microsoft.com/en-us/language/terminology ）。
- 規模：官方未公布逐語言精確條數；HuggingFace 官方鏡像 microsoft/ms_terms 資料集規模標示 10K–100K 列（全語系合計）；zh-TW 屬微軟完整本地化核心語言，條數為數萬條級（**本次未取得一手精確計數，列待補項目**）：https://huggingface.co/datasets/microsoft/ms_terms 。
- 領域：通用 IT／軟體／雲端／生產力／遊戲／Office——正好覆蓋 Paper_Kit 的「通用技術」類。
- zh-TW 品質：**高**（微軟官方 zh-TW 在地化，含台灣用語差異）。
- 授權：下載即同意 License Agreement（Microsoft Language Portal Materials License + Microsoft Terms of Use）；HF 資料卡明確描述允許用途：「**develop localized versions of applications that integrate with Microsoft products**」與「**integrate Microsoft terminology into other terminology collections or serve as a base IT glossary**」（整合進其他術語集合／作為基礎 IT 詞庫）——文字上涵蓋 Paper_Kit 用例；惟屬條件式授權非 OSI 開放授權，建議法務審閱＋於 Paper_Kit NOTICE 標示來源與條款（HF 卡 license 欄位 ms-pl 指資料集包裝層，資料本身仍受上述條款：https://huggingface.co/datasets/microsoft/ms_terms ）。
- 格式可匯入性：TBX 需解析工具（中清洗）；HF parquet 亦可直接讀取。
- 推薦度：中高（授權允許目標用途，但需審閱與聲明；條數/品質/格式皆佳）。

#### C2. Apple 術語表 — 排除
- Apple 對開發者提供 AppleGlot glossaries 下載（https://developer.apple.com/localization/resources/ ），但 ToS 不允許複製散布詞表（社群實證討論：https://developer.apple.com/forums/thread/662152 ）；授權綁 Apple 產品本地化脈絡 → 不符合整合需求。

#### C3. Google — 不適用
- Google 未提供公開術語庫下載管道（本次檢索查無）；其 Cloud Translation 的 glossary 為客戶自建資料，非開放來源。

### D 組：開放詞典／知識庫

#### D1. Wiktionary（zh.wiktionary.org）＋Kaikki.org 機器可讀 dump — 中
- 授權：與維基詞典相同——**CC BY-SA 4.0 與 GFDL 雙授權**（Kaikki 各語頁明示：https://kaikki.org/zhwiktionary/alphabetical.html 、https://kaikki.org/ ）；派生資料須以 CC BY-SA 發布。
- 規模：全語言數百萬條；中文 dump 含繁簡條目。
- zh-TW 品質：**中低**——維基詞典中文內容繁簡混存、一詞多義、社區撰寫；可抽「EN lemma → 繁中 gloss」詞對，但需大量清洗＋繁簡正規化＋台灣用語過濾。
- 格式：Kaikki zhwiktionary JSON dump 可直接解析（https://kaikki.org/zhwiktionary/alphabetical.html ）。
- 推薦度：中（量極大但清洗成本高；CC BY-SA 派生義務須與 Paper_Kit 對外授權相容性一併評估）。

#### D2. CC-CEDICT — 低-中
- 授權：**CC BY-SA 3.0**（官方頁：https://cc-cedict.org/wiki/start ；Wikipedia 記述同）；2024-01-22 約 122,444 條（https://en.wikipedia.org/wiki/CC-CEDICT ）。
- 內容：中英詞典，含簡體/繁體/拼音/英釋；**以大陸用法為主**，繁體欄多為簡轉繁字面（「软件」的繁體欄是「軟件」而非「軟體」），台灣用語品質低——但可經 OpenCC s2tw 轉換後再人工抽檢補救。
- 推薦度：低-中（量大；zh-TW 品質低；CC BY-SA 派生義務）。

#### D3. Open Multilingual Wordnet／Chinese Open Wordnet（COW）— 低
- 授權：OMW 為組件式彙編，各詞網授權不同（globalwordnet 資源表：https://globalwordnet.github.io/resources/wordnets-in-the-world 之 Chinese Wordnet/COW 條目指向 Princeton WordNet license：https://wordnet.princeton.edu/license-and-commercial-use ，PWN 現行 CC BY 4.0）；**COW 為大陸簡體中文** → 非台灣用語；OMW 彙編層授權需逐組件確認。
- 另：臺灣中研院「中文詞彙網路 CWN 2.0」為臺灣正體，但授權明示「僅供學術研究、不得商業、未經同意不得轉載」（https://lopentu.github.io/CwnWeb/ 、https://tmc.ling.sinica.edu.tw/copyright_ch/ 同類宣告）→ **紅線排除**。
- 推薦度：低（COW 簡中；CWN 禁商用）。

#### D4. dict.cc — 排除
- 2005 年由 GPL 改為**專有授權**（Wikipedia：https://en.wikipedia.org/wiki/CC-CEDICT 所在條目頁外的 dict.cc 條目 https://en.wikipedia.org/wiki/Dict.cc ）；且以德英詞對為主，無中英詞對 → 不符合。

#### D5. Tatoeba — 低（情境不符）
- 平行句子語料（CC BY 2.0 FR），非術語對；可用於抽取搭配但非詞表來源 → 不列入整合路徑。

#### D6. OpenCC — 高（工具層，非資料來源）
- MIT 授權之簡繁轉換庫（https://github.com/BYVoid/OpenCC ），內建 **s2tw／s2twp 台灣用語詞庫**（鼠標→滑鼠、打印→列印、軟件→軟體、互聯網→網際網路 等，含臺灣 IT 用語擴充詞庫；NEWS.md 記載詞庫更新：https://raw.githubusercontent.com/BYVoid/OpenCC/master/NEWS.md ）。
- 定位：作為「任何 zh-CN 詞源的 zh-TW 化」自動轉換層＋自研詞表的台灣用語校正工具（詞庫與程式分離，MIT 下可自由擴展）。
- 推薦度：高（整合成本低、立即提升 zh-TW 覆蓋）。

### E 組：醫學／法學／金融專用

| 來源 | 狀態 | 說明 |
|------|------|------|
| MeSH（NLM） | 低 | NLM 為美國政府作品＝**公有領域**（NCBI-PD notice：https://spdx.org/licenses/NCBI-PD.html ；NLM 著作權頁）；但**無官方繁中版**（本次檢索未見衛福部/國衛院等官方 zh-TW MeSH），英文詞表對 zh-TW 詞對無直接產出 |
| UMLS | 排除 | 需註冊並簽署免費授權協議，散布受限；Metathesaurus 不得直接再散布 |
| SNOMED CT | 排除 | 付費／會員國授權制，臺灣非會員 |
| 中研院 CWN 2.0 | **排除（紅線）** | 僅學術、禁商業、禁未同意轉載 |
| UNTERM（聯合國） | 排除/待申請 | 六種官方語含中文；資料庫 © 聯合國（©2000–）；未見批量匯出授權管道 |
| WIPO Pearl | 低 | 約 20 萬條、10 語（含中文，**繁簡未證實**）；一般資料授權未明（僅 COVID-19 詞集明示免費下載：https://etradeforall.org/es/node/9283 ），API 需申請（https://www.wipo.int/zh/web/wipo-pearl/w/news/2021/news_0004 ） |
| IMF《英漢國際貨幣基金組織詞彙手冊》 | 排除 | 紙本出版品（1995/1999 版，芝加哥大學圖書館館藏），無開放資料管道 |
| 香港律政司 | 中 | 見 B6（60K 法律詞條，官方許可條款） |
| 金管會 | 中 | 見 B2（金融雙語詞彙，第1版授權） |

---

## 評比表（量化快覽）

| 來源 | 條數級 | 領域覆蓋 | zh-TW 品質 | 授權 | 格式可匯入 | 推薦度 |
|------|--------|---------|-----------|------|-----------|--------|
| 樂詞網（NAER） | 193 萬＋2 萬 | 全領域（統計/資通/醫/法/經金…206 類） | 高 | 政府資料開放授權條款-第1版 | 高（CSV/ODS） | **高** |
| Microsoft Terminology | 數萬條級（zh-TW） | 通用 IT/軟體/生產力 | 高 | 條件式（允許整合進術語集合＋作基礎 IT 詞庫；需審閱） | 中高（TBX/parquet） | 中高 |
| vscode-loc zh-hant | 數千字串 | 通用技術（IDE/開發工具） | 高 | MIT | 中（JSON/XLIFF 萃取） | 中高 |
| 律政司法律詞彙 | 60K | 法律（香港用語） | 中（需台灣化映射） | 官方許可（產品聲明＋彌償） | 高（XML/CSV） | 中 |
| 金管會雙語詞彙 | 數百 | 金融監理 | 高 | 政府資料開放授權條款-第1版 | 低-中（HTML 爬取） | 中 |
| 教育部中小學雙語彙編 | 數百 | 基礎教育詞彙 | 高 | 政府資料開放授權條款-第1版 | 中 | 中 |
| Wiktionary/Kaikki | 百萬級 | 全領域（噪音高） | 中低（繁簡混存） | CC BY-SA 4.0＋GFDL | 高（JSON dump） | 中 |
| Mozilla zh-TW／LibreOffice zh_TW | 萬級字串 | 通用技術 | 高 | MPL-2.0（檔級 copyleft） | 中 | 中 |
| CC-CEDICT | 12 萬 | 通用（大陸用法） | 低 | CC BY-SA 3.0 | 高 | 低-中 |
| g0v/moedict-data-terms | 0（工具） | —— | —— | MIT（工具層） | —— | 低（工具） |
| OMW/COW | 大 | 語意網路（簡中） | 低 | 組件各異（PWN CC BY 4.0） | 中 | 低 |
| openl ai-dictionary | 數十 | AI/ML | 未證實 zh-TW | MIT | 低 | 低 |
| 衛福部/國健署詞彙 | 數十-百 | 公衛 | 高 | 政府網站宣告原則 | 低（網頁） | 低 |
| MeSH（EN） | 大 | 醫學（無繁中） | —— | 公有領域（美政府） | 中 | 低 |
| UNTERM/WIPO/Apple/Google/dict.cc/IMF/UMLS/SNOMED/CWN/LCTT | —— | —— | —— | 未授權匯出/ToS 禁散布/付費/學術限定 | —— | 排除或待申請 |

---

## 推薦整合路徑（Top 3 具體做法）

### 路徑 1（主來源）：樂詞網全領域詞表 → 三欄 CSV
1. 依領域下載：`https://terms.naer.edu.tw/download/` 依領域整批下載（統計學、數學、物理、化學、資訊與通訊、電機電子、生命科學/醫學、法律、經濟、金融…），或直接取 data.gov.tw 的 NAER 學術名詞 CSV 資料集（欄位「英文名稱、中文名稱」）。
2. 轉換：Python csv 模組 → 自研庫三欄格式（source,target,tgt_lng）；欄位對映後僅需極少清洗。
3. 品質把關：抽樣人工檢核（1）繁簡異名（2）台灣用語判準（打印/列印 等四項）；（3）多譯名情形採白名單優先。
4. 合規：NOTICE 檔加「顯名聲明」——資料來源：國家教育研究院樂詞網，依政府資料開放授權條款-第1版利用（可再授權，故與 Paper_Kit 對外授權相容，不污染）。
5. 預期效果：自研 265 條 → 數萬條級（全領域），zh-TW 官方品質、零法律風險。

### 路徑 2（IT／通用補強）：Microsoft Terminology Collection + vscode-loc
1. 自 Language Portal 下載 zh-TW .tbx（或讀取 HF parquet microsoft/ms_terms），TBX 解析（Concept ID/Definition/Source/Target）→ 三欄 CSV；與路徑 1 依「官方優先＋去重」合併。
2. 授權處理：此授權文字明示允許「整合進其他術語集合／作為基礎 IT 詞庫」，故可嵌入；仍建議法務審閱原文條款＋於 NOTICE 標示（「術語部分來源：Microsoft Terminology Collection，依 Microsoft Language Portal Materials License 使用」）；不得暗示微軟背書。
3. vscode-loc（MIT）zh-hant 語言包：解析 package.nls.json / i18n JSON，以「英文字串→zh-TW 字串」萃取高頻 UI 術語（約數百-千條）；MIT 可直接嵌入，LICENSE 標示來源即可。
4. 預期效果：「通用技術」類由數十條擴至數千條；微軟與 VS Code 用語在台灣科技文獻慣用度高。

### 路徑 3（法／金領域深化＋簡中源轉換層）
1. 法律：自 glossary.doj.gov.hk 下載英中 XML/CSV（60K 條）→ 建「香港→台灣用語映射表」（申索→請求/索賠、按金→保證金、檢控→起訴 等約百餘條映射）後匯入；合規需於產品內載明律政司授權聲明（依其 Mass/Product Reproduction 條款：政府擁有版權、依許可複製、不擔保準確性、不暗示政府認可）。
2. 金融：爬取金管會雙語詞彙網頁（第1版授權）→ 匯入金融類；量小但用語權威。
3. 轉換層：整合 OpenCC（MIT）——凡未來採用 zh-CN 詞源（如 CC-CEDICT、Wiktionary 簡中條目）一律先過 s2twp 再人工抽檢，立即獲得台灣用語（打印→列印、鼠標→滑鼠 等）。
4. 預期效果：法金領域詞表從數十條擴至數千-數萬條；法律部分須保留映射表維護成本。

---

## 授權風險清單（每條附證據）

1. **immersive-translate/terms（紅線）**：無 LICENSE，保留所有權利；不得複製/子集/執行期快取（https://github.com/immersive-translate/terms ，詳前報告）。
2. **中研院 CWN 2.0（紅線）**：僅學術研究、不得商業、未同意不得轉載（https://lopentu.github.io/CwnWeb/ ）。
3. **UNTERM**：© 聯合國 2000–，無批量匯出授權管道 → 需向聯合國申請，不可逕自爬取嵌入。
4. **WIPO Pearl**：全庫授權未明（僅 COVID-19 詞集免費明示）；API 需申請 → 嵌入前須先取得書面使用條件。
5. **Apple 術語表**：ToS 不許複製散布詞表（https://developer.apple.com/forums/thread/662152 ）。
6. **dict.cc**：2005 年後為專有授權（https://en.wikipedia.org/wiki/Dict.cc ）。
7. **UMLS**：免費但需簽署授權協議、散布受限；**SNOMED CT** 付費會員制 → 皆不可嵌入。
8. **LCTT Dict.md**：無授權聲明＋簡中（https://github.com/LCTT/TranslateProject/blob/master/Dict.md ）。
9. **python-docs-zh-tw**：GitHub license = Other/NOASSERTION；Python 文件為 CC BY-NC-SA（非商業限制）→ 只作用語參考，不嵌資料。
10. **CC BY-SA/GFDL 來源（Wiktionary、Kaikki、CC-CEDICT）**：派生詞表須以同授權發布——若 Paper_Kit 詞庫檔以寬鬆授權（MIT 等）對外散布，嵌入 SA 資料將產生授權相容衝突；採「資料檔分離＋逐檔標示 CC BY-SA」或僅內部參考。
11. **MPL-2.0 本地化檔（Mozilla/LibreOffice）**：檔級 copyleft；萃取條目成新檔時須保留 MPL 標示與來源說明，或僅作比對參考不嵌入。
12. **香港律政司**：許可條款含彌償義務、違約自動終止、大量複製監控（政府可無預警終止）、產品內強制聲明 → 嵌入前須完成合規文案，且對「台灣化映射」衍生的準確性風險自負。
13. **微軟術語庫**：非 OSI 開放授權；允許用途文字（整合進術語集合／基礎 IT 詞庫）涵蓋本案，但建議留存條款原文＋NOTICE 標示；不得宣稱微軟認可。
14. **政府資料開放授權條款-第1版（樂詞網/金管會/data.gov.tw）**：可再授權、不可撤回、商業可用；義務僅「顯名聲明（註明出處）」；授權不及專利商標與個人資料 → 最低風險來源。
15. **GitHub ToS 與授權之別**：repo 可 fork（ToS §D.5）不構成再授權；凡無 LICENSE 檔一律視為保留所有權利（https://docs.github.com/en/site-policy/github-terms/github-terms-of-service ）。

---

## 來源 URL 清單

**A 組（GitHub/開源）**
- immersive-translate/terms（排除）：https://github.com/immersive-translate/terms
- g0v/moedict-data-terms（MIT）：https://github.com/g0v/moedict-data-terms 、metadata：https://api.github.com/repos/g0v/moedict-data-terms
- openl-translate/ai-dictionary（MIT）：https://github.com/openl-translate/ai-dictionary
- python-docs-zh-tw（license=Other）：https://github.com/python/python-docs-zh-tw 、https://api.github.com/repos/asdfghjkl123620/python-docs-zh-tw
- LCTT Dict.md（排除）：https://github.com/LCTT/TranslateProject/blob/master/Dict.md
- vscode-loc（MIT）：https://github.com/microsoft/vscode-loc 、LICENSE：https://github.com/microsoft/vscode-loc/blob/main/LICENSE.md
- Mozilla zh-TW（MPL-2.0）：https://hg.mozilla.org/l10n-central/zh-TW/
- LibreOffice zh_TW（MPL-2.0）：https://translations.documentfoundation.org/projects/website/newdesign/zh_Hant/
- Chromium zh-TW（BSD 檔頭例）：https://codereview.chromium.org/2280143002/
- OpenCC（MIT）：https://github.com/BYVoid/OpenCC 、詞庫更新：https://raw.githubusercontent.com/BYVoid/OpenCC/master/NEWS.md

**B 組（政府/官方）**
- 樂詞網授權宣告：https://terms.naer.edu.tw/mysite/about/2/ ；下載專區：https://terms.naer.edu.tw/download/ ；中小學雙語彙編：https://terms.naer.edu.tw/download/467/ 、https://terms.naer.edu.tw/publish/1/637/
- 樂詞網規模敘述：https://open2.idataiwan.com/info/691292 ；NAER data.gov.tw 資料集例：https://open2.idataiwan.com/info/663358 、https://scidm.nchc.org.tw/dataset/insight_classification_dataset_5_3
- 政府資料開放授權條款-第1版條文例：https://data.nantou.gov.tw/pl/specification 、https://data.taipei/rule/
- 金管會雙語詞彙：https://www.fsc.gov.tw/ch/home.jsp?id=178&parentpath=0,6 ；金管會開放宣告：https://www.fsc.gov.tw/ch/main.jsp?websitelink=artsublink.jsp&dataserno=201604250004
- 國健署雙語詞彙：https://210.241.78.32/Pages/Bilingual.aspx?nodeid=4411
- 中央機關一般職稱雙語詞彙：https://scidm.nchc.org.tw/en/dataset/best_wish6320
- 律政司詞彙網站：https://www.glossary.doj.gov.hk/ ；啟用新聞稿：https://www.info.gov.hk/gia/general/202112/30/P2021123000239.htm
- 國發會雙語資料庫學習資源網背景：https://www.scy.moj.gov.tw/258950/259045/259046/699467/post

**C 組（大廠）**
- MS Language Portal：https://www.microsoft.com/en-us/language/terminology （存檔：https://web.archive.org/web/20190328164030/https://www.microsoft.com/en-us/language/terminology ）；HF 鏡像與授權描述：https://huggingface.co/datasets/microsoft/ms_terms
- Apple Localization Resources：https://developer.apple.com/localization/resources/ ；ToS 討論：https://developer.apple.com/forums/thread/662152

**D 組（開放詞典/知識庫）**
- Kaikki.org（授權同維基詞典）：https://kaikki.org/ 、中文 dump：https://kaikki.org/zhwiktionary/alphabetical.html
- Wiktionary 授權（CC BY-SA 4.0＋GFDL）：https://en.wiktionary.org/wiki/Wiktionary:Copyrights
- CC-CEDICT（CC BY-SA 3.0）：https://cc-cedict.org/wiki/start 、規模（Wikipedia）：https://en.wikipedia.org/wiki/CC-CEDICT
- globalwordnet 資源表（中文詞網授權）：https://globalwordnet.github.io/resources/wordnets-in-the-world ；Princeton WordNet 授權：https://wordnet.princeton.edu/license-and-commercial-use
- 中研院 CWN：https://lopentu.github.io/CwnWeb/ 、同類授權宣告：https://tmc.ling.sinica.edu.tw/copyright_ch/
- dict.cc 授權史（Wikipedia）：https://en.wikipedia.org/wiki/Dict.cc

**E 組（專業領域）**
- NCBI-PD（NLM 公有領域聲明）：https://spdx.org/licenses/NCBI-PD.html
- WIPO Pearl 新聞（COVID-19 免費下載）：https://etradeforall.org/es/node/9283 ；API 上線：https://www.wipo.int/zh/web/wipo-pearl/w/news/2021/news_0004
- IMF 英漢詞彙手冊館藏：https://catalog.lib.uchicago.edu/vufind/Record/12496973

**基礎原則**
- GitHub ToS（fork 不等於再授權）：https://docs.github.com/en/site-policy/github-terms/github-terms-of-service
