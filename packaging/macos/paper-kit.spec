# -*- mode: python ; coding: utf-8 -*-
"""Paper_Kit **macOS 版**打包 spec（packaging/build.py 依平台選用）。

平台分離（2026-08-14 使用者要求 macOS／Windows 各自乾淨專案）：
本檔 = macOS 版專屬（Apple Silicon arm64 主目標；Intel x86_64 亦適用）——
Windows 版（win-x64，UPX 壓縮）在 packaging/windows/paper-kit.spec。

- name 由 PK_VERSION 環境變數帶入 → 產物 paper-kit-<version>
  （build.py 透傳）
- 入口相對路徑（SPECPATH）——repo 內可攜，不再硬編碼本機絕對路徑
- upx=False：UPX 不支援 macOS binary（v0.1.1 定案）

macOS 注意（BUG_REPORT_macOS_v0.1.8，2026-08-14 修復）：
- 入口已加 multiprocessing.freeze_support()（frozen exe＋spawn → resource_tracker
  無限遞迴 117 程序——見 src/paper_kit/presentation/app.py main()）
- 打包產物未簽署（無 Developer ID）→ 使用者需繞過 Gatekeeper（右鍵開啟
  或 `xattr -dr com.apple.quarantine` 對整個資料夾遞迴移除——只移主執行檔
  不夠，內嵌 Python 帶 quarantine 時 macOS 拒絕載入 shared library）

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
    upx=False,  # macOS 版：UPX 不支援 mac binary（v0.1.1 定案）
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
    upx=False,
    upx_exclude=[],
    name=_NAME,
)
