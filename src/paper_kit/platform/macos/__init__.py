"""macOS 版專屬（平台分離 2026-08-14）。

macOS 版行為集中於此：Finder 開啟資料夾（finder.py）、POSIX 程序樹殺
（processes.py）。與 Windows 版（platform/windows/）互不 import——分離
守則由 tests/platform/test_platform.py 強制。

Linux 開發兜底：同為 POSIX 行為，與 macOS 共用本資料夾（不另設資料夾）。
"""
