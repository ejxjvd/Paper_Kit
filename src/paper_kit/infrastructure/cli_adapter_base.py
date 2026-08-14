"""CLI 引擎 adapter 共用骨架（票 13：換插頭重構）。

Pdf2zhNextAdapter 與 BabelDocAdapter 共用同一 translate 循環——retry 退避、
逾時樹殺、取消、key 遮罩、友善錯誤對映——只有「命令組裝」與「輸出解析」
隨引擎不同。子類實作 _build_command / _parse_output / _api_key 即完成插頭。
"""

import logging
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from paper_kit.application.ports import EngineError, MISSING_API_KEY_MESSAGE
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
import paper_kit.infrastructure.llm_probe as llm_probe  # 卡②：探測走單點（module 訪問，patch 單點才生效）
from paper_kit.infrastructure.logging_setup import format_error_chain, redact, redact_command
from paper_kit.infrastructure.uv_bootstrap import resolve_uv
from paper_kit.platform import kill_tree as _platform_kill_tree  # 平台分離（2026-08-14）
from paper_kit.platform import spawn_kwargs  # POSIX 進程組長／win32 無操作

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

    平台分離（2026-08-14）：實作收斂於 paper_kit.platform.kill_tree——
    Windows 版 = taskkill /T /F 遞迴（platform/windows/processes.py）、
    macOS/Linux 版 = killpg 進程組（platform/macos/processes.py）；已退場
    （poll 非 None）的守衛在 dispatch 層。本函式保留命名相容薄轉發
    （測試/呼叫方沿用舊名）。
    """
    _platform_kill_tree(proc)


class CliAdapterBase:
    """CLI 引擎 adapter 骨架。子類提供 _api_key / _build_command / _parse_output。"""

    # 暫時性錯誤簽名（重試判定；standards review：引擎特有→子類可覆寫）
    _transient_signatures: tuple[str, ...] = ()

    def __init__(
        self,
        retries: int,
        timeout_seconds: int,
        inactivity_seconds: int | None = None,
        runner=None,
    ):
        self._retries = retries
        self._timeout_seconds = timeout_seconds
        # #73：無輸出行判定（CH4 真因——死守總牆鐘硬殺正在逐段翻譯的引擎）。
        # None → 退到總牆鐘（保守：只靠總 cap）。
        self._inactivity_seconds = (
            inactivity_seconds if inactivity_seconds is not None else timeout_seconds
        )
        self._runner = runner or self._default_runner(self)
        self._proc: subprocess.Popen | None = None  # 票 08：cancel 要殺得掉子程序
        self._cancelled = False
        self._on_progress: "Callable[[float], None] | None" = None  # 票 25：#72 進度回調

    # ── 子類插頭 ──────────────────────────────────────────

    def _api_key(self) -> str:
        raise NotImplementedError

    def _requires_key(self) -> bool:
        """此引擎需要 API key 嗎？（2026-08-13：免費引擎覆寫為 False——否則
        translate 守衛把 siliconflowfree/google/bing 全擋成「尚未設定 API key」。）"""
        return True

    def _build_command(self, job: TranslationJob) -> list[str]:
        raise NotImplementedError

    def _parse_output(self, output: str, job: TranslationJob) -> JobResult:
        raise NotImplementedError

    def _is_transient(self, output: str) -> bool:
        return any(sig in output for sig in self._transient_signatures)

    def _preflight(self, job: TranslationJob) -> None:
        """翻譯前預檢鉤子（卡②，2026-08-14 架構健檢）。

        #78 假成功防禦：OpenAI 相容引擎覆寫——翻譯前先 POST chat/completions
        （max_tokens=1）驗證 key＋模型可生成，上游錯誤（401/404/429）在引擎
        啟動前攔下。pdf2zh/babeldoc 對上游 HTTP 錯誤吞錯 rc=0 假成功的根因：
        根本不用它翻譯。預設 no-op（latex/ppt/rapidocr 非 LLM 引擎）。
        """

    def _preflight_openai(self, base_url: str, api_key: str, model: str) -> None:
        """OpenAI 相容端點共用預檢（卡②）：probe_model 非 200 → EngineError。

        診斷文案單點（llm_probe.diagnose）——Pdf2zhNextAdapter 與 BabelDocAdapter
        共用同一防禦；修一次兩支引擎（含未來 OpenAI 相容新引擎）自動獲得。
        """
        code, body = llm_probe.probe_model(base_url, api_key, model)
        if code != 200:
            raise EngineError(
                llm_probe.diagnose(code, body)
                if code == 0
                else f"上游 {code}：{llm_probe.diagnose(code, body)}"
            )

    def _on_line(self, line: str) -> None:
        """流式 runner 每行輸出回調（子類覆寫以解析進度）。基線 no-op。

        #73 實測：pdf2zh_next 的 rich progress bar 用 \\r 覆寫、readline 讀不到
        \n 行；可解析的只有段落 warning 行（`paragraph id: X`，無總數）→
        無可靠百分比 → 不發確定進度（UI 以 indeterminate 呈現）。引擎支援
        overall_progress 時在此解析並 _emit_progress。
        """

    def set_progress_callback(self, callback: "Callable[[float], None] | None" = None) -> None:
        """#72：job_service 注入進度回調（0.0–1.0）。None＝清除。"""
        self._on_progress = callback

    def _emit_progress(self, value: float) -> None:
        if self._on_progress is not None:
            self._on_progress(value)

    # ── 共用骨架 ──────────────────────────────────────────

    @staticmethod
    def _default_runner(adapter: "CliAdapterBase"):
        """Popen 版 runner（#73 流式）：子程序 handle 掛回 adapter，cancel() 才能 kill。

        舊版 `proc.communicate(timeout=600)` 是總牆鐘——CH4 實測（58 頁，265.8s
        完成）證明：SiliconFlow 逐段 API 呼叫間隔 5–20s，翻譯中「段落 warning 行」
        就是活性信號；死守總牆鐘會在翻譯進行到一半硬殺（真實 FAILED 案例）。
        新版改以 **inactivity deadline** 判 hang：最後一行的時間超過
        inactivity_seconds 才逾時；有輸出行就續命。總牆鐘只剩保險（拉高）。
        """

        def runner(cmd: list[str], timeout: int, cwd: str | None = None):
            if cmd[0] == "uv":
                # v0.1.1：uv 自動安裝（uv_bootstrap）——偵測鏈 PATH →
                # ~/.local/bin → ~/.paper_kit/bin（app 專屬自動落點）→
                # 自動下載官方二進制。取代舊「which＋home fallback」兩層：
                # 使用者不需要手動裝任何東西（2026-08-14 使用者要求）。
                # 全鏈失敗才給可操作訊息（含手動安裝指令），不是裸 Errno。
                uv = resolve_uv()
                if uv is None:
                    raise EngineError(
                        "系統缺少 uv 工具（引擎中介）且自動下載失敗（離線？）。"
                        "可手動執行 `curl -LsSf https://astral.sh/uv/install.sh | sh` "
                        "安裝後重試"
                    )
                cmd = [uv, *cmd[1:]]
            kwargs = {"cwd": cwd}
            # #23（2026-08-13 實跑定案）：babeldoc（rich）非 TTY 輸出固定寬度折行，
            # token 統計行數字被拆到次行 → parse 誤記 out=0。COLUMNS 放大 → rich 寬
            # console → token 行單行完整（實測 COLUMNS=1000 三行皆單行）。共用骨架
            # 統一設——pdf2zh_next 同為 rich 輸出，一併受益；對非 rich 引擎無害。
            # #76（2026-08-14 實測教訓）：PYTHONUNBUFFERED=1——pdf2zh 的 tqdm 進度
            # 在非 TTY 下**不 flush**（tqdm flush=False 預設），輸出卡在子程序 8KB
            # block 緩衝，NIM 120B 慢模型翻譯期間緩衝不滿 → reader 讀不到任何行 →
            # 300s inactivity 誤殺（使用者實測「翻譯超時」）。unbuffered 後每步
            # 即時輸出，活性信號連續（所有引擎受益）。
            kwargs["env"] = {**os.environ, "COLUMNS": "1000", "PYTHONUNBUFFERED": "1"}
            kwargs.update(spawn_kwargs())  # 平台分離：POSIX 進程組長（樹殺前提）；win32 無操作
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **kwargs
            )
            adapter._proc = proc
            lines: list[str] = []
            # reader thread 讀 stdout（rich bar 佔住 pipe 時 readline 會 block，
            # 主 thread 才能做 inactivity 輪詢——communicate 做不到的關鍵）。
            last_output = [time.monotonic()]  # 共享：reader thread 更新、主 thread 判定

            def read() -> None:
                for line in proc.stdout:
                    lines.append(line)
                    last_output[0] = time.monotonic()
                    if adapter._on_line is not None:
                        adapter._on_line(line)

            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            deadline = time.monotonic() + timeout
            try:
                while True:
                    reader.join(0.25)
                    if not reader.is_alive():
                        break  # EOF：子程序關閉 stdout（正常結束或已被 kill）
                    if proc.poll() is not None:
                        reader.join(5.0)  # 已退出，給 reader 排空剩餘緩衝
                        break
                    now = time.monotonic()
                    if now - last_output[0] > adapter._inactivity_seconds:
                        _kill_tree(proc)
                        reader.join(2.0)
                        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
                    if now > deadline:
                        _kill_tree(proc)
                        reader.join(2.0)
                        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            finally:
                adapter._proc = None
            rc = proc.wait()
            return rc, "".join(lines)

        return runner

    def cancel(self) -> None:
        """票 08：取消——樹殺正在跑的引擎子程序；之後的 translate 一律拒絕。"""
        self._cancelled = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            _kill_tree(proc)

    def translate(self, job: TranslationJob) -> JobResult:
        if self._requires_key() and not self._api_key():
            raise EngineError(MISSING_API_KEY_MESSAGE)
        if self._cancelled:
            raise EngineError("已取消")
        self._preflight(job)  # 卡②：openai 系在引擎啟動前驗證 key＋模型（預設 no-op）
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
                # #83 安全：error_chain 內嵌 exc.cmd（含明文 --*-api-key）——
                # 只遮 command 欄位不夠，error_chain 也要 redact（實測 log 曾寫入
                # 明文 SF key）。command 欄位維持 redact_command（結構遮罩）。
                logger.error(
                    "翻譯逾時",
                    extra={
                        "job_id": job.job_id,
                        "error_chain": redact(format_error_chain(timeout_exc), [self._api_key()]),
                        "command": redact_command(cmd),  # 票 09：命令含 key → 遮罩
                    },
                )
                raise EngineError(
                    # #73：逾時主因＝無輸出行（inactivity），不是總牆鐘
                    f"翻譯逾時（超過 {self._inactivity_seconds} 秒無輸出行，上游可能掛了）"
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
