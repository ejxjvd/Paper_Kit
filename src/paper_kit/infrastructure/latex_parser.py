"""LaTeX 源碼解析（票 15）：分段＋行內指令佔位——公式 100% 原樣。

策略：LaTeX 源碼分「可譯」與「原封保留」兩類——
- 保留：環境（equation/figure/tabular...）、\\begin/\\end 行、前置指令
  （documentclass/usepackage）、註解、\\label 等
- 可譯：純文字段、標題型指令（section/caption/title...）的花括號內文
行內公式 $...$/\\\\(...\\\\) 與 \\cite/\\ref/\\eqref/\\label 抽成 \\PKP{n}
佔位符保護（LLM 不會改動），翻譯後原樣還原——AC2「公式 100% 原樣」。
"""

import re
from dataclasses import dataclass
from typing import Literal

SegmentKind = Literal["keep", "translate"]

# 標題型指令：花括號內文可譯（指令字首原封，adapter 分離）
_TITLE_COMMANDS = (
    "section", "subsection", "subsubsection", "paragraph",
    "caption", "title",
)
_TITLE_RE = re.compile(rf"^\s*\\(?:{'|'.join(_TITLE_COMMANDS)})\b")
# \author 區塊（含 \AND/\And/\thanks/\texttt 分隔結構）整段 keep——
# 真論文 e2e（2026-08-12）實測：送 LLM 會被重排（\AND 移出括號→undefined）。
_AUTHOR_RE = re.compile(r"^\s*\\author\{")
# 條列項（itemize/enumerate 內）：指令字首原封、內文可譯（spec review 補——原被
# 「\ 開頭行 keep」擋住、內容永不翻譯）
_ITEM_RE = re.compile(r"^\s*\\item\b\s*")

# 內容環境（begin/end 間整段保留）——公式/圖表等不得送翻譯。
# document 等「正文容器」不在此列（內文是可譯正文）。
_ENV_RE = re.compile(r"^\s*\\(begin|end)\{([^}]*)\}")
_KEEP_ENVS = {
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "math", "displaymath",
    "figure", "figure*", "table", "table*", "tabular", "tabular*",
    "algorithm", "algorithmic", "lstlisting", "verbatim", "tikzpicture",
    "thebibliography", "theindex", "minipage",
}

# 行內需保護的指令：公式＋引用（單一交替，依出現順序抽）。
# $$ 優先於 $（不然 $$...$$ 被拆成兩個 $...$——spec review 實測缺口）。
_INLINE_RE = re.compile(
    r"\$\$.*?\$\$"             # $$...$$ 行間公式（段落間不屬環境時）
    r"|\$[^$]*\$"              # $...$ 行內公式
    r"|\\\[.*?\\\]"            # \[...\] 行間公式
    r"|\\\(.*?\\\)"            # \(...\) 括號公式
    r"|\\cite[p]?\{[^}]*\}"    # \cite/\citep/\citet{...}
    r"|\\eqref\{[^}]*\}"       # \eqref{...}
    r"|\\ref\{[^}]*\}"         # \ref{...}
    r"|\\label\{[^}]*\}"       # \label{...}
)

_PLACEHOLDER_PREFIX = "\\PKP"


@dataclass(frozen=True)
class TexSegment:
    """源碼分段：keep = 原封保留，translate = 送翻譯（譯後回填）。"""

    kind: SegmentKind
    content: str


def split_tex_segments(source: str) -> list[TexSegment]:
    """行級分段：環境/前置指令/註解 keep；純文字合併成段 translate。

    環境狀態機：\\begin{...} 後到 \\end{...} 為止（含巢狀）一律保留——
    equation/figure 等內容行不得送翻譯（公式 100% 原樣，AC2）。
    合併連續可譯行＝一次 API 呼叫（段落上下文完整）。
    """
    segments: list[TexSegment] = []
    pending: list[str] = []
    env_depth = 0  # 環境巢狀深度
    author_depth = 0  # \author{...} 括號配對深度（>0 = 區塊內）

    def flush() -> None:
        if pending:
            segments.append(TexSegment("translate", "".join(pending)))
            pending.clear()

    for line in source.splitlines(keepends=True):
        stripped = line.lstrip()
        if author_depth == 0 and _AUTHOR_RE.match(stripped):
            # \author 區塊起點：整區塊 keep（括號配對直到閉括）——
            # \AND/\And/\thanks 等分隔結構送 LLM 會被重排（e2e 實測）
            flush()
            author_depth = stripped.count("{") - stripped.count("}")
            segments.append(TexSegment("keep", line))
            continue
        if author_depth > 0:
            # 區塊內：keep 並追蹤括號深度
            author_depth += line.count("{") - line.count("}")
            flush()
            segments.append(TexSegment("keep", line))
            continue
        env_match = _ENV_RE.match(stripped)
        if env_match:
            flush()
            env_name = env_match.group(2)
            if env_name in _KEEP_ENVS:
                # 內容環境：begin → 進入 keep 狀態；end → 離開（巢狀計數）
                env_depth += 1 if env_match.group(1) == "begin" else -1
                env_depth = max(env_depth, 0)
            segments.append(TexSegment("keep", line))
        elif env_depth > 0:
            flush()
            segments.append(TexSegment("keep", line))
        elif _TITLE_RE.match(stripped) or _ITEM_RE.match(stripped):
            # 標題/item 行獨立段：split_title/item_command 依「行」切字首/內文——
            # 與後文合併會讓 rfind("}") 錯切到行內 \cite{} 的閉括
            flush()
            segments.append(TexSegment("translate", line))
        elif _is_keep_line(stripped):
            flush()
            segments.append(TexSegment("keep", line))
        else:
            pending.append(line)
    flush()
    return segments


