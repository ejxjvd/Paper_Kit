"""組合根（composition root）：presentation 唯一允許認識 infrastructure 的模組。

為什麼要有這一層（Phase 3 seam 修復，v0.3）：
`app.py` 原本直接 import 9 個 infrastructure 模組——adapter 類別、registry、repo、
探測器。這讓「簡報層」與「基礎設施」綁死：要切分 `app.py` 時，每個新模組都得
各自記得那一長串 import，漏一個就是執行期 NameError；而依賴方向也無法檢查。

現在所有 infrastructure 的認識集中在這裡（單一入口），`app.py` 與日後切出的
各頁模組只 import 這一支。守門人 `tests/presentation/test_composition_seam.py`
會掃描 `presentation/`，除本檔外出現 `paper_kit.infrastructure` 即紅燈。

注意：本模組**不得 import nicegui**——它要被純函式測試直接 import。
"""

from paper_kit.infrastructure import uv_bootstrap  # noqa: F401（app 以模組物件使用）
from paper_kit.infrastructure.app_paths import app_data_dir
from paper_kit.infrastructure.engine_registry import (
    ENGINE_SPECS,
    build_engine,
    can_select,
    resolve_key,
    sensitive_blocked,
    spec_has_key,
)
from paper_kit.infrastructure.glossary_repo import GlossaryNameError, GlossaryRepository
from paper_kit.infrastructure.job_repo import SqliteJobRepository
from paper_kit.infrastructure.latex_detector import detect_latex_dense
from paper_kit.infrastructure.llm_probe import diagnose, list_models, probe_key, probe_model
from paper_kit.infrastructure.logging_setup import (
    format_log_line,
    recent_log_entries,
    setup_logging,
)
from paper_kit.infrastructure.rapidocr_adapter import RapidOcrAdapter
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository

__all__ = [
    "ENGINE_SPECS",
    "GlossaryNameError",
    "GlossaryRepository",
    "RapidOcrAdapter",
    "SqliteJobRepository",
    "SqliteSettingsRepository",
    "app_data_dir",
    "build_engine",
    "can_select",
    "detect_latex_dense",
    "diagnose",
    "format_log_line",
    "list_models",
    "probe_key",
    "probe_model",
    "recent_log_entries",
    "resolve_key",
    "sensitive_blocked",
    "setup_logging",
    "spec_has_key",
    "uv_bootstrap",
]
