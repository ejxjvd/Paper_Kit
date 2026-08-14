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


# ── 常駐包定案（2026-08-14）：notes 提取失敗改硬失敗 ─────────────


def test_workflow_hard_fails_instead_of_silent_fallback():
    """空 notes 分支必須硬失敗（exit 1）——禁止「Paper_Kit X.Y.Z」15 字元
    fallback 靜默出空 notes（v0.1.8 實測教訓：空 notes 不影響 CI 綠燈）。"""
    text = RELEASE_YML.read_text(encoding="utf-8")
    empty_check = re.search(r"if\s*\[ -z \"\$\{NOTES\}\" \].*?fi", text, re.S)
    assert empty_check, f"release.yml 找不到空 notes 檢查分支：{RELEASE_YML}"
    block = empty_check.group(0)
    assert re.search(r'NOTES="Paper_Kit', block) is None, (
        "release.yml 仍含靜默 fallback（NOTES=\"Paper_Kit …\"）——提取失敗會再次出空 notes"
    )
    assert re.search(r"exit 1", block), "空 notes 分支必須 exit 1（硬失敗）"


def test_every_released_tag_has_notes_section():
    """硬失敗安全性：所有已發布 tag 在 RELEASE_NOTES.md 都有區段——
    歷史 tag 重發布不會誤觸硬失敗（常駐包「影響歷史重發布」顧慮排除）。"""
    import subprocess

    result = subprocess.run(
        ["git", "tag", "-l", "v*"], cwd=REPO, capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        pytest.skip("無 git 或無 tag（CI checkout 通常無 tag）")
    headings = set(
        re.findall(
            r"^## v?([0-9]+\.[0-9]+\.[0-9]+)$",
            RELEASE_NOTES.read_text(encoding="utf-8"),
            re.M,
        )
    )
    missing = [t for t in result.stdout.split() if t.removeprefix("v") not in headings]
    assert not missing, (
        f"以下已發布 tag 缺 RELEASE_NOTES 區段 → 重發布會硬失敗：{missing}"
    )


def test_current_version_has_notes_section():
    """發布前準備契約：pyproject 版本必須已有 RELEASE_NOTES 區段——
    tag 推進時提取不會失敗（正常發布不誤觸硬失敗）。"""
    pyproject = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', pyproject, re.M)
    assert m, "pyproject.toml 找不到 version"
    headings = re.findall(
        r"^## v?([0-9]+\.[0-9]+\.[0-9]+)$",
        RELEASE_NOTES.read_text(encoding="utf-8"),
        re.M,
    )
    assert m.group(1) in headings, (
        f"pyproject version {m.group(1)} 在 RELEASE_NOTES.md 缺區段——"
        f"tag v{m.group(1)} 發布時會硬失敗"
    )
