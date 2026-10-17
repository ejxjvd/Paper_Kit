"""Phase 3 seam 守門：presentation 只能透過組合根認識 infrastructure。

背景：v0.3 之前 `app.py` 直接 import 9 個 infrastructure 模組（adapter、registry、
repo、探測器）。Phase 4 要切分 `app.py`，這種散落的 import 會讓每個新模組都得
複製一份、漏一個就是執行期 NameError。修法是把所有認識集中到
`presentation/composition.py`（組合根）。

本測試是那個約定的機械守門人：
1. `presentation/` 下除 `composition.py` 外，任何 `paper_kit.infrastructure` import 即紅。
2. 組合根本身不得 import `nicegui`（要被純函式測試直接 import，也避免 UI 洩漏）。
3. 組合根必須真的 re-export app 需要的符號（漏 export = 執行期 ImportError，
   但只有在真的跑到那段 UI 時才會炸——所以在這裡一次驗完）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PRESENTATION = Path(__file__).resolve().parents[2] / "src" / "paper_kit" / "presentation"
COMPOSITION = PRESENTATION / "composition.py"


def _imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, node.lineno))
    return found


def _offenders_in(dirpath: Path) -> list[str]:
    offenders = []
    for path in sorted(dirpath.glob("*.py")):
        if path.name == "composition.py":
            continue
        for module, line in _imports(path):
            if module == "paper_kit.infrastructure" or module.startswith(
                "paper_kit.infrastructure."
            ):
                offenders.append(f"{path.name}:{line} -> {module}")
    return offenders


def test_presentation_does_not_import_infrastructure_directly():
    offenders = _offenders_in(PRESENTATION)
    assert not offenders, (
        "presentation 直接 import infrastructure（應改走 composition）：\n"
        + "\n".join(offenders)
    )


def test_guard_detects_violation_negative_fixture(tmp_path):
    """負向 fixture：把違規寫進暫存目錄，守門人必須抓到——否則這道閘門是假綠燈。"""
    (tmp_path / "bad_page.py").write_text(
        "from paper_kit.infrastructure.job_repo import SqliteJobRepository\n",
        encoding="utf-8",
    )
    (tmp_path / "ok_page.py").write_text(
        "from paper_kit.presentation.composition import SqliteJobRepository\n",
        encoding="utf-8",
    )
    offenders = _offenders_in(tmp_path)
    assert len(offenders) == 1, offenders
    assert "bad_page.py" in offenders[0], offenders


def test_composition_is_the_only_seam():
    assert COMPOSITION.is_file(), "缺少組合根 presentation/composition.py"
    modules = [m for m, _ in _imports(COMPOSITION)]
    assert any(m.startswith("paper_kit.infrastructure") for m in modules), (
        "組合根沒有 re-export 任何 infrastructure 符號——它失去存在意義"
    )


def test_composition_does_not_import_nicegui():
    ui = [f"{m}:{ln}" for m, ln in _imports(COMPOSITION) if m.split(".")[0] == "nicegui"]
    assert not ui, f"組合根不得 import nicegui（{ui}）"


@pytest.mark.parametrize(
    "symbol",
    [
        "ENGINE_SPECS",
        "build_engine",
        "can_select",
        "resolve_key",
        "sensitive_blocked",
        "spec_has_key",
        "GlossaryNameError",
        "GlossaryRepository",
        "SqliteJobRepository",
        "SqliteSettingsRepository",
        "app_data_dir",
        "detect_latex_dense",
        "diagnose",
        "list_models",
        "probe_key",
        "probe_model",
        "format_log_line",
        "recent_log_entries",
        "setup_logging",
        "RapidOcrAdapter",
        "uv_bootstrap",
    ],
)
def test_composition_exports_symbol_used_by_app(symbol):
    import importlib

    comp = importlib.import_module("paper_kit.presentation.composition")
    assert hasattr(comp, symbol), f"組合根漏 export：{symbol}"


def test_composition_reachable_after_nicegui_pops_parents(monkeypatch):
    """回歸：NiceGUI 測試 harness 會把路由模組「及其所有父套件」踢出 sys.modules。

    `nicegui.testing.general.nicegui_reset_globals` 的 teardown 對每個已註冊頁面
    路由做 `sys.modules.pop`，連同 `paper_kit`／`paper_kit.presentation` 一起移除
    （nicegui/testing/general.py:86）。結果是 composition 還留在 sys.modules，
    但它的父套件不見了——`import a.b.c as x` 這種寫法會炸
    `ImportError: cannot import name 'presentation' from 'paper_kit'`。

    `app.py` 用的是 `from paper_kit.presentation.composition import X`，不受影響；
    本測試把這個差異釘住，避免日後有人「順手」改寫成 `import ... as ...`
    而在完整測試套件裡炸掉（單跑本檔不會炸，因為沒有路由模組被 pop）。
    """
    import importlib
    import sys

    comp = importlib.import_module("paper_kit.presentation.composition")
    for name in ("paper_kit.presentation.app", "paper_kit.presentation", "paper_kit"):
        monkeypatch.delitem(sys.modules, name, raising=False)

    from paper_kit.presentation.composition import ENGINE_SPECS  # noqa: F401

    again = importlib.import_module("paper_kit.presentation.composition")
    assert again is comp, "父套件被 pop 後 composition 必須仍是同一個模組物件"
    assert hasattr(again, "uv_bootstrap")


def test_app_module_imports_without_ui_side_effects():
    """app.py 匯入路徑不得在 import 期就啟動 NIceGUI 伺服器（回歸：曾因頂層呼叫而炸）。"""
    import importlib

    mod = importlib.import_module("paper_kit.presentation.app")
    assert hasattr(mod, "main"), "app.py 應提供 main()（入口契約）"
