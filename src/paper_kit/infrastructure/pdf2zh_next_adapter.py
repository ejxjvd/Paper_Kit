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

from paper_kit.application.ports import EngineError
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
    # #73（CH4 真因）：總牆鐘只是保險（拉高，不再當主判据）；inactivity_seconds
    # 才是「判 hang」——最後一行輸出超過此秒數無新行才逾時（翻譯中有段落行=續命）。
    timeout_seconds: int = 3600
    inactivity_seconds: int = 300           # 段落活性信號間隔 5–20s；300s 有餘裕


def build_command(job: TranslationJob, cfg: EngineConfig) -> list[str]:
    """組裝 pdf2zh_next CLI 命令（純函式，測試直接斷言旗標）。"""
    cmd = ["uv", "tool", "run", "pdf2zh_next", job.source_path]
    if job.pages:
        cmd += ["--pages", job.pages]
    if job.only_selected_pages:
        # #85：「僅選中頁面」toggle——OFF＝不送（引擎預設輸出全部頁面、未選頁原樣保留）；
        # 引擎無反向 only-include flag，語義＝只翻譯選中頁面 vs 全文都過引擎
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
    if job.auto_extract and cfg.provider == "siliconflow":
        # 票 05：Kimi 角色原生版自動術語提取。Bug 1（2026-08-13）：term 引擎是獨立
        # settings 模型，驗證只檢查自身的 api_key → 缺 --term-siliconflow-api-key 會
        # 丟「SiliconFlow API key is required」；model/base-url 一併對齊主引擎。
        # #83（2026-08-13）：term 引擎＝SiliconFlow，deepseek provider 送 term 旗標
        # = 把 deepseek key 給 SiliconFlow → 401 → rc=0 零產出 → ghost COMPLETED →
        # 下載「失敗 - 沒有檔案」。引擎源碼實證：無 --term-* 旗標時
        # term_extraction_engine_settings=None → get_term_translator=None → 提取
        # 整個跳過（不需 key、不呼叫、不上雲）。敏感任務（sensitive_ok 只有
        # deepseek，票 10 紅線）因此同時守護：機密內容不上 SiliconFlow 雲端。
        # term 引擎 key 獨立化（EngineConfig.term_api_key）留待 #84/#85。
        cmd += [
            "--term-siliconflow",
            "--term-siliconflow-model", cfg.model,
            "--term-siliconflow-api-key", cfg.api_key,
            "--term-siliconflow-base-url", cfg.base_url,
        ]
    return cmd


# re-export：測試 import 位置不因重構改變（_is_transient/_friendly_error 已併入基底，
# 私有且無外部引用——移除；_kill_tree 有測試直接 import）
_kill_tree = _base_kill_tree


def parse_output(output: str, job: TranslationJob) -> JobResult:
    normalized = re.sub(r"\s+", "", output)
    mono = _RE_MONO.search(normalized)
    dual = _RE_DUAL.search(normalized)
    tokens = _RE_TOKENS.search(normalized)
    if mono is None and dual is None:
        # #83（2026-08-13 實測）：引擎子進程失敗（401）時 rc=0 靜默吞掉、零產出、
        # log 無任何產出宣告。舊行為靜默 fallback 慣例檔名 → ghost COMPLETED →
        # 下載 404「失敗 - 沒有檔案」。log 沒有產出宣告＝明確失敗，不得製造假路徑。
        raise EngineError(
            "引擎未產出任何 PDF（log 無 MonoPDF/DualPDF 行）——上游可能失敗但回傳成功"
        )
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
        # module 層查詢：測試 monkeypatch build_command 仍生效
        return build_command(job, self._config)

    def _parse_output(self, output: str, job: TranslationJob) -> JobResult:
        return parse_output(output, job)
