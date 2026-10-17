"""票 11／T-07 相位 5：設計系統——六族 token 的單一來源。

設計（2026-10-17 相位 5 重寫）：
- 所有視覺數值集中在本檔，分六族：**色彩／字級／間距／圓角／陰影／動效**。
  元件只准使用 `var(--pk-*)` 或本檔提供的語意 class，不得寫死色值。
- 並存紀律：Quasar 保留版面 utility（flex／間距），**禁用顏色與字級 utility**
  （例如固定灰階文字色、寫死字級）。理由：顏色 utility 繞過 token，深色切換
  必然漏改；這條紀律由 `tests/presentation/test_design_tokens.py` 機械守門。
- 深色模式走 NiceGUI/Quasar 慣例：body 加 `body--dark`，該區塊**逐一覆寫
  每一個色彩 token**（漏一個就是淺色字壓深色底——測試會紅）。
- `prefers-reduced-motion` 把動效時長歸零。
"""

import nicegui.ui as ui

# ── 色彩（淺色；深色必須逐項覆寫）────────────────────────────────────
LIGHT_COLORS = {
    "--pk-color-bg": "#f4f6f9",
    "--pk-color-surface": "#ffffff",
    "--pk-color-border": "#e2e6ec",
    "--pk-color-text": "#1f2937",
    "--pk-color-text-muted": "#55606e",
    "--pk-color-primary": "#1d4ed8",
    "--pk-color-on-primary": "#ffffff",
    "--pk-color-success": "#15803d",
    "--pk-color-warning": "#b45309",
    "--pk-color-error": "#b91c1c",
    "--pk-color-progress": "#2563eb",
    "--pk-color-sidebar-bg": "#e9edf3",
    "--pk-color-nav-active-bg": "#1d4ed8",
    "--pk-color-nav-active-text": "#ffffff",
    "--pk-color-nav-hover-bg": "#dde3ec",
}

DARK_COLORS = {
    "--pk-color-bg": "#0f1217",
    "--pk-color-surface": "#1a1f27",
    "--pk-color-border": "#2b3140",
    "--pk-color-text": "#e6eaf1",
    "--pk-color-text-muted": "#a6b0c0",
    "--pk-color-primary": "#7aa7ff",
    "--pk-color-on-primary": "#0b1020",
    "--pk-color-success": "#6ee7a8",
    "--pk-color-warning": "#fbbf24",
    "--pk-color-error": "#f87171",
    "--pk-color-progress": "#7aa7ff",
    "--pk-color-sidebar-bg": "#151a21",
    "--pk-color-nav-active-bg": "#2b4c9c",
    "--pk-color-nav-active-text": "#ffffff",
    "--pk-color-nav-hover-bg": "#222937",
}

TYPOGRAPHY = {
    "--pk-font-family": 'system-ui, -apple-system, "Segoe UI", "Noto Sans TC", sans-serif',
    "--pk-font-mono": "ui-monospace, SFMono-Regular, Consolas, monospace",
    "--pk-font-size-xs": "0.75rem",
    "--pk-font-size-sm": "0.875rem",
    "--pk-font-size-md": "1rem",
    "--pk-font-size-lg": "1.125rem",
    "--pk-font-size-xl": "1.375rem",
    "--pk-font-size-2xl": "1.75rem",
    "--pk-font-weight-regular": "400",
    "--pk-font-weight-medium": "500",
    "--pk-font-weight-bold": "700",
    "--pk-line-height-tight": "1.2",
    "--pk-line-height-normal": "1.55",
}

SPACING = {
    "--pk-space-1": "4px",
    "--pk-space-2": "8px",
    "--pk-space-3": "12px",
    "--pk-space-4": "16px",
    "--pk-space-5": "24px",
    "--pk-space-6": "32px",
}

RADIUS = {
    "--pk-radius-sm": "6px",
    "--pk-radius-md": "12px",
    "--pk-radius-lg": "18px",
    "--pk-radius-full": "9999px",
}

SHADOW = {
    "--pk-shadow-sm": "0 1px 3px rgba(0, 0, 0, 0.08)",
    "--pk-shadow-md": "0 4px 12px rgba(0, 0, 0, 0.10)",
    "--pk-shadow-lg": "0 12px 28px rgba(0, 0, 0, 0.16)",
}

MOTION = {
    "--pk-motion-fast": "120ms",
    "--pk-motion-base": "200ms",
    "--pk-motion-slow": "320ms",
    "--pk-ease-standard": "cubic-bezier(0.2, 0.7, 0.3, 1)",
    "--pk-ease-emphasized": "cubic-bezier(0.2, 0.9, 0.1, 1)",
}


def _declarations(tokens: dict[str, str]) -> str:
    return "\n".join(f"  {name}: {value};" for name, value in tokens.items())


_ROOT_TOKENS = {
    **LIGHT_COLORS,
    **TYPOGRAPHY,
    **SPACING,
    **RADIUS,
    **SHADOW,
    **MOTION,
}

