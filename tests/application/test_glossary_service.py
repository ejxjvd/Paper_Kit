"""GlossaryService（application）：術語庫 CRUD＋CSV 匯入（票 05）。

驗證：多份術語表管理、CSV 標頭驗證錯誤訊息清楚、tgt_lng 過濾、
挑選組合 resolve 成存在的檔案路徑（FakeEngine 傳遞在 job_service 測試）。
"""

import pytest

from paper_kit.application.glossary_service import GlossaryService
from paper_kit.domain.glossary import GlossaryFormatError
from paper_kit.infrastructure.glossary_repo import GlossaryNameError, GlossaryRepository

VALID_CSV = "source,target\nattention,注意力機制\nsoftmax,Softmax\n"


def make_service(tmp_path) -> GlossaryService:
    return GlossaryService(GlossaryRepository(tmp_path / "glossaries"))


def test_crud_lifecycle(tmp_path):
    svc = make_service(tmp_path)
    svc.create_glossary("dl")
    svc.rename_glossary("dl", "dl-v2")
    svc.add_entry("dl-v2", "attention", "注意力機制")
    assert svc.entries("dl-v2") == [("attention", "注意力機制")]
    svc.delete_entry("dl-v2", 0)
    assert svc.entries("dl-v2") == []
    svc.delete_glossary("dl-v2")
    assert svc.list_glossaries() == []


def test_duplicate_create_rejected(tmp_path):
    svc = make_service(tmp_path)
    svc.create_glossary("dl")
    with pytest.raises(GlossaryNameError, match="已存在"):
        svc.create_glossary("dl")


def test_import_csv_creates_entries(tmp_path):
    svc = make_service(tmp_path)
    count = svc.import_csv("dl", VALID_CSV, target_lang="zh-TW")
    assert count == 2
    assert svc.entries("dl") == [("attention", "注意力機制"), ("softmax", "Softmax")]


def test_import_csv_missing_header_clear_error(tmp_path):
    svc = make_service(tmp_path)
    with pytest.raises(GlossaryFormatError, match="source"):
        svc.import_csv("dl", "target\n注意力機制\n", target_lang="zh-TW")


def test_import_csv_tgt_lng_mismatch_rows_skipped(tmp_path):
    svc = make_service(tmp_path)
    csv_text = "source,target,tgt_lng\nattention,注意,en\ntransformer,Transformer,zh\n"
    count = svc.import_csv("dl", csv_text, target_lang="zh")
    assert count == 1
    assert svc.entries("dl") == [("transformer", "Transformer")]


def test_import_csv_empty_is_empty_glossary(tmp_path):
    svc = make_service(tmp_path)
    assert svc.import_csv("dl", "", target_lang="zh") == 0
    assert svc.entries("dl") == []


def test_import_csv_overwrites_existing(tmp_path):
    svc = make_service(tmp_path)
    svc.import_csv("dl", VALID_CSV, target_lang="zh")
    svc.import_csv("dl", "source,target\nnew,新詞\n", target_lang="zh")
    assert svc.entries("dl") == [("new", "新詞")]


def test_paths_for_only_existing_glossaries(tmp_path):
    svc = make_service(tmp_path)
    svc.create_glossary("dl")
    paths = svc.paths_for(["dl", "missing"])
    assert paths == [str((tmp_path / "glossaries" / "dl.csv"))]
