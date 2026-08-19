"""CLI 引擎 adapter 共用骨架（票 13：換插頭重構）。

Pdf2zhNextAdapter 與 BabelDocAdapter 共用同一 translate 循環——retry 退避、
逾時樹殺、取消、key 遮罩、友善錯誤對映——只有「命令組裝」與「輸出解析」
隨引擎不同。子類實作 _build_command / _parse_output / _api_key 即完成插頭。
"""

import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from paper_kit.application.ports import EngineError, MISSING_API_KEY_MESSAGE
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
import paper_kit.infrastructure.llm_probe as llm_probe  # 卡②：探測走單點（module 訪問，patch 單點才生效）
from paper_kit.infrastructure.app_paths import app_data_dir  # v0.2.1：引擎輸出留檔位置
from paper_kit.infrastructure.logging_setup import format_error_chain, redact, redact_command
from paper_kit.infrastructure.subprocess_exec import spawn, stream  # 候選 2：機制本體
from paper_kit.infrastructure.uv_bootstrap import download_failures, resolve_uv
from paper_kit.platform import kill_tree as _platform_kill_tree  # 平台分離（2026-08-14）

# CLI 引擎專屬的環境變數（不放進 subprocess_exec——那是通用機制，不該認得 rich／tqdm）。
# #23（2026-08-13 實跑定案）：babeldoc（rich）非 TTY 輸出固定寬度折行，token 統計行
# 數字被拆到次行 → parse 誤記 out=0。COLUMNS 放大 → rich 寬 console → 單行完整。
# #76（2026-08-14 實測教訓）：PYTHONUNBUFFERED=1——pdf2zh 的 tqdm 進度在非 TTY 下
# 不 flush，輸出卡在子程序 8KB block 緩衝 → reader 讀不到任何行 → 300s inactivity
# 誤殺（使用者實測「翻譯超時」）。unbuffered 後活性信號連續。
_ENGINE_ENV = {"COLUMNS": "1000", "PYTHONUNBUFFERED": "1"}

logger = logging.getLogger("paper_kit.infrastructure.cli_adapter_base")

_KNOWN_ERRORS = [
    (("401", "Api key is invalid", "AuthenticationError"),
     "API key 無效或已過期（檢查 key 與端點：國際站用 .com）"),
    (("'source' and 'target'", "must contain"),
     "術語表 CSV 格式錯誤：標頭列必須含 source,target"),
    # v0.1.9.7（2026-08-19 使用者個人筆電實測）：Python 版本過新 → 相依套件
    # （pydantic-core）無預編譯輪子 → uv 退回原始碼編譯 → 需要 Rust 工具鏈 → 失敗。
    # 已於 build_command 釘 --python ENGINE_PYTHON 根治；此訊息是萬一再現時的路標。
    (("maturin.build_wheel", "Rust not found", "Failed to build `pydantic-core"),
     "引擎相依套件需要從原始碼編譯（該 Python 版本缺預編譯輪子）——"
     "本程式已釘定引擎 Python 版本，若仍出現請附 log 回報"),
]


def _manual_install_hint() -> str:
    """平台正確的手動安裝備援指令（v0.1.9.3：Windows 無 sh——`curl | sh`
    在 PowerShell 已實證直接 CommandNotFoundException，使用者照做必卡）。

    Windows 給兩條 PowerShell 可執行備援（內建 winget／官方 install.ps1）；
    macOS/Linux 給官方 install script（macOS 加 brew 備援）。
    """
    if sys.platform == "win32":
        return (
            "可手動安裝後重試（CMD／PowerShell 皆可執行）："
            "①`winget install astral-sh.uv`；"
            "②`powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"`；"
            "③瀏覽 https://github.com/astral-sh/uv/releases/latest 下載 "
            "uv-x86_64-pc-windows-msvc.zip，解壓後把 uv.exe 放入本程式 "
            "data\\bin 資料夾"
        )
    if sys.platform == "darwin":
        return (
            "可手動安裝後重試："
            "①`curl -LsSf https://astral.sh/uv/install.sh | sh`；"
            "②`brew install uv`；"
            "③瀏覽 https://github.com/astral-sh/uv/releases/latest 下載 "
            "uv-aarch64-apple-darwin.tar.gz（或 x86_64 版），解壓後把 uv "
            "放入本程式 data/bin 資料夾"
        )
    return (
        "可手動安裝後重試："
        "①`curl -LsSf https://astral.sh/uv/install.sh | sh`；"
        "②瀏覽 https://github.com/astral-sh/uv/releases/latest 下載 "
        "uv-x86_64-unknown-linux-gnu.tar.gz，解壓後把 uv 放入本程式 data/bin 資料夾"
    )


