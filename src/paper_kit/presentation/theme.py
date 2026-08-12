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
"""


def apply_theme() -> ui.dark_mode:
    """注入主題 CSS，回傳深色模式控制器（切換即時生效、不重載）。"""
    ui.add_css(THEME_CSS)
    return ui.dark_mode()