def _is_keep_line(stripped: str) -> bool:
    if not stripped or stripped.startswith("%"):  # 空行／註解
        return True
    if _ENV_RE.match(stripped):  # \begin{...} / \end{...}
        return True
    if _TITLE_RE.match(stripped) or _ITEM_RE.match(stripped):  # 標題/item → 可譯
        return False
    if stripped.startswith("\\"):  # 其餘指令行 → 保留
        return True
    return False  # 純文字 → 可譯


def split_title_command(line: str) -> tuple[str, str, str] | None:
    """標題型指令行 → (字首, 內文, 後綴)；非標題行回 None。

    \\section{Transformer Architecture}\\n →
    ("\\section{", "Transformer Architecture", "}\\n")——adapter 只翻內文，
    指令字首原封（票 15：標題花括號內文可譯）。
    """
    if not _TITLE_RE.match(line):
        return None
    open_idx = line.find("{")
    close_idx = line.rfind("}")
    if open_idx < 0 or close_idx <= open_idx:
        return None
    return line[: open_idx + 1], line[open_idx + 1 : close_idx], line[close_idx:]


def split_item_command(line: str) -> tuple[str, str, str] | None:
    """\\item 行 → (字首, 內文, 後綴)；非 item 行回 None。

    "\\item First point\\n" → ("\\item ", "First point", "\\n")——adapter 只翻內文，
    \\item 指令原封（票 15 spec review：條列項內容可譯）。
    """
    match = _ITEM_RE.match(line)
    if not match:
        return None
    return match.group(0), line[match.end():], ""


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_XECJK_RE = re.compile(r"\\usepackage(\[[^\]]*\])?\{xeCJK\}")
_CJK_INJECTION = (
    "% Paper_Kit: 譯文含中文——自動加入 CJK 支援（xeCJK + 中文字型）\n"
    "\\usepackage{xeCJK}\n"
    "\\setCJKmainfont{Microsoft JhengHei}\n"
)


def inject_cjk_support(tex: str) -> str:
    """組裝後源碼：含 CJK 字元且前置區無 xeCJK → 於 \\begin{document} 前注入。

    真論文 e2e 補（2026-08-12）：英文原文（無 xeCJK）翻譯注入中文後，
    xelatex 預設字型無法渲染 CJK——自動補套件＋字型（Microsoft JhengHei
    為 Windows 內建，MiKTeX 環境必定存在）。已含 xeCJK 或無中文則原樣。
    """
    if not _CJK_RE.search(tex) or _XECJK_RE.search(tex):
        return tex
    injection = _CJK_INJECTION + "\\begin{document}"
    return tex.replace("\\begin{document}", injection, 1)


def protect_tex_inline(text: str) -> tuple[str, list[str]]:
    """行內公式/引用 → \\PKP{n} 佔位符（LLM 不該改動），回傳保護後文字＋佔位清單。"""
    placeholders: list[str] = []

    def _sub(match: re.Match) -> str:
        placeholders.append(match.group(0))
        return f"{_PLACEHOLDER_PREFIX}{{{len(placeholders) - 1}}}"

    return _INLINE_RE.sub(_sub, text), placeholders


def restore_tex_inline(translated: str, placeholders: list[str]) -> str:
    """把譯文中的 \\PKP{n} 換回原文（公式/引用原樣歸位）。"""
    def _restore(match: re.Match) -> str:
        index = int(match.group(1))
        if 0 <= index < len(placeholders):
            return placeholders[index]
        return match.group(0)  # 未知佔位符原樣留（不製造損壞）

    return re.sub(rf"{re.escape(_PLACEHOLDER_PREFIX)}\s*\{{(\d+)\}}", _restore, translated)
