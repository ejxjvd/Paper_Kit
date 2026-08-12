"""Fingerprinter（application）：任務層快取輸入指紋（票 24 快取核心）。

紅→綠 slice 1：純函式——同輸入同指紋；任一輸入變動即不同。
"""

from pathlib import Path

import pytest

from paper_kit.application.fingerprint import fingerprint


def make_pdf(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def make_glossary(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_same_input_same_fingerprint(tmp_path: Path):
    src = make_pdf(tmp_path, "a.pdf", b"%PDF-1.4 same content")
    args = dict(
        source_path=src, engine_id="deepseek", target_lang="zh-TW",
        pages=None, sensitive=False, glossary_files=[],
    )
    assert fingerprint(**args) == fingerprint(**args)


def test_file_content_change_changes_fingerprint(tmp_path: Path):
    """同檔名改內容（user story 3）——改版後不誤用舊翻譯。"""
    a = make_pdf(tmp_path, "a.pdf", b"v1")
    b = make_pdf(tmp_path, "b.pdf", b"v2")  # 不同檔名先建立，再改名測「同檔名」
    a.write_bytes(b"v2")  # 現在 a.pdf 內容 = b.pdf 內容、檔名不同
    common = dict(engine_id="deepseek", target_lang="zh-TW", pages=None, sensitive=False, glossary_files=[])
    # 關鍵：內容相同 → 指紋相同（指紋綁內容不綁檔名）
    assert fingerprint(source_path=a, **common) == fingerprint(source_path=b, **common)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda a: dict(engine_id="siliconflow"),
        lambda a: dict(target_lang="en"),
        lambda a: dict(pages="1-2"),
        lambda a: dict(sensitive=True),
    ],
    ids=["engine", "lang", "pages", "sensitive"],
)
def test_each_parameter_change_changes_fingerprint(tmp_path: Path, mutate):
    src = make_pdf(tmp_path, "a.pdf", b"%PDF-1.4")
    base = dict(
        source_path=src, engine_id="deepseek", target_lang="zh-TW",
        pages=None, sensitive=False, glossary_files=[],
    )
    assert fingerprint(**base) != fingerprint(**{**base, **mutate(base)})


def test_glossary_content_change_changes_fingerprint(tmp_path: Path):
    src = make_pdf(tmp_path, "a.pdf", b"%PDF-1.4")
    g1 = make_glossary(tmp_path, "g1.txt", "LLM=大語言模型")
    g2 = make_glossary(tmp_path, "g2.txt", "LLM=大型語言模型")
    common = dict(
        source_path=src, engine_id="deepseek", target_lang="zh-TW",
        pages=None, sensitive=False,
    )
    assert fingerprint(glossary_files=[g1], **common) != fingerprint(glossary_files=[g2], **common)


def test_glossary_count_change_changes_fingerprint(tmp_path: Path):
    src = make_pdf(tmp_path, "a.pdf", b"%PDF-1.4")
    g1 = make_glossary(tmp_path, "g1.txt", "LLM=大語言模型")
    common = dict(
        source_path=src, engine_id="deepseek", target_lang="zh-TW",
        pages=None, sensitive=False,
    )
    assert fingerprint(glossary_files=[], **common) != fingerprint(glossary_files=[g1], **common)


def test_glossary_order_does_not_change_fingerprint(tmp_path: Path):
    """同一組術語表不同順序 → 同指紋（翻譯結果相同，不應造成假 miss）。"""
    src = make_pdf(tmp_path, "a.pdf", b"%PDF-1.4")
    g1 = make_glossary(tmp_path, "g1.txt", "LLM=大語言模型")
    g2 = make_glossary(tmp_path, "g2.txt", "GPU=顯示卡")
    common = dict(
        source_path=src, engine_id="deepseek", target_lang="zh-TW",
        pages=None, sensitive=False,
    )
    assert fingerprint(glossary_files=[g1, g2], **common) == fingerprint(glossary_files=[g2, g1], **common)


def test_missing_source_raises(tmp_path: Path):
    missing = tmp_path / "nope.pdf"
    with pytest.raises(FileNotFoundError):
        fingerprint(
            source_path=missing, engine_id="deepseek", target_lang="zh-TW",
            pages=None, sensitive=False, glossary_files=[],
        )
