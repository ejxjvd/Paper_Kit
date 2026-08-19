"""子程序執行：唯一的 spawn 點，加上兩種等待語意（架構深化候選 2，2026-08-19）。

**為什麼存在**：先前系統有兩份獨立的子程序實作——`cli_adapter_base._default_runner`
（串流、看門狗、可取消）與 `process_utils.run_command`（阻塞、capture_output）。
兩份各自決定編碼、逾時、錯誤處理，於是同一個 cp950 解碼 bug **同時住在兩邊**
（2026-08-19 使用者實測崩潰，兩處都要修）。

而且那些機制當時只能靠**繼承** `CliAdapterBase` 取得：真正同形的兩支引擎
（pdf2zh_next、babeldoc）拿得到，真正不同的兩支（latex、ppt_vision）反而複用不了，
各自重寫了 translate/cancel。機制很深，深度卻只有一種形狀的 adapter 摸得到。

**這個 module 的形狀**（grilling 定案，2026-08-19）：

- `spawn()` 是**唯一**的子程序啟動點。編碼、平台 spawn 參數在此釘死一次，
  不再散落——「怎麼安全地讀一個子程序」只有一份答案。
- 回傳 `ExecHandle`，**所有權明確交給呼叫方**：誰要取消誰就拿著它。
  不用回調把子程序藏起來，因為「誰持有這個行程」正是死鎖 bug 的溫床。
- 上面架兩種等待語意：`stream()` 逐行回報＋活性看門狗；`collect()` 跑完拿全部。
  兩者共用同一個 spawn 與解碼契約，但各自誠實——xelatex 要的是「跑完給我輸出」，
  硬套串流回調只是噪音。
- **不認得 uv**：`uv tool run` 是引擎家族的部署細節，不是所有子程序的共同問題
  （xelatex、soffice 都不經過 uv）。命令要能直接執行，由 adapter 負責。

**interface 就是測試面**：因為 spawn 是普通函式呼叫而非繼承鉤子，
`tests/infrastructure/test_subprocess_exec.py` 可以拿**真實子程序**測它。
cp950 那個 bug 會被那種測試當場抓到——舊架構下 787 個測試全綠卻完全看不見，
因為測試只能整塊替換掉 Popen。
"""

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field

from paper_kit.platform import kill_tree as _platform_kill_tree
from paper_kit.platform import spawn_kwargs

logger = logging.getLogger(__name__)

# 解碼契約（cp950 崩潰修復，2026-08-19）：兩端一起釘死才算關掉問題。
# 讀端 encoding 明確指定（不吃系統地區編碼——繁中 Windows 會挑 cp950 去解 UTF-8）；
# errors="replace" 是保險絲：壞位元組退化成 U+FFFD，不會讓 reader thread 陣亡。
# 寫端 PYTHONIOENCODING/PYTHONUTF8 叫子程序也寫 UTF-8。
_ENCODING = "utf-8"
_ERRORS = "replace"
_DECODE_ENV = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


@dataclass
class ExecHandle:
    """一個執行中的子程序。所有權在呼叫方——要取消就對它下手。

    刻意是薄的：它不管等待策略（那是 stream/collect 的事），只負責
    「這是哪個行程、怎麼殺掉它」。
    """

    proc: subprocess.Popen
    cmd: list[str] = field(default_factory=list)

    def kill_tree(self) -> None:
        """樹殺：uv／sh 只是中介，只殺它孫程序照跑、管道還握著。"""
        _platform_kill_tree(self.proc)

    def poll(self) -> int | None:
        return self.proc.poll()

    @property
    def running(self) -> bool:
        return self.proc.poll() is None


def spawn(cmd: list[str], *, cwd: str | None = None, env_extra: dict | None = None) -> ExecHandle:
    """啟動子程序並回傳 handle。stdout/stderr 合流、以 UTF-8 解碼。

    env_extra：呼叫方專屬的環境變數。**不放引擎知識在這個 module 裡**——
    例如 rich 的 COLUMNS 與 tqdm 的 PYTHONUNBUFFERED 是 CLI 引擎的需求，
    由 cli_adapter_base 傳進來；xelatex／soffice 不需要那些。
    """
    env = {**os.environ, **_DECODE_ENV, **(env_extra or {})}
    kwargs = {"cwd": cwd, "env": env}
    kwargs.update(spawn_kwargs())  # 平台分離：POSIX 進程組長（樹殺前提）；win32 無操作
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=_ENCODING,
        errors=_ERRORS,
        **kwargs,
    )
    return ExecHandle(proc=proc, cmd=list(cmd))


def stream(
    handle: ExecHandle,
    *,
    on_line=None,
    inactivity_seconds: float,
    timeout_seconds: float,
) -> tuple[int, str]:
    """逐行讀到 EOF，回傳 (rc, 全部輸出)。逾時丟 subprocess.TimeoutExpired。

    **判 hang 看活性，不看總時間**（#73，CH4 實測 58 頁 265.8s）：翻譯期間
    LLM 逐段呼叫間隔 5–20s，段落輸出行就是活性信號；死守總牆鐘會在翻譯進行到
    一半硬殺。所以 inactivity_seconds 才是主判据，timeout_seconds 只是保險。

    reader thread 的存在理由：rich 進度條佔住 pipe 時 readline 會 block，
    要有另一條 thread 才能做 inactivity 輪詢——communicate() 做不到這件事。
    """
    proc = handle.proc
    lines: list[str] = []
    last_output = [time.monotonic()]  # 共享：reader 更新、主 thread 判定

    def read() -> None:
        # 例外必須就地接住（2026-08-19 cp950 崩潰的真正卡死點）：reader 死掉時
        # 下方 `not reader.is_alive()` 會誤判成 EOF 而 break，接著 proc.wait()
        # 無限等——子程序寫滿 pipe 緩衝後阻塞在 write 永不退出，而看門狗此時
        # 已離開迴圈救不了。樹殺讓 wait() 立刻回來：吵著失敗，勝過靜默卡死。
        try:
            for line in proc.stdout:
                lines.append(line)
                last_output[0] = time.monotonic()
                if on_line is not None:
                    on_line(line)
        except Exception:
            logger.exception("讀取子程序輸出失敗——樹殺以避免 wait() 死鎖")
            handle.kill_tree()

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout_seconds
    while True:
        reader.join(0.25)
        if not reader.is_alive():
            break  # EOF：子程序關閉 stdout（正常結束或已被 kill）
        if proc.poll() is not None:
            reader.join(5.0)  # 已退出，給 reader 排空剩餘緩衝
            break
        now = time.monotonic()
        if now - last_output[0] > inactivity_seconds or now > deadline:
            handle.kill_tree()
            reader.join(2.0)
            raise subprocess.TimeoutExpired(cmd=handle.cmd, timeout=timeout_seconds)
    return proc.wait(), "".join(lines)


def collect(handle: ExecHandle, *, timeout_seconds: float) -> tuple[int, str]:
    """跑到結束，回傳 (rc, 全部輸出)。逾時樹殺後丟 subprocess.TimeoutExpired。

    給不需要活性信號的短命子程序用（xelatex、soffice、wslpath）——它們要的是
    「跑完給我輸出」，套上串流回調只是噪音。
    """
    try:
        output, _ = handle.proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        handle.kill_tree()
        handle.proc.communicate()  # 排空管道，避免留下殭屍
        raise
    return handle.proc.returncode, output or ""
