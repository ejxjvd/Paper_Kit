"""GlossaryRepository（infrastructure）：術語庫＝目錄下多份 CSV 檔。

票 05：多份術語表各自命名成檔；CRUD（新增／改名／刪除／讀寫）。
名稱防呆：空白、路徑分隔符、逗號、"."、".." 一律拒絕（檔名=術語表名）。
"""

import pytest

from paper_kit.domain.glossary import Glossary
from paper_kit.infrastructure.glossary_repo import GlossaryNameError, GlossaryRepository


def make_repo(tmp_path) -> GlossaryRepository:
    return GlossaryRepository(tmp_path / "glossaries")


def test_new_repo_lists_nothing(tmp_path):
    assert make_repo(tmp_path).list_names() == []


def test_create_then_list_and_read(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("deepseek-nlp")
    assert repo.list_names() == ["deepseek-nlp"]
    assert len(repo.read("deepseek-nlp")) == 0  # 空術語表可讀


def test_create_duplicate_rejected(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("dl")
    with pytest.raises(GlossaryNameError, match="已存在"):
        repo.create("dl")


def test_write_and_read_round_trip(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("dl")
    repo.write("dl", Glossary.parse("source,target\nattention,注意力機制\n"))
    g = repo.read("dl")
    assert g.get("attention") == "注意力機制"


def test_rename(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("a")
    repo.rename("a", "b")
    assert repo.list_names() == ["b"]
    with pytest.raises(KeyError):
        repo.read("a")


def test_rename_to_existing_rejected(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("a")
    repo.create("b")
    with pytest.raises(GlossaryNameError, match="已存在"):
        repo.rename("a", "b")


def test_rename_missing_rejected(tmp_path):
    repo = make_repo(tmp_path)
    with pytest.raises(KeyError):
        repo.rename("missing", "b")


def test_delete(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("a")
    repo.delete("a")
    assert repo.list_names() == []
    with pytest.raises(KeyError):
        repo.read("a")


def test_delete_missing_rejected(tmp_path):
    with pytest.raises(KeyError):
        make_repo(tmp_path).delete("missing")


@pytest.mark.parametrize(
    "bad",
    ["", "   ", ".", "..", "a/b", "a\\b", "a,b", "a\x00b",
     "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b"],
)
def test_invalid_names_rejected(tmp_path, bad):
    repo = make_repo(tmp_path)
    with pytest.raises(GlossaryNameError):
        repo.create(bad)


def test_trailing_dot_stripped(tmp_path):
    """Windows 檔名尾點會被吃 → 直接剝掉（避免 create 成功但檔案名不符）。"""
    repo = make_repo(tmp_path)
    repo.create("my gloss.")
    assert repo.list_names() == ["my gloss"]


def test_names_are_stripped(tmp_path):
    repo = make_repo(tmp_path)
    repo.create("  my gloss  ")
    assert repo.list_names() == ["my gloss"]


def test_path_for_resolves_under_dir(tmp_path):
    repo = make_repo(tmp_path)
    assert repo.path_for("dl") == tmp_path / "glossaries" / "dl.csv"
