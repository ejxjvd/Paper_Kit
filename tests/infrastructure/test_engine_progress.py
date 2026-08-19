"""engine_progress：從真實引擎輸出行認出階段（v0.2.2，2026-08-19）。

fixture 全部取自使用者實跑的兩份 log（2 頁 36s／39 頁 190s），不是編造的。
"""

from paper_kit.infrastructure.engine_progress import ProgressTracker, parse_stage


def test_recognises_real_stage_lines():
    """真實輸出行（含 rich 的來源標記與填充）必須認得出來。"""
    line = ("[08/19/26 19:51:45] INFO INFO:babeldoc.format.pdf.high_level:"
            "start to translate: /out/paper.pdf                    high_level.py:473")
    stage = parse_stage(line)
    assert stage is not None and stage.label == "解析文件"


def test_ignores_non_stage_lines():
    assert parse_stage("INFO google translate call count: 264") is None


def test_progress_is_monotonic():
    """引擎會重複印同類訊息（實測 PDF save 出現兩次）——進度不得倒退或重跳。"""
    t = ProgressTracker()
    assert t.feed("INFO:pdf2zh_next.config.model:Using translation engine: Google") is not None
    assert t.feed("INFO:pdf2zh_next.config.model:Using translation engine: Google") is None
    assert t.feed("start to translate: /x.pdf") is not None
    assert t.feed("Using translation engine: Google") is None, "不得倒退"


def test_full_real_sequence_advances():
    """完整跑一遍實測順序，進度必須嚴格遞增且不到 1.0（1.0 由任務完成決定）。"""
    t = ProgressTracker()
    seen = []
    for line in [
        "INFO:pdf2zh_next.config.model:Using translation engine: Google",
        "INFO:pdf2zh_next.main:Warmup babeldoc assets...",
        "INFO:babeldoc.docvision.base_doclayout:Loading ONNX model...",
        "INFO:babeldoc.format.pdf.high_level:start to translate: /x.pdf",
        "INFO:...il_translator:Found first title paragraph: The entropy formula",
        "INFO:...pdf_creater:Font subsetting completed successfully",
        "INFO:...pdf_creater:PDF save with clean=True completed successfully",
        "INFO:...pdf_creater:PDF save with clean=True completed successfully",
        "INFO:babeldoc.format.pdf.high_level:finish translate: /x.pdf, cost: 25.7 s",
    ]:
        stage = t.feed(line)
        if stage:
            seen.append(stage.progress)
    assert seen == sorted(seen) and len(set(seen)) == len(seen), "必須嚴格遞增"
    assert t.value < 1.0, "引擎不得回報 100%——那由任務轉入完成時決定"
