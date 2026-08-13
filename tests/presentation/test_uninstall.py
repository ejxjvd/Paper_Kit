"""乾淨卸載測試（v0.1.2）。

背景（2026-08-14 使用者指出「你這不乾淨啊」）：v0.1.2 起資料與程式同
資料夾（portable，exe 旁 data/）→ 刪除程式資料夾即全部清除；
`paper-kit --uninstall` 為可選保險（只清資料、留程式）。本測試守住
uninstall_all_data 的刪除行為（參數化注入目錄，不碰真實 APP_DIR）。
"""

from pathlib import Path

from paper_kit.presentation.app import uninstall_all_data


def test_uninstall_removes_everything(tmp_path: Path):
    """app 資料目錄（含 db/輸出/設定）整包刪除。"""
    (tmp_path / "paper_kit.db").write_bytes(b"db")
    (tmp_path / "outputs" / "abc").mkdir(parents=True)
    (tmp_path / "outputs" / "abc" / "out.pdf").write_bytes(b"pdf")
    (tmp_path / "settings.json").write_text("{}")

    removed = uninstall_all_data(tmp_path)

    assert removed == tmp_path
    assert not tmp_path.exists(), "整個 app 資料目錄應被刪除"


def test_uninstall_missing_dir_is_safe(tmp_path: Path):
    """資料目錄不存在時不炸（fresh 安裝直接跑 uninstall）。"""
    removed = uninstall_all_data(tmp_path / "nope")
    assert removed == tmp_path / "nope"


def test_uninstall_only_touches_given_dir(tmp_path: Path):
    """只刪目標目錄，不動其他（同層旁目錄安在）。"""
    target = tmp_path / "app_data"
    target.mkdir()
    (target / "db").write_bytes(b"x")
    neighbor = tmp_path / "keep_me"
    neighbor.mkdir()

    uninstall_all_data(target)

    assert not target.exists()
    assert neighbor.exists()
