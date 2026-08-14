"""macOS 版專屬：POSIX 程序樹殺與 spawn 參數。

killpg 殺整棵進程組（Popen start_new_session 保證組長）——uv 只是中介，
只 kill 它孫程序照跑、管道還握著（review 硬問題）。Linux 開發兜底共用
POSIX 通則。Windows 版（taskkill /T /F 遞迴）在 platform/windows/processes.py。
"""

import os
import signal


def kill_tree(proc) -> None:
    """killpg 樹殺。殺不到的（進程組已退場）直接放行。"""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def spawn_kwargs() -> dict:
    """Popen 參數：進程組長（start_new_session）——kill_tree 才殺得到整棵樹。"""
    return {"start_new_session": True}
