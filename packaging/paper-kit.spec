# -*- mode: python ; coding: utf-8 -*-
"""Paper_Kit 打包 spec（packaging/build.py 共用）。

v0.1.1 工程化（2026-08-14）：
- name 由 PK_VERSION 環境變數帶入 → 產物 paper-kit-<version>（build.py 透傳）
- upx 條件化：mac 不適用（UPX 不支援 mac binary）
- 入口相對路徑（SPECPATH）——repo 內可攜，不再硬編碼本機絕對路徑

隱私：本檔（與整個 repo）不得出現任何 Vault 相關字眼（公開 repo 紅線）。
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all

_PK_VERSION = os.environ.get("PK_VERSION", "0.1.1")
_NAME = f"paper-kit-{_PK_VERSION}"
_IS_MAC = sys.platform == "darwin"

datas = []
binaries = []
hiddenimports = []
for _pkg in ("nicegui", "rapidocr_onnxruntime"):
    tmp_ret = collect_all(_pkg)
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]

a = Analysis(
    [os.path.join(SPECPATH, "..", "src", "paper_kit", "presentation", "app.py")],
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
    upx=not _IS_MAC,
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
    upx=not _IS_MAC,
    upx_exclude=[],
    name=_NAME,
)
