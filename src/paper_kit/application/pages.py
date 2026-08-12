"""頁面範圍規則（application 純函式）：驗證＋頁數計算（票 07）。

UI 輸入的頁面範圍（`1-2`／`3-5`／`1-2,4-6`／空白=全部）是 job 資料也是
成本估算的輸入——兩個 application service（JobService、CostService）共用，
故獨立成模組，不跨 service 互 import。
"""

import re

_PAGES_PATTERN = re.compile(r"^\d+(-\d+)?(,\d+(-\d+)?)*$")


def parse_pages(text: str | None) -> str | None:
    """驗證頁面範圍輸入。空白/None → None（全部頁面）；格式非法 → ValueError。

    語義檢查：頁碼 ≥ 1 且每段 起 ≤ 終（`5-2`／`0-5` 直接拒絕，不把壞範圍
    漏到引擎才爆——review 修正）。
    """
    if text is None:
        return None
    clean = text.strip()
    if not clean:
        return None
    if not _PAGES_PATTERN.match(clean):
        raise ValueError(f"頁面範圍格式錯誤：{clean!r}（如 1-2、3-5、1-2,4-6）")
    for part in clean.split(","):
        lo, _, hi = part.partition("-")
        if int(lo) < 1 or (hi and int(hi) < int(lo)):
            raise ValueError(f"頁面範圍無效：{clean!r}（頁碼 ≥1、起 ≤ 終）")
    return clean


def page_count_in_range(pages_spec: str) -> int:
    """範圍規格 → 頁數（成本估算按範圍縮放用；呼叫前已過 parse_pages 驗證）。"""
    total = 0
    for part in pages_spec.split(","):
        lo, _, hi = part.partition("-")
        total += int(hi) - int(lo) + 1 if hi else 1
    return total
