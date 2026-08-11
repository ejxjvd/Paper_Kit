"""JobResult 值物件：一次翻譯的產出與用量（純值，無行為）。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class JobResult:
    mono_path: str | None = None
    dual_path: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
