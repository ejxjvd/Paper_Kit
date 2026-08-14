"""內建術語表（#84 方案 A）：自研詞表資料契約＋種子冪等。

授權紅線（2026-08-14 research 查證）：immersive-translate/terms 無 LICENSE
＝保留所有權利——本模組詞條一律自研彙編，CSV 三欄格式（source,target,
tgt_lng）與其相容（日後上游補授權可直吃通用子集，見
docs/research/2026-08-14-Paper_Kit-研究-immersive-terms術語庫-查證.md）。
"""

import csv
import functools
import io

from paper_kit.application.glossary_service import GlossaryService
from paper_kit.domain.glossary import Glossary
from paper_kit.infrastructure.builtin_glossary import (
    BUILTIN_GLOSSARY_CSV,
    BUILTIN_GLOSSARY_NAME,
    NAER_GLOSSARY_NAME,
)
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


# ---------------------------------------------------------------------------
# naer-core（樂詞網學術名詞）資料契約——來源國家教育研究院樂詞網，依政府資料
# 開放授權條款-第1版使用（顯名聲明見 builtin_glossary 模組 docstring 與
# scripts/naer_build.py 檔頭）。生成腳本可重現，資料為版本化資源檔。
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _naer_csv() -> str:
    import gzip
    from importlib import resources

    path = resources.files("paper_kit.infrastructure.data").joinpath("naer_core.csv.gz")
    assert path.is_file(), "naer_core.csv.gz 資源檔不存在——先跑 scripts/naer_build.py 生成"
    return gzip.decompress(path.read_bytes()).decode("utf-8")


def test_naer_core_resource_exists_parses_and_is_large():
    """樂詞網詞表 gzip 資源：存在、可解壓、領域可解析、達規模（>2 萬條）。"""
    g = Glossary.parse(_naer_csv(), target_lang="zh-TW")
    assert len(g) > 20_000, "naer-core 應 >2 萬條（2026-08-14 生成基準 29,295）"


def test_naer_core_source_contract_alpha_start_single_word_no_parens():
    """source 契約（生成準則，scripts/naer_build.py）：小寫字母開頭、無空格、
    無括號/大括號——濾除檔名（.shtml）、代碼（1080p/24）、ISO 括號註記。"""
    for source, _ in Glossary.parse(_naer_csv(), target_lang="zh-TW").entries():
        assert source[0].islower(), f"source 開頭非小寫字母: {source!r}"
        assert " " not in source, f"source 含空格（非單詞）: {source!r}"
        assert not any(ch in source for ch in "()（）[]{}"), f"source 含括號/註記: {source!r}"


def test_naer_core_all_rows_tgt_lng_zh_tw():
    """每列 tgt_lng 必須為 zh-TW（三欄齊備——與既有 paper-kit-basic 同契約）。"""
    reader = csv.DictReader(io.StringIO(_naer_csv()))
    rows = list(reader)
    assert rows, "CSV 需有資料列"
    assert all(r["tgt_lng"].strip().lower() == "zh-tw" for r in rows)


def test_naer_core_no_source_contains_comma_or_quote():
    """source/target 不得含逗號或引號（naive 解析相容，同 paper-kit-basic 契約）。"""
    reader = csv.DictReader(io.StringIO(_naer_csv()))
    for row in reader:
        for col in ("source", "target"):
            assert not any(ch in row[col] for ch in ',"'), f"{col!r} 含逗號/引號: {row[col]!r}"


def test_naer_core_sources_unique():
    """source 全域唯一（領域 parse 的 dict 化不可丟列）。"""
    csv_text = _naer_csv()
    parsed = Glossary.parse(csv_text, target_lang="zh-TW")
    raw_count = sum(1 for _ in csv.DictReader(io.StringIO(csv_text)))
    assert len(parsed) == raw_count, "有 source 重複被後者覆寫"


def test_naer_core_spot_check_academic_terms():
    """抽樣：真學術詞條（非噪音）——算盤/橫坐標/吸收等。"""
    g = Glossary.parse(_naer_csv(), target_lang="zh-TW")
    for src, tgt in (("abacus", "算盤"), ("abscissa", "橫坐標；橫軸"), ("absorption", "吸收")):
        assert g.get(src) == tgt, f"{src!r} 應譯為 {tgt!r}（樂詞網學術名詞）"


def test_naer_core_seed_creates_glossary(tmp_path):
    """seed_naer（service 層）：不存在時建立，回傳 True，規模達契約。"""
    svc = make_service(tmp_path)
    created = svc.seed_naer()
    assert created is True
    assert NAER_GLOSSARY_NAME in svc.list_glossaries()
    assert len(svc.entries(NAER_GLOSSARY_NAME)) > 20_000


def test_naer_core_seed_is_idempotent_does_not_overwrite(tmp_path):
    """seed_naer 冪等：已存在時不覆寫使用者內容，回傳 False。"""
    svc = make_service(tmp_path)
    svc.import_csv(NAER_GLOSSARY_NAME, "source,target\ncustom,自訂譯名\n", target_lang="zh-TW")
    created = svc.seed_naer()
    assert created is False
    assert svc.entries(NAER_GLOSSARY_NAME) == [("custom", "自訂譯名")]  # 未覆寫
