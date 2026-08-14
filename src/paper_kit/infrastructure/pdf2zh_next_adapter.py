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
    provider: str = "siliconflow"           # "siliconflow" | "deepseek" | "siliconflowfree" | "google" | "bing" | openai 系
    model: str = DEFAULT_MODEL
    api_key: str = ""
    term_api_key: str = ""                  # #84：術語提取獨立 key（空＝沿用 api_key）
    # 2026-08-13（免費引擎誤擋修復）：build_engine 帶入 spec.needs_key——
    # 免費引擎（siliconflowfree/google/bing）false，translate 守衛放行（指令本就不含 key 旗標）
    requires_key: bool = True
    base_url: str = DEFAULT_BASE_URL        # SiliconFlow 國際站
    # v0.1.3（NIM 限制情報 2026-08-14）：免費層速率防火牆 40 RPM／並發 2-5 → 503。
    # spec.qps/spec.max_workers 帶入（nvidia 1/1）；None＝不帶旗標（引擎預設）。
    # ⚠️ CLI 契約（v0.1.4 實測教訓）：pdf2zh_next --qps 為 int（argparse type=int）——
    # float 直接 "invalid int value" 退出；qps 必須 int（節流靠 pool 1 串行）。
    qps: int | None = None
    max_workers: int | None = None
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
    elif cfg.provider == "openai":
        # 免費 LLM 接入（2026-08-13）：OpenAI 相容免費端點（Free-LLM-Collection）
        # 共用 pdf2zh 的 --openai 引擎——base-url/model/key 全由 spec 提供
        cmd += [
            "--openai",
            "--openai-model", cfg.model,
            "--openai-api-key", cfg.api_key,
            "--openai-base-url", cfg.base_url,
        ]
    else:
        # 免費引擎：旗標名＝provider（--google／--bing／--siliconflowfree），不需 key
        cmd += [f"--{cfg.provider}"]
    # v0.1.3（NIM 40 RPM／並發 2-5 限制，2026-08-14 使用者情報）：spec 內建節流——
    # --qps 1（每秒 1 請求上限）＋--pool-max-workers 1＝不併發（pdf2zh 預設併發
    # 會瞬間踩爆 40 RPM 拿 429）；實際速率由每個 LLM 請求生成時間（數秒～數十秒）
    # 自然限制，遠低於 40 RPM。其他引擎 None＝不帶、用引擎預設。
    if cfg.qps:
        cmd += ["--qps", str(cfg.qps)]
    if cfg.max_workers:
        cmd += ["--pool-max-workers", str(cfg.max_workers)]
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
        # #84：term 引擎 key 獨立化——term_api_key 設定時用獨立 key（設定頁
        # siliconflow 卡「術語提取 API key」欄）；未設定（空）沿用主 key（向後相容）。
        cmd += [
            "--term-siliconflow",
            "--term-siliconflow-model", cfg.model,
            "--term-siliconflow-api-key", cfg.term_api_key or cfg.api_key,
            "--term-siliconflow-base-url", cfg.base_url,
        ]
    return cmd


# re-export：測試 import 位置不因重構改變（_is_transient/_friendly_error 已併入基底，
# 私有且無外部引用——移除；_kill_tree 有測試直接 import）
_kill_tree = _base_kill_tree


def _diagnose_no_output(output: str) -> str:
    """#78（2026-08-14 Gemini 404 實測教訓）：pdf2zh 對上游 HTTP 錯誤吞錯
    （rc=0 靜默退出）→ 假成功。掃引擎 log 帶出真實原因，不讓使用者猜。"""
    normalized = re.sub(r"\s+", "", output)
    if re.search(r"(?i)error.{0,40}4\s?04", normalized) or "404" in normalized:
        return "上游 404：模型不存在或不支援此用法——檢查模型 ID（設定頁「載入模型清單」挑選可生成模型）"
    if re.search(r"(?i)429|toodeeprequests|ratelimit", normalized):
        return "上游 429：限流（免費額度/RPM 用完）——稍後重試或換引擎"
    if re.search(
        r"(?i)401|unauthorized|invalidkey|apikey|authenticationfailed",
        normalized,
    ):
        # authentication failed：ModelScope 跨站 key（.cn vs .ai 不互通）案例
        # ——錯誤訊息不含 401 字樣，regex 補 authentication。
        return "上游 401：API key 無效或已過期——檢查 key（ModelScope 注意站別 .cn/.ai 不互通）"
    return "上游可能失敗但回傳成功（詳見引擎 log）"


