"""Windows 版專屬（平台分離 2026-08-14）。

Windows 版行為集中於此：explorer 開啟資料夾＋WSL 路徑正規化（explorer.py）、
taskkill 程序樹殺（processes.py）。與 macOS 版（platform/macos/）互不
import——分離守則由 tests/platform/test_platform.py 強制。
"""