# v0.1.9.7（2026-08-19 使用者個人筆電實測）：多行錯誤的「最有資訊量的那一行」標記。
# uv 的解析／建置失敗是一棵樹（× 開頭、╰─▶ 分支、續行縮排），真正的原因在**開頭**，
# 而舊版取 lines[-1] 剛好拿到最沒用的續行殘片——實測使用者只看到
# 「        depends on pydantic (v2.11.10) which depends on pydantic-core」。
_ERROR_MARKERS = ("×", "╰─▶", "No solution found", "Failed to build", "error:", "ERROR:")

_ENGINE_OUTPUT_CLIP = 8000  # JSON log 單筆上限；完整內容另存 logs/engines/<job_id>.log


def _tidy(output: str) -> str:
    """剝掉 rich 的行尾填充。

    v0.2.1（2026-08-19 使用者實測 log）：COLUMNS=1000 是為了讓 rich 不折行（#23），
    代價是它把**每一行都補空白到 1000 字元**——一次 74 次呼叫的翻譯產生 247,497 字，
    九成是空白。留檔前先剝掉，體積降一個數量級。
    """
    return "\n".join(line.rstrip() for line in output.splitlines())


def _dump_engine_output(job_id: str, output: str) -> str | None:
    """完整引擎輸出另存獨立檔案，回傳路徑；失敗回 None。

    v0.2.1：先前只把截斷後的內容塞進 JSON log，而截斷是保頭保尾——**進度行剛好
    在中間被丟掉**（使用者實測：拿到頭尾卻拿不到 progress_monitor 的進度格式）。
    完整內容存檔，JSON log 只留摘要與路徑。

    留檔失敗絕不影響翻譯：診斷是附加價值，不是任務的一部分。
    """
    try:
        directory = app_data_dir() / "logs" / "engines"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{job_id}.log"
        path.write_text(output, encoding="utf-8")
        return str(path)
    except Exception:
        logger.warning("引擎輸出留檔失敗（不影響翻譯）", exc_info=True)
        return None


def _clip(output: str) -> str:
    """JSON log 內嵌用截斷——保頭也保尾（錯誤根在頭、結果行在尾）。完整內容見留檔。"""
    if len(output) <= _ENGINE_OUTPUT_CLIP:
        return output
    half = _ENGINE_OUTPUT_CLIP // 2
    return f"{output[:half]}\n…（省略 {len(output) - _ENGINE_OUTPUT_CLIP} 字，完整內容見 engine_output_file）…\n{output[-half:]}"


