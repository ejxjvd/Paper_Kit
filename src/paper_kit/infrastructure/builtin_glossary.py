"""內建術語表（#84 方案 A：格式參考 immersive-terms，詞條全自研／樂詞網）。

兩份內建詞表（seed 皆冪等，見 glossary_service）：

1. `paper-kit-basic`（265 條，自研彙編）
   授權紅線（2026-08-14 research 實地查證，見
   docs/research/2026-08-14-Paper_Kit-研究-immersive-terms術語庫-查證.md）：
   immersive-translate/terms **無 LICENSE**＝法律「保留所有權利」——不得直接
   複製/嵌入/執行期快取其詞條。本詞表詞條一律自研彙編（以使用者提供之
   「12 大 AI 術語庫核心映射」參考清單為原料逐條驗證繁中化＋Paper_Kit
   論文翻譯慣用語補充），CSV 三欄格式（source,target,tgt_lng）與其相容——
   日後上游補授權（MIT/CC-BY）可直吃通用領域子集（≈400 條），格式互轉零成本。

2. `naer-core`（29,560 條，樂詞網學術名詞單詞層——術語庫擴充 2026-08-14）
   來源：國家教育研究院 樂詞網（terms.naer.edu.tw）下載專區——電子計算機／
   電機工程／食品科技／魚類 4 領域全量（音樂 6 包與論文翻譯無關不入選）。
   **授權：政府資料開放授權條款-第1版**（可再授權、商業可用、僅需顯名聲明——
   本 docstring 與 scripts/naer_build.py 檔頭即為顯名聲明）。生成可重現：
   `uv run python scripts/naer_build.py`（下載 ODS → 過濾 → gzip 資源檔）。
   資料契約（tests/infrastructure/test_builtin_glossary.py 鎖定）：source
   小寫字母開頭、單詞、無括號註記；target 無簡體字形污染；tgt_lng 全 zh-TW。
"""

BUILTIN_GLOSSARY_NAME = "paper-kit-basic"

# naer-core：樂詞網 gzip 資源檔（package data 目錄，importlib.resources 讀取）
NAER_GLOSSARY_NAME = "naer-core"
NAER_GLOSSARY_GZ = "naer_core.csv.gz"

