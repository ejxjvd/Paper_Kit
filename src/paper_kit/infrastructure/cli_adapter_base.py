"""CLI 引擎 adapter 共用骨架（票 13：換插頭重構）。

Pdf2zhNextAdapter 與 BabelDocAdapter 共用同一 translate 循環——retry 退避、
逾時樹殺、取消、key 遮罩、友善錯誤對映——只有「命令組裝」與「輸出解析」
隨引擎不同。子類實作 _build_command / _parse_output / _api_key 即完成插頭。
"""

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

from paper_kit.application.ports import EngineError, MISSING_API_KEY_MESSAGE
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.logging_setup import format_error_chain, redact, redact_command

logger = logging.getLogger("paper_kit.infrastructure.cli_adapter_base")

_KNOWN_ERRORS = [
    (("401", "Api key is invalid", "AuthenticationError"),
     "API key 無效或已過期（檢查 key 與端點：國際站用 .com）"),
    (("'source' and 'target'", "must contain"),
     "術語表 CSV 格式錯誤：標頭列必須含 source,target"),
]


def _friendly_error(output: str) -> str:
    for signatures, message in _KNOWN_ERRORS:
        if any(sig in output for sig in signatures):
            return message
    lines = [l for l in output.splitlines() if l.strip()]
    return f"引擎執行失敗：{lines[-1][-200:] if lines else '(無輸出)'}"


def _kill_tree(proc: subprocess.Popen) -> None:
    """樹殺：uv 只是中介，只 kill 它孫程序照跑、管道還握著（review 硬問題）。

    零依賴方案（psutil 未裝）：POSIX 用進程組（Popen start_new_session 保證組長），
    Windows 用 taskkill /T /F 遞迴殺整棵樹。殺不到的（已退場）直接放行。
    """
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True,
            text=True,
        )
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # 進程組已退場


class CliAdapterBase:
    """CLI 引擎 adapter 骨架。子類提供 _api_key / _build_command / _parse_output。"""

    # 暫時性錯誤簽名（重試判定；standards review：引擎特有→子類可覆寫）
    _transient_signatures: tuple[str, ...] = ()

    def __init__(self, retries: int, timeout_seconds: int, runner=None):
        self._retries = retries
        self._timeout_seconds = timeout_seconds
        self._runner = runner or self._default_runner(self)
        self._proc: subprocess.Popen | None = None  # 票 08：cancel 要殺得掉子程序
        self._cancelled = False

    # ── 子類插頭 ──────────────────────────────────────────

    def _api_key(self) -> str:
        raise NotImplementedError

    def _build_command(self, job: TranslationJob) -> list[str]:
        raise NotImplementedError

    def _parse_output(self, output: str, job: TranslationJob) -> JobResult:
        raise NotImplementedError

    def _is_transient(self, output: str) -> bool:
        return any(sig in output for sig in self._transient_signatures)

    # ── 共用骨架 ──────────────────────────────────────────

    @staticmethod
    def _default_runner(adapter: "CliAdapterBase"):
        """Popen 版 runner：子程序 handle 掛回 adapter，cancel() 才能 kill。"""

        def runner(cmd: list[str], timeout: int, cwd: str | None = None):
            kwargs = {"cwd": cwd}
            if sys.platform != "win32":
                kwargs["start_new_session"] = True  # POSIX：進程組長，_kill_tree 才殺得到整棵樹
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs
            )
            adapter._proc = proc
            try:
                out, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill_tree(proc)  # 樹殺：只 kill 中介 uv，孫程序會握住管道卡到死（review）
                proc.communicate()
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            finally:
                adapter._proc = None
            return proc.returncode, out

        return runner

    def cancel(self) -> None:
        """票 08：取消——樹殺正在跑的引擎子程序；之後的 translate 一律拒絕。"""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            _kill_tree(proc)

    def translate(self, job: TranslationJob) -> JobResult:
        if not self._api_key():
            raise EngineError(MISSING_API_KEY_MESSAGE)
        if self._cancelled:
            raise EngineError("已取消")
        cmd = self._build_command(job)
        # babeldoc 輸出走子程序 CWD → 以任務資料夾為 cwd，產出才落在該處（票 03 實測教訓）
        cwd = str(Path(job.source_path).parent) if job.source_path else None
        last_error = ""
        for attempt in range(self._retries + 1):
            if self._cancelled:
                raise EngineError("已取消")
            if attempt:
                import time

                time.sleep(2**attempt)  # 退避 2s, 4s
            try:
                rc, output = self._runner(cmd, timeout=self._timeout_seconds, cwd=cwd)
            except subprocess.TimeoutExpired as timeout_exc:
                logger.error(
                    "翻譯逾時",
                    extra={
                        "job_id": job.job_id,
                        "error_chain": format_error_chain(timeout_exc),  # 票 09 review：真實鏈
                        "command": redact_command(cmd),  # 票 09：命令含 key → 遮罩
                    },
                )
                raise EngineError(
                    f"翻譯逾時（超過 {self._timeout_seconds} 秒無回應，上游可能掛了）"
                ) from timeout_exc
            if self._cancelled:
                raise EngineError("已取消")  # 子程序被 kill 後回傳的雜訊不算數
            if rc == 0:
                return self._parse_output(output, job)
            last_error = output
            if not self._is_transient(output):
                break
        # 票 09：失敗 log 記錯誤＋遮罩 key；toast 同樣 redact（review：不只有 log 要守）
        safe_error = redact(last_error, [self._api_key()])
        logger.error(
            "翻譯失敗",
            extra={
                "job_id": job.job_id,
                "error": _friendly_error(safe_error),
                "command": redact_command(cmd),
            },
        )
        raise EngineError(_friendly_error(safe_error))
