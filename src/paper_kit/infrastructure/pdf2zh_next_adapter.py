"""Pdf2zhNextAdapter：把 pdf2zh_next CLI 包在 TranslationEnginePort 後面。

POC 教訓（2026-08-12 實測）：
- SiliconFlow 帳號在國際站 → base-url 預設 https://api.siliconflow.com/v1（.cn 會 401）
- -next 不吃 process env → key/base-url 一律 CLI 旗標直傳
- 暫時性 50507（Unknown error）→ retry（預設 2 次）
- 引擎 hang → subprocess 逾時（預設 600s）視為失敗
- 錯誤對映：401/術語表格式 → 友善訊息，不透傳原始 traceback
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from paper_kit.application.ports import EngineError, TranslationEnginePort
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob

DEFAULT_BASE_URL = "https://api.siliconflow.com/v1"
DEFAULT_MODEL = "google/gemma-4-31B-it"

_TRANSIENT_SIGNATURES = ("50507", "Unknown error")
_KNOWN_ERRORS = [
    (("401", "Api key is invalid", "AuthenticationError"),
     "API key 無效或已過期（檢查 key 與端點：國際站用 .com）"),
    (("'source' and 'target'", "must contain"),
     "術語表 CSV 格式錯誤：標頭列必須含 source,target"),
]

# babeldoc log 有欄位式折行（路徑/token 行會斷行）→ 先移除全部空白再搜
_RE_MONO = re.compile(r"MonoPDF:(.*?\.pdf)")
_RE_DUAL = re.compile(r"DualPDF:(.*?\.pdf)")
_RE_TOKENS = re.compile(
    r"TotalTokenUsage:Total\d+,Prompt(\d+),CacheHitPrompt\d+,Completion(\d+)"
)


@dataclass(frozen=True)
class EngineConfig:
    provider: str = "siliconflow"           # "siliconflow" | "deepseek"
    model: str = DEFAULT_MODEL
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL        # SiliconFlow 國際站
    retries: int = 2                        # 暫時性錯誤重試次數
    timeout_seconds: int = 600              # 引擎 hang 保護


def build_command(job: TranslationJob, cfg: EngineConfig) -> list[str]:
    """組裝 pdf2zh_next CLI 命令（純函式，測試直接斷言旗標）。"""
    cmd = ["uv", "tool", "run", "pdf2zh_next", job.source_path]
    if job.pages:
        cmd += ["--pages", job.pages]
    cmd += ["--only-include-translated-page"]
    cmd += ["--lang-out", job.target_lang]
    if cfg.provider == "deepseek":
        cmd += ["--deepseek", "--deepseek-api-key", cfg.api_key]
    elif cfg.provider == "siliconflow":
        cmd += [
            "--siliconflow",
            "--siliconflow-model", cfg.model,
            "--siliconflow-api-key", cfg.api_key,
            "--siliconflow-base-url", cfg.base_url,
        ]
    else:
        # 免費引擎：旗標名＝provider（--google／--bing／--siliconflowfree），不需 key
        cmd += [f"--{cfg.provider}"]
    if job.glossary_files:
        cmd += ["--glossaries", ",".join(job.glossary_files), "--no-auto-extract-glossary"]
    return cmd


def _is_transient(output: str) -> bool:
    return any(sig in output for sig in _TRANSIENT_SIGNATURES)


def _friendly_error(output: str) -> str:
    for signatures, message in _KNOWN_ERRORS:
        if any(sig in output for sig in signatures):
            return message
    lines = [l for l in output.splitlines() if l.strip()]
    return f"引擎執行失敗：{lines[-1][-200:] if lines else '(無輸出)'}"


def _parse_output(output: str, job: TranslationJob) -> JobResult:
    normalized = re.sub(r"\s+", "", output)
    mono = _RE_MONO.search(normalized)
    dual = _RE_DUAL.search(normalized)
    tokens = _RE_TOKENS.search(normalized)
    stem = job.source_path.rsplit(".", 1)[0] if job.source_path else "output"
    return JobResult(
        mono_path=mono.group(1) if mono else f"{stem}.zh.mono.pdf",
        dual_path=dual.group(1) if dual else f"{stem}.zh.dual.pdf",
        input_tokens=int(tokens.group(1)) if tokens else 0,
        output_tokens=int(tokens.group(2)) if tokens else 0,
    )


class Pdf2zhNextAdapter:
    """實作 TranslationEnginePort。runner 可注入（測試用 FakeRunner）。"""

    def __init__(self, config: EngineConfig, runner=None):
        self._config = config
        self._runner = runner or self._default_runner

    @staticmethod
    def _default_runner(cmd: list[str], timeout: int, cwd: str | None = None):
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return proc.returncode, proc.stdout + proc.stderr

    def translate(self, job: TranslationJob) -> JobResult:
        if not self._config.api_key:
            raise EngineError("尚未設定 API key（設定頁填入後再翻譯）")
        cmd = build_command(job, self._config)
        # babeldoc 輸出走子程序 CWD → 以任務資料夾為 cwd，產出才落在該處（票 03 實測教訓）
        cwd = str(Path(job.source_path).parent) if job.source_path else None
        last_error = ""
        for attempt in range(self._config.retries + 1):
            if attempt:
                import time

                time.sleep(2**attempt)  # 退避 2s, 4s
            try:
                rc, output = self._runner(cmd, timeout=self._config.timeout_seconds, cwd=cwd)
            except subprocess.TimeoutExpired:
                raise EngineError(
                    f"翻譯逾時（超過 {self._config.timeout_seconds} 秒無回應，上游可能掛了）"
                )
            if rc == 0:
                return _parse_output(output, job)
            last_error = output
            if not _is_transient(output):
                break
        raise EngineError(_friendly_error(last_error))
