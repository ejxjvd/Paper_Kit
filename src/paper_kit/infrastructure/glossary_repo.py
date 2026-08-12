"""GlossaryRepository（infrastructure）：術語庫＝目錄下多份 CSV 檔。

票 05：多份術語表各自命名成檔（檔名＝術語表名＋.csv）；
檔內容的解析/序列化規則在領域 Glossary（單一真相），這裡只管檔案 IO。
名稱防呆：空白、路徑分隔符、逗號、"．"、".." 一律拒絕。
"""

from pathlib import Path

from paper_kit.domain.glossary import Glossary

# Windows 保留字元（本機為 Windows；檔名=術語表名，寫檔前全擋掉）
_FORBIDDEN_CHARS = '/\\,*?"<>|:'


class GlossaryNameError(ValueError):
    """無效術語表名（空白、含分隔符、重複等）。"""


class GlossaryRepository:
    def __init__(self, dir_path: str | Path):
        self._dir = Path(dir_path)
        self._dir.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> list[str]:
        """術語表名（＝*.csv 檔名，排序）。"""
        return sorted(p.stem for p in self._dir.glob("*.csv"))

    def path_for(self, name: str) -> Path:
        """術語表名 → 檔名（含驗證；寫入操作共用同一路徑規則）。"""
        clean = self._validate(name)
        return self._dir / f"{clean}.csv"

    @staticmethod
    def _validate(name: str) -> str:
        clean = name.strip().strip(".")  # Windows 檔名尾點會被吃 → 先剝掉
        if not clean or clean in {".", ".."}:
            raise GlossaryNameError("術語表名不可為空白")
        if any(ch in clean for ch in _FORBIDDEN_CHARS):
            raise GlossaryNameError(f"術語表名不可含 {_FORBIDDEN_CHARS}：{name!r}")
        if any(ord(c) < 32 for c in clean):
            raise GlossaryNameError("術語表名不可含控制字元")
        return clean

    def create(self, name: str) -> None:
        path = self.path_for(name)
        if path.exists():
            raise GlossaryNameError(f"術語表已存在：{name}")
        self.write(name, Glossary.parse(""))  # 空表檔頭走領域 to_csv（單一真相）

    def read(self, name: str) -> Glossary:
        path = self.path_for(name)
        if not path.exists():
            raise KeyError(name)
        return Glossary.parse(path.read_text(encoding="utf-8"))

    def write(self, name: str, glossary: Glossary) -> None:
        self.path_for(name).write_text(glossary.to_csv(), encoding="utf-8")

    def rename(self, old: str, new: str) -> None:
        src = self.path_for(old)
        if not src.exists():
            raise KeyError(old)
        dest = self.path_for(new)
        if dest.exists():
            raise GlossaryNameError(f"術語表已存在：{new}")
        src.rename(dest)

    def delete(self, name: str) -> None:
        path = self.path_for(name)
        if not path.exists():
            raise KeyError(name)
        path.unlink()
