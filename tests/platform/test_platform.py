"""平台分離 TDD（2026-08-14 使用者要求：macOS／Windows 各自乾淨專案，避免汙染）。

工程事實（2026-08-14 統計）：單一源碼 7,618 行中平台分支僅 18 處——99.8%
是平台無關共用核心。使用者拍板「repo 內平台資料夾分離」：平台知識全部收斂
於 paper_kit.platform 套件——

- platform/__init__.py    dispatch 單點（open_folder／kill_tree／spawn_kwargs）
                           ＋平台標籤（App 內版本標註）
- platform/macos/         macOS 版專屬（Finder 開啟、POSIX 樹殺）——Linux
                           開發兜底共用（同為 POSIX 行為，不進 windows/）
- platform/windows/       Windows 版專屬（explorer 開啟＋WSL 路徑正規化、
                           taskkill 樹殺）
- platform/uv_assets.py   uv 官方二進制資產查表（win32/darwin/linux）

分離守則（本檔強制）：macos/ 與 windows/ 互不 import、互不引用。
"""

import ast
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import paper_kit.platform as platform_mod
from paper_kit.platform import macos, windows
from paper_kit.platform.macos import finder as macos_finder
from paper_kit.platform.macos import processes as macos_processes
from paper_kit.platform.windows import explorer as win_explorer
from paper_kit.platform.windows import processes as win_processes


class _FakeProc:
    """poll 返回物——kill_tree 守衛（已退場判定）用。"""

    def __init__(self, pid: int = 7, poll=None):
        self.pid = pid
        self._poll = poll

    def poll(self):
        return self._poll


# ── 平台標籤（App 內版本標註：「Paper_Kit 論文翻譯器（Windows 版）」） ──


def test_platform_label_maps_three_platforms(monkeypatch):
    assert platform_mod.platform_label() in ("Windows", "macOS", "Linux")  # 本機實跑值
    monkeypatch.setattr(sys, "platform", "win32")
    assert platform_mod.platform_label() == "Windows"
    monkeypatch.setattr(sys, "platform", "darwin")
    assert platform_mod.platform_label() == "macOS"
    monkeypatch.setattr(sys, "platform", "linux")
    assert platform_mod.platform_label() == "Linux"


# ── 檔案管理員開啟 dispatch（單點分派） ──────────────────


def test_open_folder_win32_routes_to_explorer(tmp_path, monkeypatch):
    """win32 → windows/explorer.open_folder（explorer.exe＋WSL 正規化）。"""
    monkeypatch.setattr(sys, "platform", "win32")
    # 防 Popen mock 攔到 subprocess.run 內部的 Popen（帶 text kwargs 炸）——
    # wslpath 層單獨 mock run 給假 UNC（既有測試同法）
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0, stdout="\\\\wsl.localhost\\Ubuntu\\tmp\\x\n"
        ),
    )
    calls: list = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    shown = platform_mod.open_folder(tmp_path / "out")
    assert calls and calls[0][0] == "explorer.exe"
    assert shown == r"\\wsl.localhost\Ubuntu\tmp\x", "顯示 target＝正規化後的 explorer 路徑"


def test_open_folder_darwin_routes_to_finder(tmp_path, monkeypatch):
    """darwin → macos/finder.open_folder（open = Finder）＋先建目錄。"""
    monkeypatch.setattr(sys, "platform", "darwin")
    calls: list = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    shown = platform_mod.open_folder(tmp_path / "out")
    assert calls == [["open", str(tmp_path / "out")]]
    assert shown == str(tmp_path / "out")
    assert (tmp_path / "out").is_dir(), "Finder 分支也先建目錄"


def test_open_folder_linux_uses_xdg_open(tmp_path, monkeypatch):
    """linux（開發兜底）→ xdg-open（POSIX 通則與 macOS 共用）。"""
    monkeypatch.setattr(sys, "platform", "linux")
    calls: list = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd: calls.append(cmd))
    platform_mod.open_folder(tmp_path / "out")
    assert calls[0][0] == "xdg-open"


