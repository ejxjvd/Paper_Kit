"""Paper_Kit NiceGUI 介面——入口與門面（T-07 相位 4 切分後）。

原本這裡是 2,349 行的單體；現在只留啟動黏合層（port 檢查、卸載、
uv 狀態、`main()` 組裝）與**門面 re-export**。頁面建構搬到：

- `presentation/index_page.py`——主頁（引擎卡、任務卡、進度輪詢）
- `presentation/settings_page.py`——設定頁（keys、術語庫、計價、快取）
- `presentation/history_page.py`——歷史頁與批量下載路由
- `presentation/debug_page.py`——Debug log 頁
- `presentation/shell.py`——共用頁框／側欄／主題
- `presentation/file_ops.py`——檔案管理員開啟與下載守衛
- `presentation/job_actions.py`——任務重試／取消／刪除（單筆與批量）
- `presentation/runtime.py`——路徑常數

門面契約由 `tests/presentation/test_app_facade.py` 守門：切分前的 64 個頂層
名稱必須全部還能從本模組取得，且本模組不得再定義已搬走的函式。
"""

import logging
import multiprocessing  # macOS 遞迴修復（freeze_support，BUG_REPORT v0.1.8）
import shutil
import socket  # 啟動前 port 檢查
import sys
import threading  # _uv_startup_status：啟動背景安裝執行緒（2026-08-15）
from pathlib import Path

from nicegui import app, ui

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.ocr import OcrService  # 票 12：掃描件 OCR
from paper_kit.application.settings_service import SettingsService
from paper_kit.application.translation_cache import TranslationCache  # 票 25：設定頁快取區
from paper_kit.platform import platform_label  # App 內版本標註（平台分離，2026-08-14）
from paper_kit.platform.windows.explorer import (  # 命名相容薄轉發（既有測試沿用舊名）
    explorer_target as _explorer_target,
    win_to_wsl as _win_to_wsl,
)
from paper_kit.presentation.composition import (
    GlossaryRepository,
    RapidOcrAdapter,
    SqliteJobRepository,
    SqliteSettingsRepository,
    setup_logging,
)
from paper_kit.presentation.debug_page import _debug_page
from paper_kit.presentation.file_ops import (
    _download_output,
    _folder_opener,
    _open_folder,
    _real_path,
)
from paper_kit.presentation.history_page import (
    _cost_label,
    _history_page,
    _history_row,
    _history_rows,
    _tokens_label,
    register_batch_download_route,
)
from paper_kit.presentation.handlers import build_job_card  # 命名相容（測試以門面組卡片資料）
from paper_kit.presentation.index_page import (
    _engine_picker,
    _index_page,
    _is_latex_dense_source,
    _notify_estimate,
    _preview,
    _refresh,
    _render_card,
    _render_single_engine_card,
    _resolve_task_engine,
    _save_engine_choice,
    _start_job,
    _swap_single_engine_card,
)
from paper_kit.presentation.job_actions import (
    _batch_cancel,
    _batch_retry,
    _cancel_job,
    _confirm_delete_one,
    _delete_jobs,
    _do_delete_one,
    _retry_job,
)
from paper_kit.presentation.runtime import (
    APP_DIR,
    DB_PATH,
    DEFAULT_PORT,
    FILES_BASE,
    GLOSSARIES_DIR,
    OUTPUTS_DIR,
)
from paper_kit.presentation.settings_page import (
    _add_entry,
    _cache_stats_label,
    _create_glossary,
    _delete_entry,
    _delete_glossary,
    _import_glossary,
    _key_handlers,
    _rename_glossary,
    _render_engine_key_card,
    _render_entries,
    _save_defaults,
    _save_pricing,
    _seed_builtin,
    _seed_naer,
    _settings_page,
    _sync_glossary_pickers,
)
from paper_kit.presentation.shell import (
    BADGE_COLORS,
    SIDEBAR_NAV,
    _engine_label_map,
    _enter_theme,
    _nav_active,
    _toggle_theme,
    app_frame,
)

logger = logging.getLogger("paper_kit.presentation.app")

