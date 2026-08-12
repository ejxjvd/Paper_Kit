"""TranslationCache（application）：任務層快取（票 24 快取核心）。

紅→綠 slice 2：SQLite 索引＋快取檔自有副本——put/get/clear/stats；
快取是優化不是依賴（DB 損壞、外部刪檔都不炸）。
"""

from pathlib import Path

import pytest

from paper_kit.application.translation_cache import CachedResult, TranslationCache


def make_cache(tmp_path: Path, enabled: bool = True) -> TranslationCache:
    return TranslationCache(cache_dir=tmp_path / "cache", enabled=enabled)


def write_file(path: Path, content: bytes) -> Path:
    path.write_bytes(content)
    return path


def test_put_then_get_returns_cached_result(tmp_path: Path):
    cache = make_cache(tmp_path)
    mono = write_file(tmp_path / "mono.pdf", b"MONO")
    dual = write_file(tmp_path / "dual.pdf", b"DUAL")

    cache.put("fp1", str(mono), str(dual))

    hit = cache.get("fp1")
    assert hit is not None
    assert Path(hit.mono_path).read_bytes() == b"MONO"
    assert Path(hit.dual_path).read_bytes() == b"DUAL"


def test_get_miss_returns_none(tmp_path: Path):
    cache = make_cache(tmp_path)
    assert cache.get("never-put") is None


def test_put_mono_only(tmp_path: Path):
    """PPT 視覺／LaTeX 路徑單一產出（dual=None）照常快取。"""
    cache = make_cache(tmp_path)
    mono = write_file(tmp_path / "note.pdf", b"NOTE")

    cache.put("fp-mono-only", str(mono), None)

    hit = cache.get("fp-mono-only")
    assert hit is not None
    assert Path(hit.mono_path).read_bytes() == b"NOTE"
    assert hit.dual_path is None


def test_cache_files_are_own_copies(tmp_path: Path):
    """票 24 設計：快取持有自有副本——原檔刪除後命中不受影響（票 18 刪任務刪輸出）。"""
    cache = make_cache(tmp_path)
    mono = write_file(tmp_path / "mono.pdf", b"MONO")
    cache.put("fp-copy", str(mono), None)
    mono.unlink()  # 原輸出被刪（刪任務）

    hit = cache.get("fp-copy")
    assert hit is not None and Path(hit.mono_path).exists()


def test_clear_empties_cache(tmp_path: Path):
    cache = make_cache(tmp_path)
    cache.put("fp1", str(write_file(tmp_path / "m1.pdf", b"M1")), None)
    cache.put("fp2", str(write_file(tmp_path / "m2.pdf", b"M2")), None)

    cache.clear()

    assert cache.get("fp1") is None
    assert cache.get("fp2") is None
    assert cache.stats() == (0, 0)


def test_stats_counts_tasks_and_bytes(tmp_path: Path):
    cache = make_cache(tmp_path)
    cache.put("fp1", str(write_file(tmp_path / "m1.pdf", b"12345")), None)  # 5 bytes
    cache.put("fp2", str(write_file(tmp_path / "m2.pdf", b"123")), None)    # 3 bytes

    count, total = cache.stats()
    assert count == 2
    assert total == 8


def test_corrupt_db_degrades_gracefully(tmp_path: Path):
    """快取是優化不是依賴：DB 損壞 → get 回 None、put 不炸、翻譯照常。"""
    cache = make_cache(tmp_path)
    cache.put("fp-ok", str(write_file(tmp_path / "m.pdf", b"M")), None)
    # 破壞 DB（直接寫垃圾進 index.db，模擬毀損/殘斷）
    (tmp_path / "cache" / "index.db").write_bytes(b"garbage not a sqlite file")

    broken = make_cache(tmp_path)  # 重建指向同目錄（壞 DB）

    assert broken.get("fp-ok") is None  # 不炸、回 None
    broken.put("fp-new", str(write_file(tmp_path / "m2.pdf", b"N")), None)  # 不炸
    assert broken.get("fp-new") is None  # 寫不進去也要安靜（優化不是依賴）


def test_externally_deleted_cache_file_self_heals(tmp_path: Path):
    cache = make_cache(tmp_path)
    cache.put("fp1", str(write_file(tmp_path / "m1.pdf", b"M1")), None)
    hit = cache.get("fp1")
    assert hit is not None
    Path(hit.mono_path).unlink()  # 外部刪檔（使用者手動清目錄）

    assert cache.get("fp1") is None  # 自癒：回 None、不殘留死索引


def test_enabled_flag_defaults_true_and_settable(tmp_path: Path):
    """票 25 UI 開關的承載旗標（JobService 層決定查不查；這裡只承載狀態）。"""
    assert make_cache(tmp_path).enabled is True
    assert make_cache(tmp_path, enabled=False).enabled is False
