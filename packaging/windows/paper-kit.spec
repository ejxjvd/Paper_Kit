# -*- mode: python ; coding: utf-8 -*-
"""Paper_Kit **Windows 版**打包 spec（packaging/build.py 依平台選用）。

平台分離（2026-08-14 使用者要求 macOS／Windows 各自乾淨專案）：
本檔 = Windows 版專屬（win-x64，UPX 壓縮可用）——macOS 版（arm64 主
目標，UPX 不支援 mac binary）在 packaging/macos/paper-kit.spec。

- name 由 PK_VERSION 環境變數帶入 → 產物 paper-kit-<version>.exe
  （build.py 透傳）
- 入口相對路徑（SPECPATH）——repo 內可攜，不再硬編碼本機絕對路徑

隱私紅線：本檔（與整個 repo）不得出現任何個人筆記系統相關字眼（公開 repo）。
"""
import os
from PyInstaller.utils.hooks import collect_all

_PK_VERSION = os.environ.get("PK_VERSION", "0.1.2")
_NAME = f"paper-kit-{_PK_VERSION}"

datas = []
binaries = []
hiddenimports = []
for _pkg in ("nicegui", "rapidocr_onnxruntime"):
    tmp_ret = collect_all(_pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    [os.path.join(SPECPATH, "..", "..", "src", "paper_kit", "presentation", "app.py")],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Windows 版：UPX 壓縮可用（macOS 不支援，見 macos/paper-kit.spec）
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=_NAME,
)
