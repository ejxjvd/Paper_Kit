"""Glossary 值物件（純函式，無 IO）。

POC 實測定案（babeldoc/glossary.py 來源核對）：
- CSV 必須含標頭列 `source,target[,tgt_lng]`
- tgt_lng 選填；若存在必須與目標語言相符（正規化：小寫、- → _）否則整列跳過
- 傳入內容字串而非檔案路徑 —— 檔案 IO 屬 infrastructure 層
"""

import csv
import io
from dataclasses import dataclass, field


class GlossaryFormatError(ValueError):
    """CSV 格式錯誤（缺標頭等）。"""


def _normalize_lang(lang: str) -> str:
    return lang.strip().lower().replace("-", "_")


@dataclass(frozen=True)
class Glossary:
    target_lang: str
    _terms: dict[str, str] = field(default_factory=dict)

    @classmethod
    def parse(cls, csv_text: str, target_lang: str = "zh") -> "Glossary":
        """解析 CSV 內容字串 → Glossary。缺 source/target 標頭丟 GlossaryFormatError。"""
        norm_target = _normalize_lang(target_lang)
        if not csv_text.strip():
            return cls(target_lang=norm_target)
        reader = csv.DictReader(io.StringIO(csv_text))
        fieldnames = reader.fieldnames or []
        if "source" not in fieldnames or "target" not in fieldnames:
            missing = [c for c in ("source", "target") if c not in fieldnames]
            raise GlossaryFormatError(
                f"術語表 CSV 缺必要欄位: {', '.join(missing)}（標頭列必須含 source,target）"
            )
        terms: dict[str, str] = {}
        for row in reader:
            if row.get("tgt_lng") and _normalize_lang(row["tgt_lng"]) != norm_target:
                continue  # tgt_lng 不符目標語言 → 整列跳過
            terms[row["source"]] = row["target"]
        return cls(target_lang=norm_target, _terms=terms)

    def get(self, source: str) -> str | None:
        return self._terms.get(source)

    def entries(self) -> list[tuple[str, str]]:
        """有序 (source, target) 列表（票 05：編輯頁顯示、序列化共用）。"""
        return list(self._terms.items())

    def to_csv(self) -> str:
        """序列化回 CSV（source,target 標頭）——儲存格式單一真相。"""
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")  # csv 預設 \r\n，統一 \n
        writer.writerow(["source", "target"])
        writer.writerows(self.entries())
        return buf.getvalue()

    def with_entry(self, source: str, target: str) -> "Glossary":
        """票 05：新增/覆寫一列（不可變——回傳新物件）。"""
        terms = dict(self._terms)
        terms[source] = target
        return Glossary(target_lang=self.target_lang, _terms=terms)

    def without_index(self, index: int) -> "Glossary":
        """票 05：刪除一列（越界丟 IndexError；不可變）。"""
        pairs = self.entries()
        if not 0 <= index < len(pairs):
            raise IndexError(f"術語列索引越界: {index}")
        del pairs[index]
        return Glossary(target_lang=self.target_lang, _terms=dict(pairs))

    def __len__(self) -> int:
        return len(self._terms)
