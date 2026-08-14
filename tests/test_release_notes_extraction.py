"""Release notes 提取一致性（v0.1.8 bug 防回歸，2026-08-15 使用者抓到）。

v0.1.8 的 Release body 空（只剩「Paper_Kit 0.1.8」15 字元 fallback）——根因：
`.github/workflows/release.yml` 的 awk 提取 regex 為 `^## <tag>$`（無 v 前綴），
但 `packaging/RELEASE_NOTES.md` 標題帶 v（`## v0.1.8`）→ 匹配 0 行 → NOTES 空。

本測試：讀 CI 檔的 awk regex，驗證 RELEASE_NOTES.md 的每個區段標題都被
regex 匹配——提取邏輯若再壞（regex 改動／標題格式漂移），Release notes 會
再次空掉，測試先紅。
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RELEASE_YML = REPO / ".github" / "workflows" / "release.yml"
RELEASE_NOTES = REPO / "packaging" / "RELEASE_NOTES.md"


def _extraction_regexes() -> list[re.Pattern]:
    """從 release.yml 抽出 awk 的標題偵測 regex（`"X" tag "Y"` 拼接式）。"""
    text = RELEASE_YML.read_text(encoding="utf-8")
    # awk：$0 ~ "<前綴>" tag "<後綴>" → 執行時 regex = 前綴 + tag + 後綴；
    # 只抓含 tag 變數的（區段結束偵測 `$0 ~ "^## "` 無 tag，是另一用途）
    matches = re.findall(r'\$0\s*~\s*"([^"]*)"\s*tag\s*"([^"]*)"', text)
    assert matches, f"release.yml 找不到 awk 標題 regex：{RELEASE_YML}"
    return [re.compile(g1 + r"[0-9.]+" + g2) for g1, g2 in matches]


def test_release_notes_every_section_matches_ci_regex():
    """RELEASE_NOTES.md 每個 `## vX.Y.Z` 標題必須被 CI 提取 regex 匹配——
    不匹配＝該版 Release body 會是空的（v0.1.8 實測 bug）。"""
    headings = re.findall(r"^(## v?[0-9]+\.[0-9]+\.[0-9]+)$", RELEASE_NOTES.read_text(encoding="utf-8"), re.M)
    assert headings, "RELEASE_NOTES.md 找不到任何版本區段標題"
    regexes = _extraction_regexes()
    bad = [h for h in headings if not any(rx.fullmatch(h) for rx in regexes)]
    assert not bad, (
        f"以下區段標題不被 CI 提取 regex 匹配 → 該版 Release notes 會空：{bad}"
        f"（CI regex: {[rx.pattern for rx in regexes]}）"
    )


def test_release_notes_extraction_smoke():
    """模擬 CI awk 提取流程（Python 同構實作）：v0.1.8 區段必須提取到內容、
    且不含下一版標題。"""
    text = RELEASE_NOTES.read_text(encoding="utf-8")
    lines = text.splitlines()
    tag = "0.1.8"
    start = next(i for i, ln in enumerate(lines) if re.fullmatch(rf"## v?{tag}", ln))
    out = [lines[start]]
    for ln in lines[start + 1 :]:
        if re.fullmatch(r"## .*", ln):
            break
        out.append(ln)
    joined = "\n".join(out)
    assert "空殼模型誤報 401" in joined, f"v0.1.8 區段提取內容異常：{joined[:200]}"
    assert "## v0.1.7" not in joined, "提取範圍越界（夾帶下一版標題）"


@pytest.mark.parametrize("heading", ["## v0.1.9", "## 0.1.9"])
def test_regex_matches_variant_headings(heading):
    """regex 同時相容帶 v／不帶 v 兩種標題格式（v0.1.8 修復後）。"""
    regexes = _extraction_regexes()
    assert any(rx.fullmatch(heading) for rx in regexes), (
        f"{heading!r} 不被 CI 提取 regex 匹配：{[rx.pattern for rx in regexes]}"
    )
