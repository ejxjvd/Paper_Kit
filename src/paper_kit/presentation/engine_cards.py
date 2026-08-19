"""引擎卡片：主頁三個入口各自顯示哪些引擎、以什麼順序（架構深化候選 3，2026-08-19）。

**為什麼在 presentation**：這是純粹的呈現決定——哪張卡排前面、哪些引擎放進
「免費翻譯」區。它先前住在 `infrastructure/engine_registry`，於是 presentation
反過來 import infrastructure 才拿得到排序（seam 洩漏；app.py 對 infrastructure
的 import 曾多達 9 次，和它 import application 的次數一樣多）。

引擎的**身分與能力**（id／provider／model／needs_key／sensitive_ok／定價）仍留在
registry——那是基礎設施事實。這裡只回答「怎麼呈現給使用者」。

加引擎時：先在 registry 登記 spec，再決定要不要出現在下面某個入口。
`tests/infrastructure/test_engine_registry.py` 有不變式測試把關兩邊不脫節
（例如新的 keyless 引擎必須登記於免費翻譯入口）。
"""

UI_ENGINE_IDS: tuple[str, ...] = (
    "siliconflow", "deepseek", "babeldoc", "latex", "openai", "gemini-pro",
)

# 免費翻譯入口（2026-08-13）：主頁「免費翻譯（不需 API key）」區的卡集合與順序——
# 三支 needs_key=False 引擎（不變式測試把關：未來 keyless 引擎必須登記於此）。
# siliconflowfree 排首（上游預設、活躍）；google/bing 上游已棄用。app.py 只迭代此 tuple。
UI_FREE_ENGINE_IDS: tuple[str, ...] = ("siliconflowfree", "google", "bing")

# 免費 LLM key 引擎（2026-08-13，Free-LLM-Collection 查證後加入）：主頁「免費 LLM
# （自備免費 key）」區的卡集合與順序＝品質優先序（docs/research/2026-08-13-
# Free-LLM-Collection-查證與品質優先序.md §3）——NVIDIA NIM 居首（T1/T2 品質＋
# 40RPM＋無日總量）、Gemini 殿後（免費層資料訓練紅線，非敏感才可用）。
# 全走 provider=openai（pdf2zh --openai 三旗標）、BYOK（自申請免費 key 填入）。
# app.py 只迭代此 tuple——加引擎單點。
# v0.1.7（2026-08-14）：Z.AI 查證後回補（#78 補完）——智譜國際站
# api.z.ai 實測：glm-4.7-flash（思考）/glm-4.5-flash（非思考）小寫 ID 免費可生成，
# 真翻譯產出存在。zai 排第 2（GLM 中文品質 T1/T2，僅次 NVIDIA）。
UI_FREE_KEY_ENGINE_IDS: tuple[str, ...] = (
    "nvidia", "zai", "modelscope", "groq", "openrouter", "dashscope", "gemini",
)