BUILTIN_GLOSSARY_CSV = """source,target,tgt_lng
Transformer,Transformer 模型,zh-TW
Fine-tuning,模型微調,zh-TW
Inference,推理,zh-TW
Embedding,向量嵌入,zh-TW
Token,Token,zh-TW
Prompt,提示詞,zh-TW
Alignment,AI 對齊,zh-TW
Attention,注意力機制,zh-TW
Gradient Descent,梯度下降,zh-TW
Overfitting,過擬合,zh-TW
Weights,權重,zh-TW
Bias,偏差,zh-TW
Epoch,訓練輪數,zh-TW
Hallucination,幻覺,zh-TW
Ground Truth,真實標籤,zh-TW
Machine Learning,機器學習,zh-TW
Neural Network,神經網路,zh-TW
Deep Learning,深度學習,zh-TW
Language Model,語言模型,zh-TW
Large Language Model,大型語言模型,zh-TW
LLM,LLM,zh-TW
Baseline,基準線,zh-TW
Benchmark,基準測試,zh-TW
Ablation,消融實驗,zh-TW
Regularization,正則化,zh-TW
Backpropagation,反向傳播,zh-TW
Activation Function,激活函數,zh-TW
Loss Function,損失函數,zh-TW
Optimizer,最佳化器,zh-TW
Learning Rate,學習率,zh-TW
Batch Size,批次大小,zh-TW
Dataset,資料集,zh-TW
Feature,特徵,zh-TW
Label,標籤,zh-TW
Prediction,預測,zh-TW
Training Data,訓練資料,zh-TW
Test Data,測試資料,zh-TW
Validation Data,驗證資料,zh-TW
Model,模型,zh-TW
Parameters,參數,zh-TW
Gradient,梯度,zh-TW
Latent,潛在,zh-TW
Temperature,溫度,zh-TW
Sampling,取樣,zh-TW
Beam Search,波束搜尋,zh-TW
Tokenizer,分詞器,zh-TW
Semantic,語意,zh-TW
Syntactic,語法,zh-TW
Context,上下文,zh-TW
Retrieval,檢索,zh-TW
Embedding Space,嵌入空間,zh-TW
Transfer Learning,遷移學習,zh-TW
Multi-task Learning,多任務學習,zh-TW
Reinforcement Learning,強化學習,zh-TW
Supervised Learning,監督式學習,zh-TW
Unsupervised Learning,非監督式學習,zh-TW
Self-supervised Learning,自監督學習,zh-TW
Generative Model,生成式模型,zh-TW
Discriminative Model,鑑別式模型,zh-TW
Encoder,編碼器,zh-TW
Decoder,解碼器,zh-TW
Attention Mechanism,注意力機制,zh-TW
Knowledge Distillation,知識蒸餾,zh-TW
Zero-shot,零樣本,zh-TW
Few-shot,少樣本,zh-TW
Fine-grained,細粒度,zh-TW
SOTA,當前最佳,zh-TW
Vector,向量,zh-TW
Matrix,矩陣,zh-TW
Tensor,張量,zh-TW
Significance,顯著性,zh-TW
Statistical Significance,統計顯著性,zh-TW
Confounder,干擾因子,zh-TW
Qualitative,質性,zh-TW
Quantitative,量化,zh-TW
Empirical,實證的,zh-TW
Peer Review,同行評審,zh-TW
Abstract,摘要,zh-TW
Correlation,相關性,zh-TW
Causation,因果關係,zh-TW
P-value,P 值,zh-TW
Confidence Interval,信賴區間,zh-TW
Standard Deviation,標準差,zh-TW
Mean,平均值,zh-TW
Median,中位數,zh-TW
Variance,變異數,zh-TW
Hypothesis,假說,zh-TW
Null Hypothesis,虛無假說,zh-TW
Effect Size,效果量,zh-TW
Statistical Power,統計檢定力,zh-TW
Sample Size,樣本數,zh-TW
Randomized,隨機化,zh-TW
Controlled Trial,對照試驗,zh-TW
Double-blind,雙盲,zh-TW
Longitudinal Study,縱貫研究,zh-TW
Cross-sectional Study,橫斷研究,zh-TW
Meta-analysis,後設分析,zh-TW
Systematic Review,系統性回顧,zh-TW
Literature Review,文獻回顧,zh-TW
Methodology,研究方法,zh-TW
Discussion,討論,zh-TW
Conclusion,結論,zh-TW
Introduction,緒論,zh-TW
Appendix,附錄,zh-TW
Bibliography,參考文獻,zh-TW
Citation,引用,zh-TW
Reference,參考文獻,zh-TW
Figure,圖,zh-TW
Table,表,zh-TW
Manuscript,稿件,zh-TW
Preprint,預印本,zh-TW
Conference Paper,會議論文,zh-TW
Journal Paper,期刊論文,zh-TW
Corresponding Author,通訊作者,zh-TW
Co-author,共同作者,zh-TW
Acknowledgements,致謝,zh-TW
Supplementary Material,補充材料,zh-TW
Thread,執行緒,zh-TW
Instance,實例,zh-TW
Socket,通訊端,zh-TW
Dump,傾印,zh-TW
Render,渲染,zh-TW
Callback,回呼,zh-TW
Deploy,部署,zh-TW
Syntax,語法,zh-TW
Array,陣列,zh-TW
String,字串,zh-TW
Exception,例外,zh-TW
Argument,引數,zh-TW
Parameter,參數,zh-TW
Compile,編譯,zh-TW
Parse,解析,zh-TW
Cookie,Cookie,zh-TW
Session,工作階段,zh-TW
Cache,快取,zh-TW
Buffer,緩衝區,zh-TW
Fork,分叉,zh-TW
Commit,提交,zh-TW
Blame,追溯,zh-TW
Firmware,韌體,zh-TW
Database,資料庫,zh-TW
Resolution,解析度,zh-TW
Operating System,作業系統,zh-TW
IP Address,IP 位址,zh-TW
Algorithm,演算法,zh-TW
Cloud Computing,雲端運算,zh-TW
API,API,zh-TW
CLI,命令列介面,zh-TW
Runtime,執行時期,zh-TW
Framework,框架,zh-TW
Module,模組,zh-TW
Dependency,相依性,zh-TW
Interface,介面,zh-TW
Network,網路,zh-TW
Server,伺服器,zh-TW
Program,程式,zh-TW
File,檔案,zh-TW
Folder,資料夾,zh-TW
Default,預設值,zh-TW
Profile,設定檔,zh-TW
Software,軟體,zh-TW
Video,影片,zh-TW
Data,資料,zh-TW
Information,資訊,zh-TW
Application,應用程式,zh-TW
Function,函式,zh-TW
Variable,變數,zh-TW
Object,物件,zh-TW
Class,類別,zh-TW
Method,方法,zh-TW
Attribute,屬性,zh-TW
Repository,儲存庫,zh-TW
Release,發行版,zh-TW
Version,版本,zh-TW
Update,更新,zh-TW
Bug,Bug,zh-TW
Debug,除錯,zh-TW
Error,錯誤,zh-TW
Warning,警告,zh-TW
Log,日誌,zh-TW
Clinical Trial,臨床試驗,zh-TW
Adverse Effect,不良反應,zh-TW
In vitro,體外,zh-TW
In vivo,體內,zh-TW
Placebo,安慰劑,zh-TW
Blinded Study,盲法試驗,zh-TW
Malignant,惡性的,zh-TW
Culture,培養,zh-TW
Screening,篩檢,zh-TW
Subject,受試者,zh-TW
Indication,適應症,zh-TW
Dosage,劑量,zh-TW
Morbidity,罹病率,zh-TW
Mortality,死亡率,zh-TW
Prevalence,盛行率,zh-TW
Incidence,發生率,zh-TW
Biopsy,切片檢查,zh-TW
Prognosis,預後,zh-TW
Diagnosis,診斷,zh-TW
Therapy,治療,zh-TW
Genome,基因體,zh-TW
Gene,基因,zh-TW
Protein,蛋白質,zh-TW
Cell Line,細胞株,zh-TW
Tissue,組織,zh-TW
Terms and Conditions,條款與條件,zh-TW
Liability,法律責任,zh-TW
Force Majeure,不可抗力,zh-TW
Indemnification,免責補償,zh-TW
Without Prejudice,不損及權益,zh-TW
Execute,簽署,zh-TW
Construction,條款解釋,zh-TW
Remedy,救濟措施,zh-TW
Provision,條款,zh-TW
Jurisdiction,管轄權,zh-TW
Arbitration,仲裁,zh-TW
Confidentiality,保密義務,zh-TW
Breach,違約,zh-TW
Warranty,保證,zh-TW
Statute,法規,zh-TW
Regulation,法規,zh-TW
Compliance,遵循,zh-TW
Party,當事人,zh-TW
Agreement,協議,zh-TW
Contract,契約,zh-TW
Clause,條款,zh-TW
Effective Date,生效日期,zh-TW
Termination,終止,zh-TW
Renewal,續約,zh-TW
Obligation,義務,zh-TW
Right,權利,zh-TW
FOB,船上交貨價,zh-TW
Bill of Lading,海運提單,zh-TW
Bear Market,空頭市場,zh-TW
Bull Market,多頭市場,zh-TW
Yield,殖利率,zh-TW
Liquidation,強制平倉,zh-TW
Hawkish,鷹派,zh-TW
Dovish,鴿派,zh-TW
Short,放空,zh-TW
Option,選擇權,zh-TW
Derivative,衍生性金融商品,zh-TW
Hedge,避險,zh-TW
Arbitrage,套利,zh-TW
Portfolio,投資組合,zh-TW
Dividend,股利,zh-TW
Equity,股權,zh-TW
Bond,債券,zh-TW
Interest Rate,利率,zh-TW
Inflation,通貨膨脹,zh-TW
GDP,國內生產毛額,zh-TW
Trade Deficit,貿易逆差,zh-TW
Exchange Rate,匯率,zh-TW
Customs,海關,zh-TW
Tariff,關稅,zh-TW
Import,進口,zh-TW
Export,出口,zh-TW
"""
