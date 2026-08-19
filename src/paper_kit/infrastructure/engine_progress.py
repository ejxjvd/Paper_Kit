"""引擎進度：從輸出行認出階段（2026-08-19）。

**為什麼是階段而不是頁數**——兩次實測定案：

1. 預設情況下，pdf2zh_next 的 rich 進度條**只在結束時印一次最終狀態**
   （180 秒的翻譯裡沒有任何一行帶遞增頁數）。rich 在非 TTY 下不做即時重繪。
2. 加上 `--report-interval 1` 後輸出**完全沒有變化**——那個旗標的進度報告不走
   stdout（應是給 GUI／API 模式的回調用）。

所以「解析 stdout 拿即時頁數」這條路是死的。**但**引擎的 INFO 行是即時到達的
（時間戳分散在整個執行期間），它們標記了處理階段。這個 module 就是把那些行
對應成階段與進度值。

誠實的限制：`Found title paragraph` 到 `Font subsetting` 之間就是實際翻譯，
那段**沒有任何訊號**（39 頁那次佔 113s／190s）。所以進度會在該階段停留很久。
UI 因此顯示階段名稱而不是假造的頁數——寧可說「正在翻譯段落」，
也不要用進度值反推出一個不存在的「第 12/39 頁」。

markers 取自 babeldoc，pdf2zh_next 與 babeldoc 兩支引擎共用。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    """一個可辨識的處理階段。"""

    marker: str      # 出現在輸出行中的子字串（比對用）
    progress: float  # 到達此階段時的進度（0.0–1.0）
    label: str       # UI 顯示的階段名稱


# 進度值取自實測時間軸（2 頁 36s／39 頁 190s 兩份樣本）。因為文件大小會改變各
# 階段的實際佔比，這些值是折衷而非精確——重點是**單調前進**且階段名稱誠實。
# 引擎永遠不發 1.0：那由任務轉入「完成」時決定。
_STAGES: tuple[Stage, ...] = (
    Stage("Using translation engine", 0.02, "啟動引擎"),
    Stage("Warmup babeldoc assets", 0.04, "準備資源"),
    Stage("Loading ONNX model", 0.07, "載入版面模型"),
    Stage("start to translate", 0.12, "解析文件"),
    # 標題段落被認出＝版面解析完成、開始逐段翻譯（最長的一段，之後無訊號）
    Stage("Found first title paragraph", 0.30, "翻譯段落"),
    Stage("Found title paragraph", 0.30, "翻譯段落"),
    Stage("Font subsetting completed", 0.85, "處理字型"),
    Stage("PDF save with clean", 0.92, "輸出 PDF"),
    Stage("finish translate", 0.97, "收尾"),
)


def parse_stage(line: str) -> Stage | None:
    """認出這一行代表的階段；不是階段行回 None。"""
    for stage in _STAGES:
        if stage.marker in line:
            return stage
    return None


class ProgressTracker:
    """把輸出行流轉成單調前進的進度。

    只在**前進**時回報：引擎會重複印同一類訊息（實測 `PDF save ... completed`
    出現兩次、`Using translation engine` 出現兩次），進度不該因此倒退或重複跳動。
    """

    def __init__(self) -> None:
        self._value = 0.0

    def feed(self, line: str) -> Stage | None:
        """吃一行輸出。有前進 → 回傳該階段；否則 None。"""
        stage = parse_stage(line)
        if stage is None or stage.progress <= self._value:
            return None
        self._value = stage.progress
        return stage

    @property
    def value(self) -> float:
        return self._value