def _friendly_error(output: str) -> str:
    for signatures, message in _KNOWN_ERRORS:
        if any(sig in output for sig in signatures):
            return message
    lines = [l for l in output.splitlines() if l.strip()]
    if not lines:
        return "引擎執行失敗：(無輸出)"
    # 優先回報第一個帶錯誤標記的行（樹狀錯誤的根），找不到才退回最後一行
    for line in lines:
        if any(marker in line for marker in _ERROR_MARKERS):
            return f"引擎執行失敗：{line.strip()[:200]}"
    return f"引擎執行失敗：{lines[-1][-200:]}"


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
        """串流 runner：組出可執行命令 → spawn → stream。機制本體在 subprocess_exec。

        架構深化（2026-08-19，候選 2）：這裡原本內嵌整套 Popen／reader thread／
        看門狗／樹殺，且只能靠繼承取得——真正不同的兩支 adapter（latex、ppt_vision）
        因此複用不了，各自重寫。機制搬進 subprocess_exec 之後，這裡只剩兩件
        **引擎專屬**的事：把 "uv" 換成可執行的絕對路徑、傳入 rich/tqdm 需要的環境變數。

        runner 簽名刻意不變（grilling Q2）：既有 30 處 FakeRunner 測試測的是
        「命令組得對不對、輸出解析對不對」，與執行機制無關，不該因重構變紅。
        """

        def runner(cmd: list[str], timeout: int, cwd: str | None = None):
            if cmd[0] == "uv":
                # v0.1.1：uv 自動安裝（uv_bootstrap）——偵測鏈 PATH →
                # ~/.local/bin → ~/.paper_kit/bin（app 專屬自動落點）→
                # 自動下載官方二進制。使用者不需要手動裝任何東西。
                # 留在 adapter 而非執行核心（grilling Q7）：uv 是引擎家族的部署
                # 細節，不是所有子程序的共同問題——xelatex、soffice 都不經過它。
                uv = resolve_uv()
                if uv is None:
                    # v0.1.9.3：訊息帶各源失敗實因（取代「離線?」猜測——實測
                    # 機器有網但 GitHub 域不可達，猜測誤導）＋平台正確的多重
                    # 手動備援指令（Windows 給 PowerShell 可執行的）。
                    reasons = download_failures()
                    detail = "；".join(reasons) if reasons else "（無詳細資訊）"
                    raise EngineError(
                        "系統缺少 uv 工具（引擎中介）且自動下載失敗"
                        f"（各源原因：{detail}）。{_manual_install_hint()}"
                    )
                cmd = [uv, *cmd[1:]]
            handle = spawn(cmd, cwd=cwd, env_extra=_ENGINE_ENV)
            adapter._proc = handle.proc  # 票 08：cancel() 要殺得掉正在跑的子程序
            try:
                return stream(
                    handle,
                    on_line=adapter._on_line,
                    inactivity_seconds=adapter._inactivity_seconds,
                    timeout_seconds=timeout,
                )
            finally:
                adapter._proc = None

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
                # v0.1.9.7：成功也記一次完整引擎輸出（遮罩後）。翻譯以分鐘計，
                # 一個任務一筆不會洗版；而它是唯一能取得「引擎到底印了什麼」的
                # 管道——頁面級進度解析（#72 待辦）就缺這份地面真相。
                safe_output = _tidy(redact(output, [self._api_key()]))
                logger.info(
                    "引擎輸出",
                    extra={
                        "job_id": job.job_id,
                        "engine_output": _clip(safe_output),
                        "engine_output_file": _dump_engine_output(job.job_id, safe_output),
                    },
                )
                return self._parse_output(output, job)
            last_error = output
            if not self._is_transient(output):
                break
        # 票 09：失敗 log 記錯誤＋遮罩 key；toast 同樣 redact（review：不只有 log 要守）
        safe_error = _tidy(redact(last_error, [self._api_key()]))
        logger.error(
            "翻譯失敗",
            extra={
                "job_id": job.job_id,
                "error": _friendly_error(safe_error),
                # v0.1.9.7：完整輸出隨失敗一起留檔——只留 _friendly_error 那一行，
                # 實測不足以診斷（uv 多行錯誤被砍剩無意義的續行）。
                "engine_output": _clip(safe_error),
                "engine_output_file": _dump_engine_output(job.job_id, safe_error),
                "command": redact_command(cmd),
            },
        )
        raise EngineError(_friendly_error(safe_error))
