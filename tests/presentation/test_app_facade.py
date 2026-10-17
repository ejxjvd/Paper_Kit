"""T-07 相位 4：`app.py` 切分後的門面契約。

背景：切分前 `app.py` 是 2,349 行的單體（頁面建構、任務操作、設定頁、歷史頁、
debug 頁全在一起）。切分時最大的風險是**門面漏 export**：測試與外部入口都
`from paper_kit.presentation.app import X`，漏一個就是執行期 ImportError，而且
只有在真的走到那段路徑時才會炸——這是靜默失去保護的典型形態。

本檔三層守門：
1. 基準清單（`app_facade_baseline.txt`，切分前以 AST 產生的 64 個頂層名稱）
   必須全部還能從 `app` 取得。
2. `app.py` 只剩門面：行數上限＋不得再定義已搬走的函式（防止有人「搬回去」
   造成兩份實作漂移）。
3. 檢查器本身要有負向 fixture——證明它真的會紅，而不是永遠綠。
"""

from __future__ import annotations

import ast
import importlib
import types
from pathlib import Path

import pytest

APP_PY = Path(__file__).resolve().parents[2] / "src" / "paper_kit" / "presentation" / "app.py"
BASELINE_FILE = Path(__file__).with_name("app_facade_baseline.txt")

# 已搬出的函式 → 新落點模組（app.py 不得再定義）
MOVED = {
    "shell": [
        "_nav_active",
        "_engine_label_map",
        "_enter_theme",
        "_toggle_theme",
        "app_frame",
    ],
    "file_ops": ["_folder_opener", "_open_folder", "_real_path", "_download_output"],
    "job_actions": [
        "_retry_job",
        "_delete_jobs",
        "_confirm_delete_one",
        "_do_delete_one",
        "_batch_retry",
        "_batch_cancel",
        "_cancel_job",
    ],
    "index_page": [
        "_resolve_task_engine",
        "_engine_picker",
        "_render_single_engine_card",
        "_swap_single_engine_card",
        "_start_job",
        "_notify_estimate",
        "_render_card",
        "_preview",
        "_refresh",
        "_is_latex_dense_source",
        "_save_engine_choice",
        "_index_page",
    ],
    "settings_page": [
        "_key_handlers",
        "_render_engine_key_card",
        "_cache_stats_label",
        "_settings_page",
        "_save_defaults",
        "_sync_glossary_pickers",
        "_import_glossary",
        "_create_glossary",
        "_seed_builtin",
        "_seed_naer",
        "_delete_glossary",
        "_rename_glossary",
        "_render_entries",
        "_delete_entry",
        "_add_entry",
        "_save_pricing",
    ],
    "history_page": [
        "_history_page",
        "register_batch_download_route",
        "_history_rows",
        "_tokens_label",
        "_cost_label",
        "_history_row",
    ],
    "debug_page": ["_debug_page"],
}

# 門面必須保留的入口（真正住在 app.py 的東西）
STAYS_IN_APP = ["main", "uninstall_all_data", "_port_available", "_uv_startup_status"]

MAX_FACADE_LINES = 600


def _baseline() -> list[str]:
    lines = [
        ln.strip()
        for ln in BASELINE_FILE.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    assert len(lines) >= 60, f"基準清單異常短（{len(lines)}）——檔案被動過手腳？"
    return lines


def _missing(module: object, names: list[str]) -> list[str]:
    return [n for n in names if not hasattr(module, n)]


def _top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
    return out


def test_facade_reexports_every_baseline_name():
    app = importlib.import_module("paper_kit.presentation.app")
    missing = _missing(app, _baseline())
    assert not missing, (
        "門面漏 re-export（切分前存在、現在從 app 取不到）：\n" + "\n".join(missing)
    )


def test_facade_check_detects_missing_negative_fixture():
    """負向 fixture：拿掉一個名稱，檢查器必須抓到——否則這道閘門是假綠燈。"""
    stub = types.SimpleNamespace(main=lambda: None)
    assert _missing(stub, ["main", "_index_page"]) == ["_index_page"]


@pytest.mark.parametrize("module_name,names", sorted(MOVED.items()))
def test_moved_code_lives_in_its_module(module_name, names):
    mod = importlib.import_module(f"paper_kit.presentation.{module_name}")
    missing = _missing(mod, names)
    assert not missing, f"{module_name} 缺少：{missing}"


def test_app_py_no_longer_defines_moved_functions():
    defined = _top_level_names(APP_PY)
    moved = {name for names in MOVED.values() for name in names}
    duplicated = sorted(defined & moved)
    assert not duplicated, (
        "app.py 仍在定義已搬走的函式（會與新模組形成兩份實作）：\n"
        + "\n".join(duplicated)
    )


def test_app_py_is_thin_facade():
    lines = APP_PY.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= MAX_FACADE_LINES, (
        f"app.py 仍有 {len(lines)} 行（上限 {MAX_FACADE_LINES}）——切分沒有真的發生"
    )


@pytest.mark.parametrize("name", STAYS_IN_APP)
def test_entry_glue_stays_in_app(name):
    assert name in _top_level_names(APP_PY), f"{name} 應留在 app.py（入口黏合層）"
