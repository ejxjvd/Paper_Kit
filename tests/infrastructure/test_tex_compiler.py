"""票 15：TeXCompiler——xelatex 編譯（xeCJK 中文支援關鍵）。

FakeRunner 注入慣例同 LibreOfficeConverter；缺 xelatex → 友善錯誤
（含 MiKTeX 安裝指引）。nonstopmode 必帶——headless 編譯不能被
錯誤中斷等輸入（配合 -halt-on-error 即停）。
"""

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.infrastructure.tex_compiler import (
    TeXCompiler,
    build_xelatex_command,
    find_xelatex,
)


def test_build_xelatex_command_has_nonstopmode_and_output_dir():
    cmd = build_xelatex_command("/usr/bin/xelatex", "paper.tex", "out")
    assert cmd[0] == "/usr/bin/xelatex"
    assert "-interaction=nonstopmode" in cmd
    assert "-halt-on-error" in cmd
    assert "-output-directory=out" in cmd
    assert cmd[-1] == "paper.tex"
    assert "--enable-installer" not in cmd  # TeX Live 不認 MiKTeX 旗標


def test_build_xelatex_command_miktex_exe_auto_installs_packages():
    """MiKTeX（.exe）加 --enable-installer：缺 xeCJK 等套件自動裝、不彈 GUI。"""
    cmd = build_xelatex_command(
        r"C:\Users\qaref\AppData\Local\Programs\MiKTeX\miktex\bin\x64\xelatex.exe",
        "paper.tex",
        "out",
    )
    assert "--enable-installer" in cmd


def test_find_xelatex_uses_path_first(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/fake/xelatex")
    assert find_xelatex() == "/fake/xelatex"


def test_find_xelatex_none_when_missing(monkeypatch):
    import shutil
    from pathlib import Path

    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "exists", lambda self: False)
    assert find_xelatex() is None


def test_compile_missing_xelatex_gives_install_guidance(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "paper_kit.infrastructure.tex_compiler.find_xelatex", lambda: None
    )
    compiler = TeXCompiler()
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}hi\\end{document}")
    with pytest.raises(EngineError, match="MiKTeX"):
        compiler.compile(tex, tmp_path / "out")


def test_compile_missing_source_gives_friendly_error(tmp_path):
    compiler = TeXCompiler()
    with pytest.raises(EngineError, match="找不到"):
        compiler.compile(tmp_path / "nope.tex", tmp_path / "out")


def test_compile_success_returns_pdf_path(tmp_path):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}\\begin{document}hi\\end{document}")
    calls: list[list[str]] = []

    def fake_runner(cmd: list[str]) -> tuple[int, str]:
        calls.append(cmd)
        (tmp_path / "out").mkdir(parents=True, exist_ok=True)
        (tmp_path / "out" / "paper.pdf").write_bytes(b"%PDF-fake")
        return 0, "compiled ok"

    compiler = TeXCompiler(xelatex="/usr/bin/xelatex", runner=fake_runner)
    pdf = compiler.compile(tex, tmp_path / "out")
    assert pdf.name == "paper.pdf"
    assert pdf.exists()
    assert "-interaction=nonstopmode" in calls[0]


def test_compile_failure_gives_friendly_error(tmp_path):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\badcmd")
    out = tmp_path / "out"
    out.mkdir()

    def fake_runner(cmd: list[str]) -> tuple[int, str]:
        return 1, "! Undefined control sequence. l.12 \\badcmd"

    compiler = TeXCompiler(xelatex="/usr/bin/xelatex", runner=fake_runner)
    with pytest.raises(EngineError, match="編譯失敗"):
        compiler.compile(tex, out)


def test_compile_timeout_gives_friendly_error(tmp_path):
    tex = tmp_path / "paper.tex"
    tex.write_text("\\documentclass{article}")
    out = tmp_path / "out"
    out.mkdir()

    def fake_runner(cmd: list[str]) -> tuple[int, str]:
        # _default_runner 的逾時合約：回傳 rc 124＋逾時說明
        return 124, "xelatex 逾時（超過 180 秒無回應）"

    compiler = TeXCompiler(xelatex="/usr/bin/xelatex", runner=fake_runner)
    with pytest.raises(EngineError, match="逾時"):
        compiler.compile(tex, out)
