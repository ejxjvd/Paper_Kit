"""Windows 版專屬：taskkill 程序樹殺與 spawn 參數。

macOS 版（POSIX killpg）在 platform/macos/processes.py。
"""

import subprocess


def kill_tree(proc) -> None:
    """taskkill /T /F 遞迴殺整棵樹（零依賴，psutil 未裝）。"""
    subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
        capture_output=True,
        text=True,
    )


def spawn_kwargs() -> dict:
    """Popen 參數：Windows 無進程組語意（taskkill /T 遞迴即可）。"""
    return {}