def test_folder_opener_maps_platforms():
    """純函式（v0.1.1 既有語意保留）：darwin→open、linux→xdg-open、win32→None。"""
    assert platform_mod.folder_opener("darwin") == "open"
    assert platform_mod.folder_opener("linux") == "xdg-open"
    assert platform_mod.folder_opener("win32") is None


# ── kill_tree dispatch（macOS 遞迴修復相關樹殺） ──────────


def test_kill_tree_win32_routes_to_taskkill(monkeypatch):
    """win32 → windows/processes.kill_tree（taskkill /T /F 遞迴殺整棵樹）。"""
    monkeypatch.setattr(sys, "platform", "win32")
    ran: list = []
    monkeypatch.setattr(
        win_processes.subprocess, "run", lambda *a, **k: ran.append(a[0])
    )
    platform_mod.kill_tree(_FakeProc())
    assert ran and ran[0][:2] == ["taskkill", "/T"]


def test_kill_tree_posix_routes_to_killpg(monkeypatch):
    """darwin → macos/processes.kill_tree（killpg 殺進程組）。"""
    monkeypatch.setattr(sys, "platform", "darwin")
    killed: list = []
    monkeypatch.setattr(
        macos_processes.os, "killpg", lambda pid, sig: killed.append(pid)
    )
    platform_mod.kill_tree(_FakeProc(pid=42))
    assert killed == [42]


def test_kill_tree_exited_proc_noop(monkeypatch):
    """已退場（poll 非 None）→ 不動作（兩平台共用守衛在 dispatch 層）。"""
    monkeypatch.setattr(sys, "platform", "win32")
    ran: list = []
    monkeypatch.setattr(win_processes.subprocess, "run", lambda *a, **k: ran.append(a))
    platform_mod.kill_tree(_FakeProc(poll=1))
    assert ran == []


# ── spawn 參數（Popen） ─────────────────────────────────


def test_spawn_kwargs_win32_empty(monkeypatch):
    """win32 無進程組語意（taskkill /T 遞迴即可，不需要組長）。"""
    monkeypatch.setattr(sys, "platform", "win32")
    assert platform_mod.spawn_kwargs() == {}


def test_spawn_kwargs_posix_new_session(monkeypatch):
    """POSIX 進程組長（start_new_session）——kill_tree 才殺得到整棵樹。"""
    monkeypatch.setattr(sys, "platform", "darwin")
    assert platform_mod.spawn_kwargs() == {"start_new_session": True}


# ── 分離守則：macos/ 與 windows/ 互不 import ─────────────


def _import_top_level(src: str) -> set[str]:
    """AST 抽取模組頂層 import 的第一段名（`from a.b import c` → {a}）。"""
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _assert_isolated(path: Path, forbidden: str, label: str) -> None:
    src = path.read_text(encoding="utf-8")
    imports = _import_top_level(src)
    assert forbidden not in imports, (
        f"{label} import 了 {forbidden}（分離鐵律：macos/ 與 windows/ 互不 import）"
    )


def test_macos_windows_modules_are_isolated():
    """平台分離鐵律：macos/ 與 windows/ 互不 import（各自乾淨）。

    AST 掃 import 語句（docstring 提及對方位址是文件指引、非 import，
    不屬「污染」）。擴充新平台行為模組時此測試自動守門。
    """
    _assert_isolated(Path(macos_finder.__file__), "windows", "macos/finder.py")
    _assert_isolated(Path(win_explorer.__file__), "macos", "windows/explorer.py")


def test_macos_windows_processes_are_isolated():
    """processes 模組同樣互不 import（樹殺實作各自乾淨）。"""
    _assert_isolated(Path(macos_processes.__file__), "windows", "macos/processes.py")
    _assert_isolated(Path(win_processes.__file__), "macos", "windows/processes.py")