THEME_CSS = f"""
:root {{
{_declarations(_ROOT_TOKENS)}
}}
body.body--dark {{
{_declarations(DARK_COLORS)}
}}
body {{
  background: var(--pk-color-bg);
  color: var(--pk-color-text);
  font-family: var(--pk-font-family);
  line-height: var(--pk-line-height-normal);
}}
.pk-card {{
  background: var(--pk-color-surface);
  border: 1px solid var(--pk-color-border);
  border-radius: var(--pk-radius-md);
  box-shadow: var(--pk-shadow-sm);
  transition: box-shadow var(--pk-motion-base) var(--pk-ease-standard);
}}
.pk-card:hover {{
  box-shadow: var(--pk-shadow-md);
}}
.pk-meta, .pk-cost {{ color: var(--pk-color-text-muted); }}
.pk-muted {{ color: var(--pk-color-text-muted); }}
.pk-text {{ color: var(--pk-color-text); }}
.pk-error {{ color: var(--pk-color-error); }}
.pk-success {{ color: var(--pk-color-success); }}
.pk-warning {{ color: var(--pk-color-warning); }}
.pk-progress {{ color: var(--pk-color-progress); }}
.pk-link {{ color: var(--pk-color-primary); text-decoration: underline; text-underline-offset: 2px; }}
.pk-text-xs {{ font-size: var(--pk-font-size-xs); }}
.pk-text-sm {{ font-size: var(--pk-font-size-sm); }}
.pk-text-lg {{ font-size: var(--pk-font-size-lg); }}
.pk-text-xl {{ font-size: var(--pk-font-size-xl); }}
.pk-text-2xl {{ font-size: var(--pk-font-size-2xl); }}
.pk-sidebar {{ background: var(--pk-color-sidebar-bg) !important; }}
.pk-nav-link {{ border-radius: var(--pk-radius-sm); transition: background var(--pk-motion-fast) var(--pk-ease-standard); }}
.pk-nav-link:hover {{ background: var(--pk-color-nav-hover-bg); }}
.pk-nav-active {{
  background: var(--pk-color-nav-active-bg) !important;
  color: var(--pk-color-nav-active-text) !important;
}}
/* 引擎卡等高（2026-10-16 D4 重做，取代 2026-08-13 的固定高度補丁）。

   病史：使用者兩次回報「3 個按鍵大小不統一」。第 1 修（9edfe9f）用 min-height
   保底——只設下界、內容仍會撐高，依然不等高。第 2 修改**固定 height 104px**
   ＋desc 兩行封頂，卡高確實不變了——但代價是**把字切掉**：siliconflow 描述
   較長，窄視窗下先犧牲，三卡之所以「看起來等高」是因為裡面的文字被裁了。

   現行做法：不限高，交給三列 `ui.row(...items-stretch)` 的 flex stretch——
   同列卡片自動等高，且文字完整。失敗模式比較：卡片變高＝視覺節奏問題，
   文字被截斷＝資訊損失。

   紅線不變：所有色值走 var(--pk-*) token，不得寫死。 */
.pk-engine-card {{
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-sizing: border-box;
  border: 1px solid var(--pk-color-border);
  border-radius: var(--pk-radius-md);
  background: var(--pk-color-surface);
}}
.pk-engine-card--disabled {{
  opacity: 0.45;
  cursor: not-allowed;
}}
/* desc 不封頂、不截斷——長的卡自然變高，同列其餘卡 stretch 跟上。 */
.pk-engine-card .pk-engine-desc {{
  line-height: var(--pk-line-height-tight);
}}
.pk-empty-state {{
  padding: var(--pk-space-5);
  border: 1px dashed var(--pk-color-border);
  border-radius: var(--pk-radius-md);
  color: var(--pk-color-text-muted);
}}
.pk-empty-icon {{ color: var(--pk-color-text-muted); font-size: var(--pk-font-size-2xl); }}
.pk-skeleton-row {{ align-items: center; }}
.pk-skeleton {{
  height: var(--pk-font-size-sm);
  background: var(--pk-color-border);
  border-radius: var(--pk-radius-sm);
  animation: pk-pulse var(--pk-motion-slow) var(--pk-ease-standard) infinite alternate;
}}
.pk-skeleton-title {{ width: 38%; }}
.pk-skeleton-meta {{ width: 22%; }}
@keyframes pk-pulse {{ from {{ opacity: 0.35; }} to {{ opacity: 0.7; }} }}
.pk-inline-error {{
  border-left: 3px solid var(--pk-color-error);
  background: var(--pk-color-surface);
  padding: var(--pk-space-2) var(--pk-space-3);
  border-radius: var(--pk-radius-sm);
}}
.pk-gap-0 {{ gap: 0; }}
.pk-gap-1 {{ gap: var(--pk-space-1); }}
.pk-gap-2 {{ gap: var(--pk-space-2); }}
.pk-gap-3 {{ gap: var(--pk-space-3); }}
.pk-gap-4 {{ gap: var(--pk-space-4); }}
.pk-container-wide {{ width: 100%; }}
.pk-container-form {{ width: 100%; max-width: 56rem; margin-inline: auto; }}
.pk-container-narrow {{ width: 100%; max-width: 42rem; margin-inline: auto; }}
.q-linear-progress__bar {{
  transition: transform var(--pk-motion-base) var(--pk-ease-standard) !important;
}}
@media (prefers-reduced-motion: reduce) {{
  :root {{
    --pk-motion-fast: 0ms;
    --pk-motion-base: 0ms;
    --pk-motion-slow: 0ms;
  }}
  *, *::before, *::after {{
    animation-duration: 1ms !important;
    transition-duration: 1ms !important;
  }}
}}
"""


def _hex(token: str) -> str:
    return LIGHT_COLORS[token]


def apply_theme() -> ui.dark_mode:
    """注入主題 CSS，回傳深色模式控制器（切換即時生效、不重載）。

    同時把 Quasar 的語意色對齊 token——`props("color=primary")` 的按鈕才會
    跟主題一致，而不是 Quasar 預設藍。
    """
    ui.add_css(THEME_CSS)
    ui.colors(
        primary=_hex("--pk-color-primary"),
        positive=_hex("--pk-color-success"),
        warning=_hex("--pk-color-warning"),
        negative=_hex("--pk-color-error"),
    )
    return ui.dark_mode()
