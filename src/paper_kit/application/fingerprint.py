"""Fingerprinter（application）：任務層快取輸入指紋（票 24）。

純函式：同一組輸入（引擎實際讀取的檔案內容＋引擎＋語言＋頁面＋敏感＋
術語表內容）→ 同一指紋；任一輸入變動 → 不同指紋。順序不敏感的術語表
（[g1, g2] 與 [g2, g1] 同指紋——翻譯結果相同，不應造成假 miss）。
"""

import hashlib
from pathlib import Path

_GLOSSARY_SEPARATOR = "+"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(
    source_path: str | Path,
    engine_id: str,
    target_lang: str,
    pages: str | None,
    sensitive: bool,
    glossary_files: list[str | Path],
) -> str:
    """輸入指紋：v1|來源檔內容 SHA-256|引擎|語言|頁面|敏感|術語表內容 SHA-256 排序聯結。

    v1 前綴：未來指紋演算法升級時可版本化（舊快取自然失效）。
    pages 正規化（None → 空字串）：None 與空白語意相同（票 07 parse_pages）。
    """
    file_hash = _file_sha256(Path(source_path))
    gloss_hashes = sorted(_file_sha256(Path(g)) for g in glossary_files)
    return "|".join(
        [
            "v1",
            file_hash,
            engine_id,
            target_lang,
            pages or "",
            "1" if sensitive else "0",
            _GLOSSARY_SEPARATOR.join(gloss_hashes),
        ]
    )
