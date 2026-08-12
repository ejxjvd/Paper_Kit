"""e2e 真論文實測：展開 \\input 把多檔 .tex 合併成單一檔。

arXiv 論文常見多檔結構（主檔 \\input 各分章）。Paper_Kit 的
LatexAdapter 接受單一 .tex——合併後即可走正式管線。

規則：
- `\input{xxx}`（帶或不帶 .tex 副檔名、可含子目錄）→ 替換為檔內容；
  可在行內任何位置（`O>\input{x}<O` 也展開）
- 註解感知：每行第一個非 escape 的 `%` 之後不展開（含註解行）
- 遞迴展開（\input 內再 \input）
- 環偵測（visited 集合）
- 缺檔 → FileNotFoundError（含檔案名）
"""

import re
from pathlib import Path

_INPUT_RE = re.compile(r"\\input\{([^}]+)\}")
_COMMENT_RE = re.compile(r"(?<!\\)%")


def _resolve(tex_dir: Path, name: str) -> Path:
    if not name.endswith(".tex"):
        name += ".tex"
    return tex_dir / name


def expand_inputs(tex_dir: Path, master: str) -> str:
    """展開 master 內所有 \\input，回傳合併後全文。"""
    return _expand(tex_dir, _resolve(tex_dir, master), visited=())


def _expand(tex_dir: Path, path: Path, visited: tuple[str, ...]) -> str:
    key = str(path.relative_to(tex_dir))
    if key in visited:
        chain = " -> ".join(visited + (key,))
        raise RuntimeError(f"\\input cycle detected: {chain}")
    if not path.exists():
        raise FileNotFoundError(f"\\input 找不到檔案：{path.name}")
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        comment = _COMMENT_RE.search(line)
        code, rest = (line[: comment.start()], line[comment.start() :]) if comment else (line, "")

        def sub(m: re.Match) -> str:
            return _expand(tex_dir, _resolve(tex_dir, m.group(1)), visited + (key,))

        out.append(_INPUT_RE.sub(sub, code) + rest)
    return "".join(out)
