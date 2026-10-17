"""檔案管理員開啟與下載守衛（T-07 相位 4 自 app.py 抽出）。

`_real_path` 讀的是本模組全域的 `OUTPUTS_DIR`——測試隔離時 patch
`paper_kit.presentation.file_ops.OUTPUTS_DIR`。
"""

import logging
from pathlib import Path

from nicegui import ui

from paper_kit.platform import (
    folder_opener as _platform_folder_opener,
    open_folder as _platform_open_folder,
)
from paper_kit.presentation.runtime import FILES_BASE, OUTPUTS_DIR

logger = logging.getLogger("paper_kit.presentation.file_ops")


def _folder_opener(platform_name: str | None = None) -> str | None:
    """平台 → 檔案管理員命令（純函式，實作收斂於 platform.folder_opener）。"""
    return _platform_folder_opener(platform_name)


def _open_folder(path: Path) -> None:
    """開啟系統檔案管理員到指定資料夾（平台分派收斂於 platform.open_folder）。

    win32 → explorer.exe（WSL 路徑正規化，輸入可為 C:\\... 或 /mnt/c/...）、
    macOS → Finder（open）、Linux → xdg-open；任何失敗 → notify 錯誤
    （使用者實測「點按無回應」的靜默感從此消除）。
    """
    try:
        target = _platform_open_folder(path)
        ui.notify(f"已開啟資料夾：{target}", type="positive")
    except Exception as exc:
        logger.error("開啟資料夾失敗", extra={"path": str(path), "error": str(exc)})
        ui.notify(f"開啟資料夾失敗：{exc}", type="negative")


def _real_path(view_url: str) -> Path:
    """/files/<job_id>/<name> → 磁碟真實路徑（下載用）。"""
    return OUTPUTS_DIR / view_url.split(FILES_BASE + "/", 1)[1]


def _download_output(view_url: str) -> None:
    """#83：產出檔不存在 → 不下載、改 ui.notify 警示。

    真因鏈末端（2026-08-13 實測）：ghost COMPLETED（引擎零產出＋假路徑）或
    產出遺失時，ui.download(缺檔路徑) → NiceGUI helpers.is_file=False → fallback
    from_url → 瀏覽器 fetch 失敗、服務端回 HTML →「失敗 - 沒有檔案」+ .htm。
    守衛：檔案真實存在才下載（mono/dual 皆經此函）。
    """
    path = _real_path(view_url)
    if not path.is_file():
        ui.notify(f"檔案不存在：{path.name}（產出遺失或未生成）", type="warning")
        return
    ui.download(str(path))
