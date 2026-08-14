"""uv 自動安裝（v0.1.1）測試：平台 URL 選擇、偵測鏈優先序、不重複下載、
解壓安裝、失敗給可操作錯誤。下載一律 mock（不觸網）。

背景（2026-08-14 使用者實測）：exe 首啟翻譯任務 FAILED「系統缺少 uv 工具
（引擎中介）」——Windows 側無 uv。使用者要求：「偵測並自動執行安裝，而不是
讓使用者自行安裝」→ uv_bootstrap 自動下載官方二進制到 app 專屬目錄。
"""

import io
import logging
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
    """patch sys.platform（全域——資產查表收斂後在 platform/uv_assets.py 讀
    同一 sys）＋該模組的 platform.machine（darwin 架構判定）。"""
    monkeypatch.setattr(uv_bootstrap.sys, "platform", platform)
    from paper_kit.platform import uv_assets  # 2026-08-14 平台分離：資產查表新家

    monkeypatch.setattr(uv_assets.platform, "machine", lambda: machine)


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
    (fake_home / ".local" / "bin" / ub.uv_executable_name()).touch()
    assert ub.installed_uv() == fake_home / ".local" / "bin" / ub.uv_executable_name()


def test_detect_app_dir_third(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    app_uv = fake_home / ".paper_kit" / "bin" / ub.uv_executable_name()
    app_uv.parent.mkdir(parents=True)
    app_uv.touch()
    assert ub.installed_uv() == app_uv


def test_detect_none_when_absent(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    assert ub.installed_uv() is None


# ── 已有則不重下載 ───────────────────────────────────────

def test_ensure_uv_existing_skips_download(fake_home, monkeypatch):
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    app_uv = fake_home / ".paper_kit" / "bin" / ub.uv_executable_name()
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
    """分塊可讀的假回應（read(n) 語意仿 urllib——v0.1.9.3 進度下載改分塊）。"""

    def __init__(self, payload: bytes):
        self._buf = payload

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            chunk, self._buf = self._buf, b""
            return chunk
        chunk, self._buf = self._buf[:n], self._buf[n:]
        return chunk

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
    monkeypatch.setattr(ub, "_RETRY_DELAY", 0)
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
        lambda timeout=60: str(fake_home / ".paper_kit" / "bin" / ub.uv_executable_name()),
    )
    adapter, captured = _runner_capture(monkeypatch)
    adapter.translate(_make_job())
    assert captured["cmd"][0] == str(
        fake_home / ".paper_kit" / "bin" / ub.uv_executable_name()
    )


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


# ── 多源下載（v0.1.9.3：GitHub 失敗自動 fallback PyPI／鏡像）───────────
# 背景（2026-08-15 使用者真機實測）：另一台 Windows 機器（無 uv）自動下載
# 失敗——錯誤訊息給的 `curl | sh` 在 PowerShell 無 sh（CommandNotFoundException
# 實證）。根因：下載源只有 GitHub（該網路連 GitHub 域失敗即全滅）＋手動指令
# 平台無差別。修復：GitHub → PyPI 官方 → 清華/阿里雲鏡像依序嘗試，失敗原因
# 逐源記錄；錯誤訊息帶實因＋Windows 給 winget 指令。

_PYPI_JSON = (
    '{"info": {"version": "0.12.4"},'
    '"releases": {"0.12.4": ['
    '{"filename": "uv-0.12.4-py3-none-win_amd64.whl",'
    ' "url": "https://files.pythonhosted.org/pkgs/win.whl"},'
    '{"filename": "uv-0.12.4-py3-none-macosx_11_0_arm64.whl",'
    ' "url": "https://files.pythonhosted.org/pkgs/arm.whl"},'
    '{"filename": "uv-0.12.4-py3-none-macosx_10_9_x86_64.whl",'
    ' "url": "https://files.pythonhosted.org/pkgs/x64.whl"},'
    '{"filename": "uv-0.12.4-py3-none-manylinux_2_28_x86_64.whl",'
    ' "url": "https://files.pythonhosted.org/pkgs/linux.whl"}'
    "]}}"
)

_MIRROR_HTML = (
    # 真網實測（2026-08-15）：tuna/aliyun 的 href 是相對路徑——測試用真實格式
    '<a href="../../packages/ab/uv-0.9.8-py3-none-win_amd64.whl#sha256=aa">'
    "uv-0.9.8-py3-none-win_amd64.whl</a>"
    '<a href="../../packages/cd/uv-0.9.9-py3-none-win_amd64.whl#sha256=bb">'
    "uv-0.9.9-py3-none-win_amd64.whl</a>"
)


def test_pypi_wheel_url_windows(monkeypatch):
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(ub.urllib.request, "urlopen", lambda url, timeout: FakeResponse(_PYPI_JSON.encode()))
    assert ub._pypi_wheel_url(timeout=60) == "https://files.pythonhosted.org/pkgs/win.whl"


def test_pypi_wheel_url_darwin_arm64(monkeypatch):
    _set_platform(monkeypatch, "darwin", machine="arm64")
    monkeypatch.setattr(ub.urllib.request, "urlopen", lambda url, timeout: FakeResponse(_PYPI_JSON.encode()))
    assert ub._pypi_wheel_url(timeout=60) == "https://files.pythonhosted.org/pkgs/arm.whl"


def test_pypi_wheel_url_linux(monkeypatch):
    _set_platform(monkeypatch, "linux")
    monkeypatch.setattr(ub.urllib.request, "urlopen", lambda url, timeout: FakeResponse(_PYPI_JSON.encode()))
    assert ub._pypi_wheel_url(timeout=60) == "https://files.pythonhosted.org/pkgs/linux.whl"


def test_mirror_wheel_url_takes_last_win_wheel(monkeypatch):
    """PEP 503 簡單索引舊→新排序——取最後（最新）win wheel，相對 href 經
    urljoin 解析成完整 URL、去 #sha256 碎片。"""
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(ub.urllib.request, "urlopen", lambda url, timeout: FakeResponse(_MIRROR_HTML.encode()))
    assert ub._mirror_wheel_url(ub._PYPI_MIRRORS[0], timeout=60) == (
        "https://pypi.tuna.tsinghua.edu.cn/packages/cd/uv-0.9.9-py3-none-win_amd64.whl"
    )


def test_download_falls_back_github_to_pypi(fake_home, monkeypatch):
    """GitHub 源失敗（含重試）→ 自動走 PyPI 源並成功安裝（不觸真網，mock 分派）。"""
    monkeypatch.setattr(ub, "_RETRY_DELAY", 0)
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(ub.shutil, "which", lambda _: None)
    zip_bytes = _fake_zip_archive()
    calls: list[str] = []

    def urlopen(url, timeout):
        calls.append(url)
        if "github.com" in url:
            raise OSError("GitHub 不可達")
        if "pypi.org" in url and "/json" in url:
            return FakeResponse(_PYPI_JSON.encode())
        return FakeResponse(zip_bytes)

    monkeypatch.setattr(ub.urllib.request, "urlopen", urlopen)
    installed = ub.download_uv()
    expected = fake_home / ".paper_kit" / "bin" / "uv.exe"
    assert installed == expected
    assert expected.is_file() and expected.read_bytes() == b"binary"
    assert sum("github.com" in u for u in calls) == 2, "GitHub 源失敗後應重試 1 次才 fallback"
    assert sum("files.pythonhosted.org" in u for u in calls) == 1, "PyPI wheel 應被下載"


def test_all_sources_fail_records_each_reason(fake_home, monkeypatch):
    monkeypatch.setattr(ub, "_RETRY_DELAY", 0)
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(
        ub.urllib.request,
        "urlopen",
        lambda url, timeout: (_ for _ in ()).throw(OSError("network down")),
    )
    assert ub.download_uv() is None
    reasons = ub.download_failures()
    assert len(reasons) >= 2, "GitHub＋PyPI 至少兩源失敗原因"
    assert any("github" in r for r in reasons)
    assert any("network down" in r for r in reasons)


def test_download_logs_progress_to_console(fake_home, monkeypatch, caplog):
    """安裝紀錄必須可見（2026-08-15 使用者要求：exe 的 CMD 視窗要能看到
    「是否正在安裝、進度到哪裡、實時速度、完成/失敗」——paper_kit logger
    有 console handler，訊息即入 CMD）。"""
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(ub.urllib.request, "urlopen", lambda url, timeout: FakeResponse(_fake_zip_archive()))
    with caplog.at_level(logging.INFO, logger="paper_kit.infrastructure.uv_bootstrap"):
        ub.download_uv()
    messages = [r.getMessage() for r in caplog.records]
    assert any("嘗試 1/2" in m for m in messages), "嘗試次數要在 CMD 看得到"
    assert any("下載完成" in m for m in messages), "下載完成要有 log"
    assert any("uv 自動安裝成功" in m for m in messages), "成功要有 log（CMD 看得到）"


def test_download_retries_then_succeeds(fake_home, monkeypatch, caplog):
    """失敗要自動重試（2026-08-15 使用者要求）——第 1 次失敗、重試後成功。"""
    monkeypatch.setattr(ub, "_RETRY_DELAY", 0)
    _set_platform(monkeypatch, "win32")
    calls = {"n": 0}

    def urlopen(url, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("瞬時網路失敗")
        return FakeResponse(_fake_zip_archive())

    monkeypatch.setattr(ub.urllib.request, "urlopen", urlopen)
    with caplog.at_level(logging.INFO, logger="paper_kit.infrastructure.uv_bootstrap"):
        installed = ub.download_uv()
    assert installed is not None, "重試後應成功"
    assert calls["n"] == 2, "同一源應嘗試 2 次"
    messages = [r.getMessage() for r in caplog.records]
    assert any("嘗試 2/2" in m for m in messages), "重試嘗試要有 log"


def test_download_failure_logs_all_sources(fake_home, monkeypatch, caplog):
    monkeypatch.setattr(ub, "_RETRY_DELAY", 0)
    _set_platform(monkeypatch, "win32")
    monkeypatch.setattr(
        ub.urllib.request,
        "urlopen",
        lambda url, timeout: (_ for _ in ()).throw(OSError("network down")),
    )
    with caplog.at_level(logging.INFO, logger="paper_kit.infrastructure.uv_bootstrap"):
        assert ub.download_uv() is None
    messages = [r.getMessage() for r in caplog.records]
    assert any("全源失敗" in m for m in messages), "全敗彙總要在 CMD 看得到"
    assert any("重試仍失敗" in m for m in messages), "重試失敗也要在 CMD 看得到"


def test_extract_whl_archive(fake_home, monkeypatch):
    """PyPI wheel 本質是 zip——解壓分支須支援 .whl。"""
    _set_platform(monkeypatch, "win32")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("uv.exe", b"wheel-binary")
    whl = fake_home / "uv-0.12.4-py3-none-win_amd64.whl"
    whl.write_bytes(buf.getvalue())
    dest = fake_home / "bin"
    assert ub._extract_uv(whl, dest) == dest / "uv.exe"
    assert (dest / "uv.exe").read_bytes() == b"wheel-binary"


# ── 錯誤訊息平台分支（v0.1.9.3）────────────────────────────

def _runner_error(monkeypatch, platform: str):
    _set_platform(monkeypatch, platform)
    monkeypatch.setattr("paper_kit.infrastructure.cli_adapter_base.resolve_uv", lambda timeout=60: None)
    from paper_kit.application.ports import EngineError
    from paper_kit.infrastructure.pdf2zh_next_adapter import EngineConfig, Pdf2zhNextAdapter

    adapter = Pdf2zhNextAdapter(EngineConfig(api_key="KEY"))
    with pytest.raises(EngineError) as excinfo:
        adapter.translate(_make_job())
    return str(excinfo.value)


def test_windows_error_hint_winget(monkeypatch):
    """Windows：手動指令必須 PowerShell 可執行——winget＋官方 install.ps1 雙備援
    （curl | sh 在 PowerShell 已實證 CommandNotFoundException，不得出現）。"""
    message = _runner_error(monkeypatch, "win32")
    assert "CMD" in message and "PowerShell" in message, "備援指令須註明 CMD／PowerShell 雙介面"
    assert "winget install astral-sh.uv" in message
    assert "astral.sh/uv/install.ps1" in message
    assert "curl" not in message


def test_posix_error_hint_curl(monkeypatch):
    message = _runner_error(monkeypatch, "linux")
    assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in message
