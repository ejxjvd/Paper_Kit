"""BabelDocAdapter：把 BabelDOC CLI（AGPL v0.6.4）包在 TranslationEnginePort 後面。

一手查證（2026-08-12）：BabelDOC 線上服務（Immersive Translate 託管 web app）
無公開程式化 API、無 API key 產品——無法以 adapter 整合。官方唯一支援的
程式化整合 = OSS CLI＋OpenAI 相容端點（README：「Currently, only OpenAI-compatible
LLM is supported」；點名 deepseek-chat）。本 adapter 即該路徑：

- 驅動 `uv tool run babeldoc`（與 pdf2zh_next 同款 uv tool run 中介）
- 後端預設 deepseek-chat @ https://api.deepseek.com/v1（README 推薦）
- translate 循環（retry/逾時/取消/redact/友善錯誤）繼承 CliAdapterBase——
  換插頭＝換子類＋registry 分派，領域與 UI 零改動
"""

import re
from dataclasses import dataclass

from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.cli_adapter_base import CliAdapterBase

DEFAULT_BABELDOC_MODEL = "deepseek-chat"  # README 推薦後端
DEFAULT_BABELDOC_BASE_URL = "https://api.deepseek.com/v1"  # OpenAI 相容端點

# babeldoc CLI 源碼實證（main.py）：logger.info 三行 token 統計
_RE_TOTAL = re.compile(r"Total tokens:\s*(\d+)")
_RE_PROMPT = re.compile(r"Prompt tokens:\s*(\d+)")
_RE_COMPLETION = re.compile(r"Completion tokens:\s*(\d+)")


@dataclass(frozen=True)
class BabelDocConfig:
    model: str = DEFAULT_BABELDOC_MODEL
    api_key: str = ""
    base_url: str = DEFAULT_BABELDOC_BASE_URL
    retries: int = 2          # 暫時性錯誤重試次數
    # #73：總牆鐘只是保險（拉高）；inactivity_seconds 判 hang（無輸出行才逾時）
    timeout_seconds: int = 3600
    inactivity_seconds: int = 300


def build_babeldoc_command(job: TranslationJob, cfg: BabelDocConfig) -> list[str]:
    """組裝 babeldoc CLI 命令（純函式，測試直接斷言旗標）。"""
    cmd = ["uv", "tool", "run", "babeldoc", "--files", job.source_path, "--openai"]
    cmd += ["--openai-model", cfg.model]
    cmd += ["--openai-base-url", cfg.base_url]
    cmd += ["--openai-api-key", cfg.api_key]
    cmd += ["--lang-out", job.target_lang]
    if job.pages:
        # babeldoc 的 only-include-translated-page 只在 --pages 時有效（CLI help 原文）
        cmd += ["--pages", job.pages, "--only-include-translated-page"]
    if job.glossary_files:
        cmd += ["--glossary-files", ",".join(job.glossary_files)]
        if not job.auto_extract:
            # 自動提取開啟時不禁用（與既有術語表並存，UI 兩開關可同開）
            cmd += ["--no-auto-extract-glossary"]
    if job.auto_extract:
        # 票 05 慣例：自動術語提取 → 同 key 的術語提取後端
        cmd += [
            "--openai-term-extraction-model", cfg.model,
            "--openai-term-extraction-base-url", cfg.base_url,
            "--openai-term-extraction-api-key", cfg.api_key,
        ]
    return cmd


def parse_output(output: str, job: TranslationJob) -> JobResult:
    total = _RE_TOTAL.search(output)
    prompt = _RE_PROMPT.search(output)
    completion = _RE_COMPLETION.search(output)
    # babeldoc CLI 不 print MonoPDF/DualPDF 行 → 檔名走源碼實證慣例
    # （result_merger.py：{basename}.{lang_out}.mono.pdf / .dual.pdf）
    stem = job.source_path.rsplit(".", 1)[0] if job.source_path else "output"
    return JobResult(
        mono_path=f"{stem}.{job.target_lang}.mono.pdf",
        dual_path=f"{stem}.{job.target_lang}.dual.pdf",
        input_tokens=int(prompt.group(1)) if prompt else 0,
        output_tokens=int(completion.group(1)) if completion else 0,
    )


class BabelDocAdapter(CliAdapterBase):
    """實作 TranslationEnginePort（第二支引擎插頭）。runner 可注入（測試 fake）。"""

    # OpenAI 相容後端共用暫時性簽名；實測到 DeepSeek 特有簽名時可覆寫（standards review）
    _transient_signatures = ("50507", "Unknown error")

    def __init__(self, config: BabelDocConfig, runner=None):
        super().__init__(
            config.retries,
            config.timeout_seconds,
            inactivity_seconds=config.inactivity_seconds,
            runner=runner,
        )
        self._config = config

    def _api_key(self) -> str:
        return self._config.api_key

    def _build_command(self, job: TranslationJob) -> list[str]:
        return build_babeldoc_command(job, self._config)

    def _parse_output(self, output: str, job: TranslationJob) -> JobResult:
        return parse_output(output, job)
