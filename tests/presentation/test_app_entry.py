"""macOS 嚴重問題修復 TDD（BUG_REPORT_macOS_v0.1.8，2026-08-14 使用者轉交）。

高嚴重度：PyInstaller frozen exe＋macOS spawn 啟動模式 → resource_tracker
子程序重跑主程式 → 無限遞迴（實測 117 程序）→ 8080 衝突＋connection lost。
修復：入口 freeze_support()（PyInstaller 官方慣例）＋啟動前 port 檢查
（被佔用→明確錯誤退出，不再靜默繼續後假象 ready）。
"""

import socket

import pytest

import paper_kit.presentation.app as app_module


# ── _port_available：啟動前 port 檢查 ─────────────────────


def test_port_available_true_when_free():
    assert app_module._port_available(0) is True  # port 0 = 系統分配，必可用


def test_port_available_false_when_bound():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("0.0.0.0", 0))
    port = s.getsockname()[1]
    try:
        assert app_module._port_available(port) is False
    finally:
        s.close()


# ── main() 入口：freeze_support 必須在最前 ────────────────


def _stub_main_heavy(monkeypatch, tmp_path):
    """main() 的 heavy 元件最小 stub（UI 不啟動、路徑隔離到 tmp）。"""
    monkeypatch.setattr(app_module, "APP_DIR", tmp_path)
    monkeypatch.setattr(app_module, "OUTPUTS_DIR", tmp_path / "outputs")
    monkeypatch.setattr(app_module, "GLOSSARIES_DIR", tmp_path / "glossaries")
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "pk.db")
    monkeypatch.setattr(app_module, "FILES_BASE", "/pk-test-files")
    monkeypatch.setattr(app_module.app, "add_static_files", lambda *a, **k: None)
    monkeypatch.setattr(app_module.ui, "run", lambda *a, **k: None)


def test_main_calls_freeze_support_first(monkeypatch, tmp_path):
    """macOS 遞迴修復：main() 必須呼叫 multiprocessing.freeze_support()，
    且在任何可能啟動 multiprocessing 的初始化之前（PyInstaller 官方慣例：
    入口第一行）。"""
    calls = []
    monkeypatch.setattr(
        app_module.multiprocessing, "freeze_support", lambda: calls.append("freeze")
    )
    _stub_main_heavy(monkeypatch, tmp_path)
    app_module.main()
    assert calls == ["freeze"], "freeze_support 必須在 main() 最前（macOS 遞迴修復）"


def test_main_exits_with_clear_message_when_port_busy(monkeypatch, tmp_path, capsys):
    """8080 被佔用（舊實例未關／遞迴殘留）→ 明確錯誤訊息＋exit 1，
    不得啟動 ui.run（實測 macOS 上綁定失敗後仍輸出 ready 的假象）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", app_module.DEFAULT_PORT))
        s.listen(1)
    except OSError:
        pytest.skip(f"port {app_module.DEFAULT_PORT} 本機已被佔用，無法測佔用情境")

    ran = []
    _stub_main_heavy(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.ui, "run", lambda *a, **k: ran.append("run"))
    try:
        with pytest.raises(SystemExit) as exc:
            app_module.main()
        assert exc.value.code == 1
        assert ran == [], "port 佔用時不得啟動 ui.run"
        err = capsys.readouterr().err
        assert str(app_module.DEFAULT_PORT) in err
        assert "佔用" in err
    finally:
        s.close()


# ── _uv_startup_status：啟動即顯示 uv 狀態（2026-08-15 使用者：
#    打開 exe 的 CMD 就要看到 uv 是否已裝／安裝進度）──────────


def test_uv_startup_status_logs_existing(monkeypatch, caplog):
    from paper_kit.infrastructure import uv_bootstrap as ub

    monkeypatch.setattr(ub, "installed_uv", lambda: "/fake/uv.exe")
    monkeypatch.setattr(ub, "download_uv", lambda timeout=120: None)
    assert app_module._uv_startup_status() is None, "已存在時不得啟動背景安裝"
    assert "已找到" in caplog.text, "CMD 應顯示 uv 已找到與位置"


def test_uv_startup_status_starts_install_when_missing(monkeypatch, caplog):
    from paper_kit.infrastructure import uv_bootstrap as ub

    calls: list[int] = []
    monkeypatch.setattr(ub, "installed_uv", lambda: None)
    monkeypatch.setattr(ub, "download_uv", lambda timeout=120: calls.append(1) or None)
    t = app_module._uv_startup_status()
    assert t is not None, "缺 uv 時必須啟動背景安裝"
    t.join(timeout=5)
    assert calls == [1], "背景安裝必須被執行"
    assert "自動安裝中" in caplog.text
