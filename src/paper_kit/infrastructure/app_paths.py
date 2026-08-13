"""應用程式資料目錄（單一權威，v0.1.2 portable 化）。

背景（2026-08-14 使用者指出「你這不乾淨啊」）：資料原存 ~/.paper_kit，
刪除程式資料夾不會清資料＝卸載不乾淨。v0.1.2 改為 **資料跟程式走
（portable）**：PyInstaller 打包後（sys.frozen）資料在 exe 旁的 `data/`
——刪除整個程式資料夾＝全部清除、系統零殘留。開發/測試（非 frozen）
退回 ~/.paper_kit，不污染原始碼資料夾（既有測試與習慣不變）。

app.py（UI/任務資料）與 uv_bootstrap.py（uv 工具落點）共用本模組，
避免 frozen 判定兩邊漂移。
"""

import sys
from pathlib import Path

# 非 frozen（開發/測試）時的落點——與 v0.1.1 相同
_DEV_APP_DIR_NAME = ".paper_kit"


def app_data_dir() -> Path:
    """應用程式資料目錄。

    - 打包後（PyInstaller）：exe 旁的 `data/`（portable——刪資料夾即全清）
    - 開發/測試：`~/.paper_kit`
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path.home() / _DEV_APP_DIR_NAME