def parse_output(output: str, job: TranslationJob) -> JobResult:
    normalized = re.sub(r"\s+", "", output)
    mono = _RE_MONO.search(normalized)
    dual = _RE_DUAL.search(normalized)
    tokens = _RE_TOKENS.search(normalized)
    if mono is None and dual is None:
        # #83（2026-08-13 實測）：引擎子進程失敗（401）時 rc=0 靜默吞掉、零產出、
        # log 無任何產出宣告。舊行為靜默 fallback 慣例檔名 → ghost COMPLETED →
        # 下載 404「失敗 - 沒有檔案」。log 沒有產出宣告＝明確失敗，不得製造假路徑。
        # #78（2026-08-14）：假成功訊息帶上引擎 log 的真實 HTTP 錯誤診斷
        #（Gemini gemini-3-pro-latest 404 案例——pdf2zh 對 404 吞錯 rc=0）。
        raise EngineError(
            f"引擎未產出任何 PDF（log 無 MonoPDF/DualPDF 行）——"
            f"{_diagnose_no_output(output)}"
        )
    stem = job.source_path.rsplit(".", 1)[0] if job.source_path else "output"
    # 缺其一時 fallback 慣例檔名必須用實際 target_lang（引擎產出
    # {stem}.{lang}.mono.pdf）——舊硬編碼 .zh. 與 zh-TW 不符 → 假路徑。
    return JobResult(
        mono_path=mono.group(1) if mono else f"{stem}.{job.target_lang}.mono.pdf",
        dual_path=dual.group(1) if dual else f"{stem}.{job.target_lang}.dual.pdf",
        input_tokens=int(tokens.group(1)) if tokens else 0,
        output_tokens=int(tokens.group(2)) if tokens else 0,
    )


def preflight_openai(
    base_url: str, api_key: str, model: str, timeout: int = 10
) -> tuple[int, str]:
    """#78 假成功杜絕第三層：翻譯前預檢——POST /chat/completions（max_tokens=1
    零成本）一次驗證 key 活性＋模型可生成。GET /models 盲區（ModelScope/Gemini
    實測：清單有顯示但生成 404/401）——POST 給真答案。

    200＝可翻譯；401＝key 無效；404＝模型不存在；429＝限流；0＝連線失敗。
    """
    import json
    import urllib.error
    import urllib.request

    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions", data=payload, method="POST"
    )
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    # v0.1.7（2026-08-14 Groq 實測）：urllib 預設 UA（Python-urllib/3.x）被
    # Groq 的 Cloudflare 指紋封鎖（403 error 1010）——curl 200 但 preflight 誤擋。
    # 帶上瀏覽器式 UA 通過；同場域（OpenRouter 等）亦受惠。
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(200).decode("utf-8", "replace")
            return resp.status, body[:80]
    except urllib.error.HTTPError as e:
        body = e.read(200).decode("utf-8", "replace")
        return e.code, body[:80]
    except Exception as e:
        return 0, str(e)[:80]


def _preflight_message(code: int, body: str) -> str:
    """preflight 非 200 → 對齊 _diagnose_no_output 的診斷訊息風格。"""
    if code in (401, 403):
        return "上游 401：API key 無效或已過期——檢查設定頁 key"
    if code == 404:
        return "上游 404：模型不存在或不支援此用法——檢查模型 ID（設定頁「載入模型清單」挑選）"
    if code == 429:
        return "上游 429：限流（免費額度/RPM 用完）——稍後重試或換引擎"
    if code == 0:
        return "連線失敗：無法連到上游 API（檢查網路或 base_url 設定）"
    return f"上游 {code}：{body[:60]}"


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

    def translate(self, job: TranslationJob) -> JobResult:
        """#78（2026-08-14 實測教訓）preflight：provider=openai 且有 key 的
        引擎，翻譯前先 POST chat/completions（max_tokens=1）驗證 key＋模型
        可生成——上游錯誤（401/404/429）在啟動引擎前就攔下、帶診斷訊息。
        pdf2zh 對 HTTP 錯誤吞錯 rc=0 假成功的根因：根本不用它翻譯。"""
        if (
            self._config.provider == "openai"
            and self._config.requires_key
            and self._config.api_key
        ):
            code, body = preflight_openai(
                self._config.base_url, self._config.api_key, self._config.model
            )
            if code != 200:
                raise EngineError(_preflight_message(code, body))
        return super().translate(job)

    def _api_key(self) -> str:
        return self._config.api_key

    def _requires_key(self) -> bool:
        return self._config.requires_key

    def _build_command(self, job: TranslationJob) -> list[str]:
        # module 層查詢：測試 monkeypatch build_command 仍生效
        return build_command(job, self._config)

    def _parse_output(self, output: str, job: TranslationJob) -> JobResult:
        return parse_output(output, job)
