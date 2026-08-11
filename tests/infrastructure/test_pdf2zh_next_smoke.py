"""整合 smoke（唯一標 slow）：fixture 2 頁公式 PDF → 真實 pdf2zh_next。

斷言：mono/dual 產出、公式符號原樣（√/softmax）、術語表生效（注意力機制）、
--lang-out zh-TW 繁體輸出（實測頁 3-4 必有「實現」一詞：繁體=實現、簡體=实现）。
需要 SILICONFLOW_API_KEY 環境變數，缺則 skip。
"""

import os
import subprocess
from pathlib import Path

import pytest

from paper_kit.application.ports import EngineError
from paper_kit.domain.translation_job import TranslationJob
from paper_kit.infrastructure.pdf2zh_next_adapter import EngineConfig, Pdf2zhNextAdapter

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.slow
def test_real_engine_smoke(tmp_path):
    api_key = os.environ.get("SILICONFLOW_API_KEY")
    if not api_key:
        pytest.skip("缺少 SILICONFLOW_API_KEY 環境變數")
    if subprocess.run(["uv", "--version"], capture_output=True).returncode != 0:
        pytest.skip("缺少 uv")

    job = TranslationJob(
        job_id="smoke-1",
        source_path=str(FIXTURES / "paper_p34.pdf"),
        target_lang="zh-TW",
        glossary_files=[str(FIXTURES / "glossary.csv")],
    )
    adapter = Pdf2zhNextAdapter(EngineConfig(api_key=api_key))
    result = adapter.translate(job)

    assert result.mono_path and result.dual_path, "mono/dual 都要產出"
    for p in (result.mono_path, result.dual_path):
        assert Path(p).exists(), f"產出檔不存在: {p}"

    # 抽樣文字：公式原樣＋術語表＋繁體
    from pypdf import PdfReader

    text = "".join(pg.extract_text() for pg in PdfReader(result.mono_path).pages)
    assert "√" in text, "公式根號原樣"
    assert "softmax" in text, "公式函式原樣"
    assert "注意力機制" in text, "術語表生效"
    assert "實現" in text and "实现" not in text, "--lang-out zh-TW 應輸出繁體"
    assert result.input_tokens > 0, "應回報實際 token 用量"
