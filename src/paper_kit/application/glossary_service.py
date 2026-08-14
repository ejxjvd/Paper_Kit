"""GlossaryService（application）：術語庫 CRUD＋CSV 匯入（票 05）。

多份術語表各自命名成檔；CSV 匯入的解析/驗證規則委派領域 Glossary（單一真相）；
檔案 IO 在 infra GlossaryRepository——這裡只管編排（錯誤原樣上拋，UI 顯示）。
"""

from paper_kit.domain.glossary import Glossary
from paper_kit.infrastructure.glossary_repo import GlossaryRepository


class GlossaryService:
    def __init__(self, repo: GlossaryRepository):
        self._repo = repo

    def list_glossaries(self) -> list[str]:
        return self._repo.list_names()

    def create_glossary(self, name: str) -> None:
        self._repo.create(name)

    def rename_glossary(self, old: str, new: str) -> None:
        self._repo.rename(old, new)

    def delete_glossary(self, name: str) -> None:
        self._repo.delete(name)

    def entries(self, name: str) -> list[tuple[str, str]]:
        """編輯頁顯示：有序 (source, target) 列表。"""
        return self._repo.read(name).entries()

    def add_entry(self, name: str, source: str, target: str) -> None:
        """新增/覆寫一列（不可變領域物件 → 全量寫回）。"""
        self._repo.write(name, self._repo.read(name).with_entry(source.strip(), target.strip()))

    def delete_entry(self, name: str, index: int) -> None:
        self._repo.write(name, self._repo.read(name).without_index(index))

    def import_csv(self, name: str, csv_text: str, target_lang: str = "zh") -> int:
        """CSV 上傳：領域驗證標頭（缺 source/target → GlossaryFormatError）→ 全量寫入。

        回傳匯入列數（tgt_lng 不符目標語言的列被領域跳過）。
        """
        glossary = Glossary.parse(csv_text, target_lang=target_lang)
        self._repo.write(name, glossary)
        return len(glossary)

    def seed_builtin(self) -> bool:
        """#84 方案 A：匯入內建基礎詞表（自研 265 條，繁中論文翻譯核心領域）。

        冪等：名稱已存在絕不覆寫（使用者可能已編輯）。回傳是否新建立。
        詞條全自研（授權紅線見 builtin_glossary 模組 docstring——immersive
        terms 無 LICENSE 不得複製，此為格式相容的自研資料）。
        """
        from paper_kit.infrastructure.builtin_glossary import (
            BUILTIN_GLOSSARY_CSV,
            BUILTIN_GLOSSARY_NAME,
        )

        if BUILTIN_GLOSSARY_NAME in self._repo.list_names():
            return False
        self.import_csv(BUILTIN_GLOSSARY_NAME, BUILTIN_GLOSSARY_CSV, target_lang="zh-TW")
        return True

    def paths_for(self, names: list[str]) -> list[str]:
        """挑選的術語表名 → 存在檔案的絕對路徑（不存在的跳過）。"""
        existing = set(self._repo.list_names())
        return [str(self._repo.path_for(n)) for n in names if n in existing]
