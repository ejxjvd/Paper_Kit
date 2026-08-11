"""Glossary 值物件（純函式，無 IO —— 傳 CSV 內容字串，非檔案路徑）。

POC 實測定案：CSV 含標頭列 `source,target[,tgt_lng]`；
tgt_lng 選填，寫了必須與目標語言相符（正規化：小寫、- → _）否則整列跳過。
"""

import pytest

from paper_kit.domain.glossary import Glossary, GlossaryFormatError

VALID_CSV = "source,target\nattention,注意力機制\nsoftmax,Softmax\n"


def test_parse_valid_csv_and_lookup():
    g = Glossary.parse(VALID_CSV)
    assert g.get("attention") == "注意力機制"
    assert g.get("softmax") == "Softmax"
    assert g.get("missing") is None


def test_missing_source_header_clear_error():
    with pytest.raises(GlossaryFormatError, match="source"):
        Glossary.parse("target\n注意力機制\n")


def test_missing_target_header_clear_error():
    with pytest.raises(GlossaryFormatError, match="target"):
        Glossary.parse("source\nattention\n")


def test_empty_csv_is_empty_glossary():
    g = Glossary.parse("")
    assert len(g) == 0


def test_tgt_lng_matching_row_kept():
    csv_text = "source,target,tgt_lng\nattention,注意力機制,zh\n"
    g = Glossary.parse(csv_text, target_lang="zh")
    assert g.get("attention") == "注意力機制"


def test_tgt_lng_mismatch_row_skipped():
    csv_text = "source,target,tgt_lng\nattention,注意,en\ntransformer,Transformer,zh\n"
    g = Glossary.parse(csv_text, target_lang="zh")
    assert g.get("attention") is None  # en 列被跳過
    assert g.get("transformer") == "Transformer"


@pytest.mark.parametrize(
    "col_value,target_lang,expected",
    [
        ("zh-TW", "zh_tw", "繁體"),   # 破折號→底線 正規化
        ("ZH-TW", "zh-TW", "繁體"),   # 大小寫正規化
        ("zh-TW", "zh", None),        # zh-TW ≠ zh
    ],
)
def test_tgt_lng_normalization(col_value, target_lang, expected):
    target_col = expected if expected is not None else "不會命中"
    csv_text = f"source,target,tgt_lng\nword,{target_col},{col_value}\n"
    g = Glossary.parse(csv_text, target_lang=target_lang)
    assert g.get("word") == expected


def test_len_counts_entries():
    g = Glossary.parse(VALID_CSV)
    assert len(g) == 2
