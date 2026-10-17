"""T-07 相位 5：設計系統守門（六族 token、深色全覆寫、對比度、utility 禁令）。

背景：`theme.py` 原先是 9 個鬆散變數（bg／card-bg／border／text／muted／error／
progress／radius／shadow），深色模式靠一份手抄的覆寫清單——新增 token 忘了在
深色補一行，就是淺色字壓深色底。Phase 5 把它擴充成六族（色彩／字級／間距／
圓角／陰影／動效），並立下並存紀律：**Quasar 保留版面 utility（flex／間距），
禁用顏色與字級 utility**——顏色只能從 token 來，否則深色切換必然漏。

本檔是那條紀律的機械守門人：
1. 六族齊備。
2. 深色模式覆寫「每一個」色彩 token（漏一個就紅）。
3. 關鍵前景／背景配對 WCAG AA ≥ 4.5:1（含負向 fixture，證明計算器會紅）。
4. `prefers-reduced-motion` 真的把動效時長歸零。
5. presentation/ 原始碼零 Quasar 顏色／字級 utility（含負向 fixture）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from paper_kit.presentation.theme import THEME_CSS

PRESENTATION = Path(__file__).resolve().parents[2] / "src" / "paper_kit" / "presentation"

FAMILIES = ("color", "font", "space", "radius", "shadow", "motion")

QUASAR_COLORS = (
    "grey|primary|secondary|accent|dark|positive|negative|info|warning|white|black|"
    "red|pink|purple|deep-purple|indigo|blue|light-blue|cyan|teal|green|light-green|"
    "lime|yellow|amber|orange|deep-orange|brown|blue-grey"
)
QUASAR_COLOR_RE = re.compile(
    rf"(?<![\w-])(text|bg)-({QUASAR_COLORS})(?:-\d+)?(?![\w-])"
)
QUASAR_FONTSIZE_RE = re.compile(
    r"(?<![\w-])text-(xs|sm|base|lg|xl|2xl|3xl|4xl|5xl|6xl|7xl|8xl|9xl)(?![\w-])"
)


def _block(css: str, selector: str) -> str:
    """取出 selector 之後第一組大括號內容（主題檔結構單純，不用完整 CSS parser）。"""
    idx = css.find(selector)
    assert idx >= 0, f"THEME_CSS 找不到選擇器：{selector}"
    start = css.index("{", idx)
    depth = 0
    for pos in range(start, len(css)):
        if css[pos] == "{":
            depth += 1
        elif css[pos] == "}":
            depth -= 1
            if depth == 0:
                return css[start + 1 : pos]
    raise AssertionError(f"{selector} 大括號未閉合")


def _tokens(block: str) -> dict[str, str]:
    return {
        m.group(1): m.group(2).strip()
        for m in re.finditer(r"(--pk-[a-z0-9-]+)\s*:\s*([^;]+);", block)
    }


def _hex(value: str) -> str:
    m = re.search(r"#[0-9a-fA-F]{6}", value)
    assert m, f"token 不是可解析的 hex：{value!r}"
    return m.group(0)


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    channels = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]

    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    hi, lo = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def quasar_utility_offenders(source: str) -> list[str]:
    offenders = []
    for i, line in enumerate(source.splitlines(), 1):
        for m in QUASAR_COLOR_RE.finditer(line):
            offenders.append(f"L{i}: {m.group(0).strip()}（顏色 utility）")
        for m in QUASAR_FONTSIZE_RE.finditer(line):
            offenders.append(f"L{i}: {m.group(0).strip()}（字級 utility）")
    return offenders


def test_six_token_families_present():
    root = _tokens(_block(THEME_CSS, ":root"))
    for family in FAMILIES:
        names = [n for n in root if n.startswith(f"--pk-{family}-")]
        assert len(names) >= 3, f"token 族 {family} 不完整：{names}"


def test_dark_mode_overrides_every_color_token():
    light = _tokens(_block(THEME_CSS, ":root"))
    dark = _tokens(_block(THEME_CSS, "body.body--dark"))
    light_colors = {n for n in light if n.startswith("--pk-color-")}
    missing = sorted(light_colors - set(dark))
    assert not missing, f"深色模式漏覆寫色彩 token：{missing}"


def test_dark_block_only_redefines_tokens():
    dark = _block(THEME_CSS, "body.body--dark")
    stray = [
        ln.strip()
        for ln in dark.splitlines()
        if ln.strip() and not ln.strip().startswith("--pk-")
    ]
    assert not stray, f"深色區塊只能重新定義 token，出現其他敘述：{stray}"


CONTRAST_PAIRS = [
    ("--pk-color-text", "--pk-color-bg"),
    ("--pk-color-text", "--pk-color-surface"),
    ("--pk-color-text-muted", "--pk-color-bg"),
    ("--pk-color-text-muted", "--pk-color-surface"),
    ("--pk-color-primary", "--pk-color-surface"),
    ("--pk-color-success", "--pk-color-surface"),
    ("--pk-color-warning", "--pk-color-surface"),
    ("--pk-color-error", "--pk-color-surface"),
    ("--pk-color-nav-active-text", "--pk-color-nav-active-bg"),
]


@pytest.mark.parametrize("scheme,selector", [("light", ":root"), ("dark", "body.body--dark")])
@pytest.mark.parametrize("fg,bg", CONTRAST_PAIRS)
def test_contrast_pairs_pass_wcag_aa(scheme, selector, fg, bg):
    tokens = _tokens(_block(THEME_CSS, selector))
    ratio = contrast_ratio(_hex(tokens[fg]), _hex(tokens[bg]))
    assert ratio >= 4.5, f"{scheme}: {fg} on {bg} 只有 {ratio:.2f}:1（需 ≥ 4.5）"


def test_contrast_checker_detects_low_contrast_negative_fixture():
    assert contrast_ratio("#888888", "#999999") < 4.5
    assert contrast_ratio("#000000", "#ffffff") >= 21 - 0.01


def test_reduced_motion_zeroes_durations():
    idx = THEME_CSS.find("@media (prefers-reduced-motion: reduce)")
    assert idx >= 0, "缺少 prefers-reduced-motion 區塊"
    block = THEME_CSS[idx:]
    for token in ("--pk-motion-fast", "--pk-motion-base", "--pk-motion-slow"):
        assert re.search(rf"{token}\s*:\s*0m?s", block), f"{token} 未被歸零"


def test_no_quasar_color_or_fontsize_utilities():
    offenders: list[str] = []
    for path in sorted(PRESENTATION.glob("*.py")):
        offenders += [f"{path.name}:{o}" for o in quasar_utility_offenders(path.read_text(encoding="utf-8"))]
    assert not offenders, (
        "presentation 使用 Quasar 顏色／字級 utility（改走 pk-* 語意 class）：\n"
        + "\n".join(offenders)
    )


def test_quasar_scanner_detects_offender_negative_fixture():
    assert quasar_utility_offenders('.classes("text-grey-5")')
    assert quasar_utility_offenders('.classes("bg-primary text-white")')
    assert quasar_utility_offenders('.classes("text-lg font-semibold")')
    assert not quasar_utility_offenders('.classes("text-center gap-2 pk-muted")')
