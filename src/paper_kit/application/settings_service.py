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
