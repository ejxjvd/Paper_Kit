"""SettingsService（application）：設定頁 ↔ repo 的 typed 存取＋引擎解析。

換引擎＝set_engine + resolve_engine；FakeEngine 測試守住「換插頭零改動」。
"""

from paper_kit.application.ports import EngineError, TranslationEnginePort
from paper_kit.infrastructure.engine_registry import ENGINE_SPECS, EngineSpec, build_engine
from paper_kit.infrastructure.settings_repo import (
    DEFAULT_ENGINE_ID,
    DEFAULT_TARGET_LANG,
    SqliteSettingsRepository,
)


class SettingsService:
    def __init__(self, repo: SqliteSettingsRepository):
        self._repo = repo

    # ── 引擎 ──────────────────────────────────────────────

    def engine_id(self) -> str:
        return self._repo.get("engine_id", DEFAULT_ENGINE_ID) or DEFAULT_ENGINE_ID

    def set_engine(self, engine_id: str) -> None:
        if engine_id not in ENGINE_SPECS:
            raise KeyError(engine_id)
        self._repo.set("engine_id", engine_id)

    def engine_spec(self) -> EngineSpec:
        return ENGINE_SPECS[self.engine_id()]

    def api_key(self, engine_id: str) -> str:
        return self._repo.get_api_key(engine_id)

    def set_api_key(self, engine_id: str, api_key: str) -> None:
        self._repo.set_api_key(engine_id, api_key)

    def resolve_engine(self) -> TranslationEnginePort:
        """依設定建引擎；缺 key 給友善錯誤（FakeEngine 注入路徑不受影響）。"""
        spec = self.engine_spec()
        if spec.needs_key and not self.api_key(spec.id):
            raise EngineError(f"尚未設定 {spec.label} 的 API key（設定頁填入後再翻譯）")
        return build_engine(spec, api_key=self.api_key(spec.id))

    # ── 語言／輸出目錄 ──────────────────────────────────────

    def target_lang(self) -> str:
        return self._repo.get("target_lang", DEFAULT_TARGET_LANG) or DEFAULT_TARGET_LANG

    def set_target_lang(self, lang: str) -> None:
        self._repo.set("target_lang", lang)

    def output_dir(self) -> str:
        return self._repo.get("output_dir", "") or ""

    def set_output_dir(self, path: str) -> None:
        self._repo.set("output_dir", path)

    # ── 票 05：術語表挑選＋自動提取 ────────────────────────────

    def selected_glossaries(self) -> list[str] | None:
        """挑選的術語表名；未存過回 None（呼叫端用「全選」），存過（含空）原樣回傳。"""
        raw = self._repo.get("selected_glossaries")
        if raw is None:
            return None
        return [n for n in raw.split(",") if n]

    def set_selected_glossaries(self, names: list[str]) -> None:
        self._repo.set("selected_glossaries", ",".join(names))

    def selected_glossary_names(self, all_names: list[str]) -> list[str]:
        """「未存過 → 全選」慣例單一入口（UI 呼叫點不再各自寫 None 判斷）。"""
        stored = self.selected_glossaries()
        return stored if stored is not None else all_names

    def auto_extract(self) -> bool:
        """自動術語提取開關（--term-siliconflow）；預設關。"""
        return (self._repo.get("auto_extract", "0") or "0") == "1"

    def set_auto_extract(self, on: bool) -> None:
        self._repo.set("auto_extract", "1" if on else "0")

    # ── 票 11：深色模式偏好 ────────────────────────────────────

    def dark_mode(self) -> bool:
        """深色模式偏好；預設深色（論文翻譯工具夜間使用為主）。"""
        return (self._repo.get("dark_mode", "1") or "1") == "1"

    def set_dark_mode(self, on: bool) -> None:
        self._repo.set("dark_mode", "1" if on else "0")
