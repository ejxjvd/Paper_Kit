"""uv 自動安裝（v0.1.1）測試：平台 URL 選擇、偵測鏈優先序、不重複下載、
解壓安裝、失敗給可操作錯誤。下載一律 mock（不觸網）。

背景（2026-08-14 使用者實測）：exe 首啟翻譯任務 FAILED「系統缺少 uv 工具
（引擎中介）」——Windows 側無 uv。使用者要求：「偵測並自動執行安裝，而不是
讓使用者自行安裝」→ uv_bootstrap 自動下載官方二進制到 app 專屬目錄。
"""

import io
import sys
import zipfile
from pathlib import Path

import pytest

import paper_kit.infrastructure.uv_bootstrap as uv_bootstrap
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure import uv_bootstrap as ub


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """家目錄指到 tmp_path（沿用 test_pdf2zh_next_adapter 既有模式）。"""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def _set_platform(monkeypatch, platform: str, machine: str = "x86_64"):
    monkeypatch.setattr(uv_bootstrap.sys, "platform", platform)
    monkeypatch.setattr(uv_bootstrap.platform, "machine", lambda: machine)


# ── 平台 → URL（純函式）──────────────────────────────────

def test_platform_asset_windows(monkeypatch):
    _set_platform(monkeypatch, "win32")
    assert ub.platform_asset_name() == "uv-x86_64-pc-windows-msvc.zip"
    assert ub.download_url().endswith("uv-x86_64-pc-windows-msvc.zip")
    assert ub.uv_executable_name() == "uv.exe"


def test_platform_asset_darwin_arm64(monkeypatch):
    _set_platform(monkeypatch, "darwin", machine="arm64")
    assert ub.platform_asset_name() == "uv-aarch64-apple-darwin.tar.gz"
    assert ub.uv_executable_name() == "uv"


def test_platform_asset_darwin_x86_64(monkeypatch):
    _set_platform(monkeypatch, "darwin", machine="x86_64")
    assert ub.platform_asset_name() == "uv-x86_64-apple-darwin.tar.gz"


def test_platform_asset_linux(monkeypatch):
    _set_platform(monkeypatch, "linux")
    assert ub.platform_asset_name() == "uv-x86_64-unknown-linux-gnu.tar.gz"


def test_platform_asset_unknown(monkeypatch):
    _set_platform(monkeypatch, "zos")
    assert ub.platform_asset_name() is None
    assert ub.download_url() is None


# ── 偵測鏈優先序 ─────────────────────────────────────────

def test_detect_path_first(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: "/usr/bin/uv")
    assert ub.installed_uv() == Path("/usr/bin/uv")


def test_detect_home_local_bin_fallback(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    (fake_home / ".local" / "bin").mkdir(parents=True)
    (fake_home / ".local" / "bin" / "uv").touch()
    assert ub.installed_uv() == fake_home / ".local" / "bin" / "uv"


def test_detect_app_dir_third(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    app_uv = fake_home / ".paper_kit" / "bin" / "uv"
    app_uv.parent.mkdir(parents=True)
    app_uv.touch()
    assert ub.installed_uv() == app_uv


def test_detect_none_when_absent(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    assert ub.installed_uv() is None


# ── 已有則不重下載 ───────────────────────────────────────

def test_ensure_uv_existing_skips_download(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    app_uv = fake_home / ".paper_kit" / "bin" / "uv"
    app_uv.parent.mkdir(parents=True)
    app_uv.touch()
    calls = []
    monkeypatch.setattr(ub, "download_uv", lambda timeout: calls.append(timeout))
    assert ub.ensure_uv() == app_uv
    assert calls == [], "已有 uv 時不得觸發下載"


# ── 下載＋解壓安裝 ───────────────────────────────────────

def _fake_zip_archive() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("uv-x86_64-pc-windows-msvc/uv.exe", b"binary")
    return buf.getvalue()


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_download_installs_to_app_dir(fake_home, monkeypatch):
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    monkeypatch.setattr(
        ub.urllib.request, "urlopen", lambda url, timeout: FakeResponse(_fake_zip_archive())
    )
    installed = ub.download_uv()
    expected = fake_home / ".paper_kit" / "bin" / "uv.exe"
    assert installed == expected
    assert expected.is_file(), "解壓後 uv.exe 應在 app 專屬目錄"
    assert expected.read_bytes() == b"binary"


def test_download_failure_returns_none(fake_home, monkeypatch):
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(
        ub.urllib.request,
        "urlopen",
        lambda url, timeout: (_ for _ in ()).throw(OSError("network down")),
    )
    assert ub.download_uv() is None


def test_download_unsupported_platform_returns_none(fake_home, monkeypatch):
    _set_platform(monkeypatch, "zos")
    assert ub.download_uv() is None


# ── runner 整合（真實 _default_runner 層，沿用既有慣例）──

def _runner_capture(monkeypatch):
    """回傳 (adapter, captured)——FakeProc 捕捉執行的 cmd[0]。"""
    captured: dict = {}

    class FakeProc:
        returncode = 0

        def __init__(self, cmd, **kwargs):
            captured["cmd"] = cmd
            self.stdout = _LineStream("MonoPDF: out.mono.pdf DualPDF: out.dual.pdf\n")

        def poll(self):
            return 0

        def wait(self):
            return 0

    monkeypatch.setattr(
        "paper_kit.infrastructure.cli_adapter_base.subprocess.Popen", FakeProc
    )
    from paper_kit.infrastructure.pdf2zh_next_adapter import (
        EngineConfig,
        Pdf2zhNextAdapter,
    )

    return Pdf2zhNextAdapter(EngineConfig(api_key="KEY")), captured


class _LineStream:
    def __init__(self, text: str):
        self._lines = text.splitlines(keepends=True)

    def __iter__(self):
        yield from self._lines


def test_runner_uses_resolved_uv(fake_home, monkeypatch):
    """app 專屬目錄有 uv → runner 用它（不觸網、不用裸 "uv"）。"""
    monkeypatch.setattr(
        "paper_kit.infrastructure.cli_adapter_base.resolve_uv",
        lambda timeout=60: str(fake_home / ".paper_kit" / "bin" / "uv"),
    )
    adapter, captured = _runner_capture(monkeypatch)
    adapter.translate(_make_job())
    assert captured["cmd"][0] == str(fake_home / ".paper_kit" / "bin" / "uv")


def test_runner_error_when_autodownload_fails(fake_home, monkeypatch):
    """全鏈失敗（自動安裝也失敗）→ 可操作錯誤（含 uv 字樣）。"""
    monkeypatch.setattr(
        "paper_kit.infrastructure.cli_adapter_base.resolve_uv",
        lambda timeout=60: None,
    )
    from paper_kit.application.ports import EngineError
    from paper_kit.infrastructure.pdf2zh_next_adapter import (
        EngineConfig,
        Pdf2zhNextAdapter,
    )

    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))  # 真 runner
    with pytest.raises(EngineError, match="uv"):
        adapter.translate(_make_job())


def _make_job(**kw) -> TranslationJob:
    base = dict(job_id="job-1", source_path="/in/paper.pdf", target_lang="zh-TW")
    base.update(kw)
    return TranslationJob(**base)
