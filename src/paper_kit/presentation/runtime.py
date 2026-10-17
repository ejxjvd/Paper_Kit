"""執行期路徑常數（T-07 相位 4 自 app.py 抽出）。

頁面模組（index／settings／history／debug）與檔案操作都需要同一組路徑；
放在 app.py 會讓頁面反向 import 門面，形成循環。`app.py` 仍以同名 import
取得這些值，所以 `main()` 讀的是 app 模組的全域——測試 monkeypatch
`app.APP_DIR` 等仍然對 `main()` 生效。
"""

from paper_kit.presentation.composition import app_data_dir

APP_DIR = app_data_dir()  # 打包後 = exe 旁 data/（portable）；開發 = ~/.paper_kit
OUTPUTS_DIR = APP_DIR / "outputs"
GLOSSARIES_DIR = APP_DIR / "glossaries"
DB_PATH = APP_DIR / "paper_kit.db"
FILES_BASE = "/files"
DEFAULT_PORT = 8080
