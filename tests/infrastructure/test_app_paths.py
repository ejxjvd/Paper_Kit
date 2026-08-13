"""portable 資料目錄單一權威測試（v0.1.2）。

背景（2026-08-14 使用者指出「你這不乾淨啊」）：v0.1.2 起資料跟程式走——
打包後（sys.frozen）資料在 exe 旁 data/，刪除整個程式資料夾＝全部清除、
系統零殘留；開發/測試（非 frozen）退回 ~/.paper_kit（與 v0.1.1 相同，
不污染原始碼資料夾）。本測試守住兩分支不漂移。
"""

import sys
from pathlib import Path

from paper_kit.infrastructure.app_paths import app_data_dir


def test_development_uses_home_dir(monkeypatch, tmp_path):
    """非 frozen（開發/測試）：資料在 ~/.paper_kit。"""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    assert app_data_dir() == tmp_path / ".paper_kit"


def test_frozen_uses_exe_side_data_dir(monkeypatch, tmp_path):
    """打包後（PyInstaller）：資料在 exe 旁的 data/（portable——刪資料夾即全清）。"""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    exe = tmp_path / "paper-kit-v0.1.2" / "paper-kit.exe"
    monkeypatch.setattr(sys, "executable", str(exe))

    assert app_data_dir() == (exe.parent / "data").resolve()
