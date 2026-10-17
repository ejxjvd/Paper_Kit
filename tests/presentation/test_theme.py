"""票 11：主題系統（CSS 變數集中管理＋深色模式控制器）契約測試。

theme.py 是 presentation 層純模組（可 import、字串可斷言）；widget 綁定在
app.py 不可測，主題的「可維護性契約」在這裡鎖住：變數單一來源、深色覆寫、
卡片美化 class 存在。
"""

from paper_kit.presentation.theme import THEME_CSS, apply_theme


def test_theme_css_defines_central_variable_tokens():
    """CSS 變數集中管理：元件顏色一律 var(--pk-*)，不寫死色值。"""
    for token in ("--pk-color-bg", "--pk-color-surface", "--pk-color-border",
                  "--pk-color-text", "--pk-color-text-muted",
                  "--pk-color-error", "--pk-color-progress"):
        assert token in THEME_CSS


def test_theme_css_covers_dark_mode_via_quasar_class():
    """深色模式：NiceGUI/Quasar 的 body--dark class 重新定義全部變數（不殘留淺色）。"""
    assert "body--dark" in THEME_CSS
    dark_section = THEME_CSS.split("body--dark", 1)[1]
    for token in ("--pk-color-bg", "--pk-color-surface", "--pk-color-text",
                  "--pk-color-text-muted", "--pk-color-error", "--pk-color-progress"):
        assert token in dark_section


def test_theme_css_body_uses_variables():
    assert "var(--pk-color-bg)" in THEME_CSS
    assert "var(--pk-color-text)" in THEME_CSS


def test_theme_css_has_card_beautification_classes():
    """任務卡片美化：圓角/陰影/背景（.pk-card）、meta/成本/錯誤語意色 class。"""
    for cls in (".pk-card", ".pk-meta", ".pk-cost", ".pk-error", ".pk-progress"):
        assert cls in THEME_CSS
    assert "border-radius" in THEME_CSS
    assert "box-shadow" in THEME_CSS


def test_theme_css_defines_engine_card_rules():
    """引擎卡：同列等高，但**不截斷文字**（2026-10-16 D4 契約改寫）。

    契約變更記錄（§13② 護欄改裝）：
      舊契約：`.pk-engine-card { height: 104px }` ＋ desc `max-height: 2.4em;
              overflow: hidden`——把卡高鎖死、超出的字切掉。
              源由：使用者兩次回報「3 個按鍵大小不統一」，第 1 修用 min-height
              無效（內容仍會撐高），第 2 修改固定高度止血。
      新契約：不限高，改由 `ui.row(...items-stretch)` 讓同列卡片 flex stretch
              等高；desc 不封頂。三列皆已補 `items-stretch`。
      為什麼：固定高度的「等高」是假的——它靠切掉文字達成（siliconflow 描述
              較長，窄視窗下先犧牲）。失敗模式比較：卡片變高＝視覺節奏問題，
              文字被截斷＝資訊損失。且 `.pk-engine-card` 已是 flex column，
              硬鎖本來就沒必要。
      紅線不變：邊框與圓角仍須用主題 token。
    """
    assert ".pk-engine-card" in THEME_CSS
    card_section = THEME_CSS.split(".pk-engine-card", 1)[1]
    assert "height: 104px" not in card_section, (
        "固定高度＝靠截斷文字達成假等高；等高改由 row 的 items-stretch 負責"
    )
    assert "var(--pk-color-border)" in card_section, "邊框用主題 token"
    assert "var(--pk-radius-md)" in card_section, "圓角用主題 token"


def test_theme_css_engine_desc_not_truncated():
    """desc 不封頂、不截斷（D4 契約改寫）。

      舊契約：`min-height/max-height: 2.4em` ＋ `overflow: hidden`——3 行以上切掉。
      新契約：無 max-height、無 overflow: hidden——文字完整顯示，長的卡變高。
      為什麼：截斷是資訊損失，不是排版選擇；行銷文案已移到 ⓘ tooltip，
      desc 本身短，讓它自然流動即可。
    """
    assert ".pk-engine-desc" in THEME_CSS
    desc_section = THEME_CSS.split(".pk-engine-desc", 1)[1].split("}")[0]
    assert "max-height" not in desc_section, "desc 不得封頂截斷"
    assert "overflow: hidden" not in desc_section, "desc 不得裁切文字"


def test_theme_css_defines_disabled_engine_card():
    """機密模式禁用視覺卡（灰化＋不可點擊游標）——class 由主題 CSS 提供。"""
    assert ".pk-engine-card--disabled" in THEME_CSS
    assert "opacity" in THEME_CSS.split(".pk-engine-card--disabled", 1)[1]
    assert "not-allowed" in THEME_CSS.split(".pk-engine-card--disabled", 1)[1]


def test_apply_theme_returns_dark_mode_controller():
    """主題切換不重載：回傳 NiceGUI DarkMode 控制器（enable/disable/toggle 即時生效）。"""
    dark = apply_theme()
    for method in ("enable", "disable", "toggle"):
        assert callable(getattr(dark, method, None))


def test_all_engine_rows_use_items_stretch(tmp_path):
    """不變式（2026-10-16 D4）：三個引擎卡區的 ui.row 都必須帶 items-stretch。

    歷史：付費與免費 LLM 兩列有、**免費翻譯那列沒有**——這正是使用者最早回報
    「3 個按鍵大小不統一」的來源之一。現已補上；本測試防它再次漏掉。

    做法：直接掃 app.py 原始碼（引擎卡的 row class 字串是唯一真相），
    比逐一渲染三列便宜且不會因 UI 改版而漏檢。
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2]
           / "src" / "paper_kit" / "presentation" / "index_page.py").read_text(encoding="utf-8")
    # 三區的 row：付費／免費翻譯／免費 LLM（本機代理區亦同款）
    rows = [ln for ln in src.splitlines() if 'ui.row().classes("pk-gap-2 w-full' in ln]
    assert len(rows) >= 3, f"引擎卡列數異常（預期≥3）：{len(rows)}"
    for ln in rows:
        assert "items-stretch" in ln, (
            f"引擎卡列缺 items-stretch（卡片將不等高）：{ln.strip()}"
        )
