"""票 11：主題系統（CSS 變數集中管理＋深色模式控制器）契約測試。

theme.py 是 presentation 層純模組（可 import、字串可斷言）；widget 綁定在
app.py 不可測，主題的「可維護性契約」在這裡鎖住：變數單一來源、深色覆寫、
卡片美化 class 存在。
"""

from paper_kit.presentation.theme import THEME_CSS, apply_theme


def test_theme_css_defines_central_variable_tokens():
    """CSS 變數集中管理：元件顏色一律 var(--pk-*)，不寫死色值。"""
    for token in ("--pk-bg", "--pk-card-bg", "--pk-border", "--pk-text", "--pk-text-muted",
                  "--pk-error", "--pk-progress"):
        assert token in THEME_CSS


def test_theme_css_covers_dark_mode_via_quasar_class():
    """深色模式：NiceGUI/Quasar 的 body--dark class 重新定義全部變數（不殘留淺色）。"""
    assert "body--dark" in THEME_CSS
    dark_section = THEME_CSS.split("body--dark", 1)[1]
    for token in ("--pk-bg", "--pk-card-bg", "--pk-text", "--pk-text-muted",
                  "--pk-error", "--pk-progress"):
        assert token in dark_section


def test_theme_css_body_uses_variables():
    assert "var(--pk-bg)" in THEME_CSS
    assert "var(--pk-text)" in THEME_CSS


def test_theme_css_has_card_beautification_classes():
    """任務卡片美化：圓角/陰影/背景（.pk-card）、meta/成本/錯誤語意色 class。"""
    for cls in (".pk-card", ".pk-meta", ".pk-cost", ".pk-error", ".pk-progress"):
        assert cls in THEME_CSS
    assert "border-radius" in THEME_CSS
    assert "box-shadow" in THEME_CSS


def test_apply_theme_returns_dark_mode_controller():
    """主題切換不重載：回傳 NiceGUI DarkMode 控制器（enable/disable/toggle 即時生效）。"""
    dark = apply_theme()
    for method in ("enable", "disable", "toggle"):
        assert callable(getattr(dark, method, None))
