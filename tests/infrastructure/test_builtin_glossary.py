"""內建術語表（#84 方案 A）：自研詞表資料契約＋種子冪等。

授權紅線（2026-08-14 research 查證）：immersive-translate/terms 無 LICENSE
＝保留所有權利——本模組詞條一律自研彙編，CSV 三欄格式（source,target,
tgt_lng）與其相容（日後上游補授權可直吃通用子集，見
docs/research/2026-08-14-Paper_Kit-研究-immersive-terms術語庫-查證.md）。
"""

import csv
import io

from paper_kit.application.glossary_service import GlossaryService
from paper_kit.domain.glossary import Glossary
from paper_kit.infrastructure.builtin_glossary import BUILTIN_GLOSSARY_CSV, BUILTIN_GLOSSARY_NAME
from paper_kit.infrastructure.glossary_repo import GlossaryRepository


def make_service(tmp_path) -> GlossaryService:
    return GlossaryService(GlossaryRepository(tmp_path / "glossaries"))


def test_builtin_csv_parses_to_nonempty_glossary():
    """內建詞表必須是合法 CSV 且非空（目標語系 zh-TW）。"""
    g = Glossary.parse(BUILTIN_GLOSSARY_CSV, target_lang="zh-TW")
    assert len(g) > 100, "內建詞表規模應 >100 條（核心領域精選）"
    assert all(target.strip() for _, target in g.entries())


def test_builtin_csv_terms_are_unique():
    """source 不得重複（同詞跨領域以單一最佳譯名收錄）。"""
    g = Glossary.parse(BUILTIN_GLOSSARY_CSV, target_lang="zh-TW")
    sources = [s for s, _ in g.entries()]
    assert len(sources) == len(set(sources))


def test_builtin_csv_all_rows_tgt_lng_zh_tw():
    """每列 tgt_lng 必須為 zh-TW（三欄齊備——與 immersive-terms 格式相容的證據）。"""
    import csv
    import io

    reader = csv.DictReader(io.StringIO(BUILTIN_GLOSSARY_CSV))
    rows = list(reader)
    assert rows, "CSV 需有資料列"
    assert all(r["tgt_lng"].strip().lower() == "zh-tw" for r in rows)


def test_builtin_csv_no_source_contains_comma_or_quote():
    """source/target 不得含逗號或引號（上游 4,906 列實測亦無——naive 解析相容）。"""
    import csv
    import io

    reader = csv.DictReader(io.StringIO(BUILTIN_GLOSSARY_CSV))
    for row in reader:
        for col in ("source", "target"):
            assert not any(ch in row[col] for ch in ',"'), f"{col!r} 含逗號/引號: {row[col]!r}"


def test_seed_creates_glossary(tmp_path):
    """seed（service 層）：內建詞表不存在時建立，回傳 True。"""
    svc = make_service(tmp_path)
    created = svc.seed_builtin()
    assert created is True
    assert BUILTIN_GLOSSARY_NAME in svc.list_glossaries()
    assert len(svc.entries(BUILTIN_GLOSSARY_NAME)) > 100


def test_seed_is_idempotent_does_not_overwrite(tmp_path):
    """seed 冪等（service 層）：已存在時不覆寫使用者內容，回傳 False。"""
    svc = make_service(tmp_path)
    svc.import_csv(BUILTIN_GLOSSARY_NAME, "source,target\ncustom,自訂譯名\n", target_lang="zh-TW")
    created = svc.seed_builtin()
    assert created is False
    assert svc.entries(BUILTIN_GLOSSARY_NAME) == [("custom", "自訂譯名")]  # 未覆寫