# ── 門面 re-export 群組（契約見 tests/presentation/test_app_facade.py）──────
# 路徑常數：APP_DIR／OUTPUTS_DIR／GLOSSARIES_DIR／DB_PATH／FILES_BASE／DEFAULT_PORT
# 頁框：BADGE_COLORS／SIDEBAR_NAV／_nav_active／_engine_label_map／_enter_theme
#       ／_toggle_theme／app_frame
# 檔案：_folder_opener／_open_folder／_real_path／_download_output
# 任務操作：_retry_job／_delete_jobs／_confirm_delete_one／_do_delete_one
#           ／_batch_retry／_batch_cancel／_cancel_job
# 主頁：_resolve_task_engine … _index_page（12 個）
# 設定頁：_key_handlers … _save_pricing（16 個）
# 歷史頁：_history_page／register_batch_download_route／_history_rows
#         ／_tokens_label／_cost_label／_history_row
# Debug：_debug_page


def _port_available(port: int, host: str = "0.0.0.0") -> bool:
    """port 是否可綁定（True＝可用）。bind 失敗（OSError）＝已被佔用。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def uninstall_all_data(app_dir: Path = APP_DIR) -> Path:
    """v0.1.2：乾淨卸載——刪除整個 app 資料目錄（任務歷史、設定、KEY、
    輸出、logs、術語表）。回傳被刪路徑（不存在也安全）。
    v0.1.2 起資料與程式同資料夾（portable，exe 旁 data/）→ 刪除整個
    程式資料夾即全部清除；`--uninstall` 為可選保險（只清資料、留程式，
    2026-08-14 使用者要求「乾淨」定案）。
    """
    if app_dir.exists():
        shutil.rmtree(app_dir)
    return app_dir


def _uv_startup_status() -> threading.Thread | None:
    """啟動即顯示 uv 狀態（2026-08-15 使用者：打開 exe 的 CMD 就要看到
    uv 是否安裝中/進度/完成——之前 uv 動作只在翻譯時 lazy 觸發，打開
    後 CMD 只有 NiceGUI ready，什麼進度都沒有）。

    找到 → log 位置；缺 → 背景下載安裝（log 即時印 CMD：來源/嘗試/進度/
    速度/完成/失敗重試）——不阻塞 UI ready；翻譯時的 resolve_uv 走
    download_uv 鎖（uv_bootstrap._download_lock），已完成或另一執行緒
    在裝都會正確處理。回傳背景執行緒（測試 join）。
    """
    from paper_kit.presentation.composition import uv_bootstrap as uv_boot

    existing = uv_boot.installed_uv()
    if existing is not None:
        uv_boot.logger.info("uv 檢查：已找到 %s", existing)
        return None
    uv_boot.logger.info(
        "uv 檢查：未找到——自動安裝中（4 源備援 GitHub→PyPI→清華→阿里雲，"
        "進度即時顯示，失敗自動重試）"
    )
    t = threading.Thread(
        target=uv_boot.download_uv,
        kwargs={"timeout": 120},
        daemon=True,
        name="uv-auto-install",
    )
    t.start()
    return t


def main() -> None:
    # macOS 嚴重問題修復（BUG_REPORT_macOS_v0.1.8，2026-08-14）：PyInstaller
    # frozen exe＋macOS spawn → resource_tracker 子程序重跑主程式 → 無限遞迴
    # （實測 117 程序）＋8080 衝突＋connection lost。freeze_support() 必須在
    # 任何可能啟動 multiprocessing 的初始化之前（PyInstaller 官方慣例：入口
    # 第一行；Windows frozen exe 同受惠）。
    multiprocessing.freeze_support()
    # v0.1.2：`paper-kit --uninstall`——乾淨卸載（console 視窗執行）
    if "--uninstall" in sys.argv:
        try:  # Windows console 可能是 cp1252/cp950——中文訊息先轉 UTF-8
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        removed = uninstall_all_data()
        print(f"已刪除 Paper_Kit 全部資料：{removed}")
        print("現在可以安全刪除程式資料夾（exe 與 _internal）。")
        sys.exit(0)
    if not _port_available(DEFAULT_PORT):
        # 啟動前檢查：port 被佔用（舊實例未關／macOS 遞迴殘留）→ 明確錯誤
        # 退出——實測 macOS 綁定失敗後仍輸出「NiceGUI ready」的假象＋
        # 「connection lost」；重複啟動的 8080 衝突也在此攔下。
        print(
            f"錯誤：Port {DEFAULT_PORT} 已被佔用——可能已有 Paper_Kit 在執行。",
            file=sys.stderr,
        )
        print("請先關閉舊實例，或確認佔用者：", file=sys.stderr)
        print(f"  lsof -nP -iTCP:{DEFAULT_PORT} -sTCP:LISTEN  （macOS／Linux）", file=sys.stderr)
        print(f"  netstat -ano | findstr :{DEFAULT_PORT}      （Windows）", file=sys.stderr)
        sys.exit(1)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH = setup_logging(APP_DIR / "logs")  # 票 09：結構化 log 檔（debug 頁讀同一份）
    # 2026-08-15：啟動即顯示 uv 狀態（找到/缺→背景下載安裝，進度印 CMD）
    _uv_startup_status()
    app.add_static_files(FILES_BASE, str(OUTPUTS_DIR))
    repo = SqliteSettingsRepository(DB_PATH)
    # 票 08：SQLite 任務歷史——重啟 app 後任務仍在（InMemory 只留給無頭執行）
    # 票 12：注入 OcrService（RapidOCR 本機引擎）——掃描件預處理用
    settings = SettingsService(repo)
    # 票 24/25：翻譯快取——main() 組裝並注入 JobService 與設定頁（enabled 依設定頁開關即時同步）
    cache = TranslationCache(APP_DIR / "cache", enabled=settings.cache_enabled())
    service = JobService(
        jobs=SqliteJobRepository(DB_PATH),
        outputs_dir=OUTPUTS_DIR,
        ocr=OcrService(RapidOcrAdapter()),
        cache=cache,
    )
    cost = CostService(repo)
    glossaries = GlossaryService(GlossaryRepository(GLOSSARIES_DIR))

    _index_page(service, settings, cost, glossaries)
    _settings_page(settings, cost, glossaries, cache)
    _history_page(service, settings, cost)  # #26：歷史表金額欄需要 CostService
    register_batch_download_route(service)  # 票 18：批量下載 zip 路由
    _debug_page(LOG_PATH, settings)
    # 平台分離（2026-08-14）：App 內版本標註（瀏覽器 tab 標題顯示平台版本）
    ui.run(
        title=f"Paper_Kit 論文翻譯器（{platform_label()} 版）",
        reload=False,
        port=DEFAULT_PORT,
    )

__all__ = [
    "APP_DIR",
    "BADGE_COLORS",
    "DB_PATH",
    "DEFAULT_PORT",
    "FILES_BASE",
    "GLOSSARIES_DIR",
    "OUTPUTS_DIR",
    "SIDEBAR_NAV",
    "_add_entry",
    "_batch_cancel",
    "_batch_retry",
    "_cache_stats_label",
    "_cancel_job",
    "_confirm_delete_one",
    "_cost_label",
    "_create_glossary",
    "_debug_page",
    "_delete_entry",
    "_delete_glossary",
    "_delete_jobs",
    "_do_delete_one",
    "_download_output",
    "_engine_label_map",
    "_engine_picker",
    "_enter_theme",
    "_explorer_target",
    "_folder_opener",
    "_history_page",
    "_history_row",
    "_history_rows",
    "_import_glossary",
    "_index_page",
    "_is_latex_dense_source",
    "_key_handlers",
    "_nav_active",
    "_notify_estimate",
    "_open_folder",
    "_port_available",
    "_preview",
    "_real_path",
    "_refresh",
    "_rename_glossary",
    "_render_card",
    "_render_engine_key_card",
    "_render_entries",
    "_render_single_engine_card",
    "_resolve_task_engine",
    "_retry_job",
    "_save_defaults",
    "_save_engine_choice",
    "_save_pricing",
    "_seed_builtin",
    "_seed_naer",
    "_settings_page",
    "_start_job",
    "_swap_single_engine_card",
    "_sync_glossary_pickers",
    "_toggle_theme",
    "_tokens_label",
    "_uv_startup_status",
    "_win_to_wsl",
    "app_frame",
    "build_job_card",
    "logger",
    "main",
    "register_batch_download_route",
    "uninstall_all_data",
]
