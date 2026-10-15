"""票 11：主題系統——CSS 變數集中管理＋深色模式控制器。

設計：
- THEME_CSS 是全部視覺 token 的單一來源；元件 classes 一律用 var(--pk-*)
  （.pk-card／.pk-meta／.pk-cost），新增樣式不得寫死色值
- 深色模式走 NiceGUI/Quasar 慣例：body 加 body--dark class，該選擇器內
  重新定義全部變數（不殘留淺色）
- apply_theme() 回傳 ui.dark_mode() 控制器——enable/disable/toggle 即時
  切換 body class，主題切換不重載（規格 AC1）
"""

import nicegui.ui as ui

THEME_CSS = """
:root {
  --pk-bg: #f4f6f9;
  --pk-card-bg: #ffffff;
  --pk-border: #e2e6ec;
  --pk-text: #1f2937;
  --pk-text-muted: #6b7280;
  --pk-error: #dc2626;
  --pk-progress: #3b82f6;
  --pk-radius: 12px;
  --pk-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
}
body.body--dark {
  --pk-bg: #101318;
  --pk-card-bg: #1b1f28;
  --pk-border: #2b3140;
  --pk-text: #e7eaf0;
  --pk-text-muted: #9aa3b2;
  --pk-error: #f87171;
  --pk-progress: #60a5fa;
  --pk-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
}
body { background: var(--pk-bg); color: var(--pk-text); }
.pk-card {
  background: var(--pk-card-bg);
  border: 1px solid var(--pk-border);
  border-radius: var(--pk-radius);
  box-shadow: var(--pk-shadow);
}
.pk-meta, .pk-cost { color: var(--pk-text-muted); }
.pk-error { color: var(--pk-error); }
.pk-progress { color: var(--pk-progress); }
/* 引擎卡等高（2026-10-16 D4 重做，取代 2026-08-13 的固定高度補丁）。

   病史：使用者兩次回報「3 個按鍵大小不統一」。第 1 修（9edfe9f）用 min-height
   保底——只設下界、內容仍會撐高，依然不等高。第 2 修改**固定 height 104px**
   ＋desc 兩行封頂，卡高確實不變了——但代價是**把字切掉**：siliconflow 描述
   較長，窄視窗下先犧牲，三卡之所以「看起來等高」是因為裡面的文字被裁了。

   現行做法：不限高，交給三列 `ui.row(...items-stretch)` 的 flex stretch——
   同列卡片自動等高，且文字完整。失敗模式比較：卡片變高＝視覺節奏問題，
   文字被截斷＝資訊損失。

   紅線不變：所有色值走 var(--pk-*) token，不得寫死。 */
.pk-engine-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-sizing: border-box;
  border: 1px solid var(--pk-border);
  border-radius: var(--pk-radius);
  background: var(--pk-card-bg);
}
.pk-engine-card--disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
/* desc 不封頂、不截斷——長的卡自然變高，同列其餘卡 stretch 跟上。 */
.pk-engine-card .pk-engine-desc {
  line-height: 1.2em;
}
"""


def apply_theme() -> ui.dark_mode:
    """注入主題 CSS，回傳深色模式控制器（切換即時生效、不重載）。"""
    ui.add_css(THEME_CSS)
    return ui.dark_mode()
