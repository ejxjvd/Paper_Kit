"""Pdf2zhNextAdapter：把 pdf2zh_next CLI 包在 TranslationEnginePort 後面。

POC 教訓（2026-08-12 實測）：
- SiliconFlow 帳號在國際站 → base-url 預設 https://api.siliconflow.com/v1（.cn 會 401）
- -next 不吃 process env → key/base-url 一律 CLI 旗標直傳
- 暫時性 50507（Unknown error）→ retry（預設 2 次）
- 引擎 hang → subprocess 逾時（預設 600s）視為失敗
- 錯誤對映：401/術語表格式 → 友善訊息，不透傳原始 traceback

票 13：translate 循環（retry/逾時/取消/redact）已抽到 CliAdapterBase 共用，
本檔只剩引擎特有的命令組裝與輸出解析。
"""

import re
from dataclasses import dataclass

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.cli_adapter_base import (
    _kill_tree as _base_kill_tree,
    CliAdapterBase,
)

DEFAULT_BASE_URL = "https://api.siliconflow.com/v1"
DEFAULT_MODEL = "google/gemma-4-31B-it"

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
        cmd += ["--glossaries", ",".join(job.glossary_files)]
        if not job.auto_extract:
            # 自動提取開啟時不禁用（與既有術語表並存，UI 兩開關可同開；票 13 統一兩插頭）
            cmd += ["--no-auto-extract-glossary"]
    if job.auto_extract:
        cmd += ["--term-siliconflow"]  # 票 05：Kimi 角色原生版自動術語提取
    return cmd


# re-export：測試 import 位置不因重構改變（_is_transient/_friendly_error 已併入基底，
# 私有且無外部引用——移除；_kill_tree 有測試直接 import）
_kill_tree = _base_kill_tree


def parse_output(output: str, job: TranslationJob) -> JobResult:
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


class Pdf2zhNextAdapter(CliAdapterBase):
    """實作 TranslationEnginePort（換插頭＝換子類＋registry 分派）。runner 可注入。"""

    # POC 教訓：SiliconFlow 上游暫時性 50507（Unknown error）→ 重試
    _transient_signatures = ("50507", "Unknown error")

    def __init__(self, config: EngineConfig, runner=None):
        super().__init__(config.retries, config.timeout_seconds, runner=runner)
        self._config = config

    def _api_key(self) -> str:
        return self._config.api_key

    def _build_command(self, job: TranslationJob) -> list[str]:
        # module 層查詢：測試 monkeypatch build_command 仍生效
        return build_command(job, self._config)

    def _parse_output(self, output: str, job: TranslationJob) -> JobResult:
        return parse_output(output, job)
