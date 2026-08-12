"""#83 下載按鈕守衛：產出檔不存在 → 不下載、改警示。

真因鏈末端（2026-08-13 實測）：引擎零產出＋假路徑 COMPLETED 時，
ui.download(缺檔路徑) → NiceGUI helpers.is_file=False → fallback from_url
→ 瀏覽器 fetch 失敗、服務端回 HTML →「失敗 - 沒有檔案」＋ .htm 檔名。
守衛：檔案不存在一律 ui.notify 警示、不觸發下載。
"""

import pytest

import paper_kit.presentation.app as app


def test_download_output_missing_file_notifies_and_skips_download(monkeypatch, tmp_path):
    """#83（紅）：ghost COMPLETED 任務的檔案在磁碟不存在 → 不下載。"""
    monkeypatch.setattr(app, "OUTPUTS_DIR", tmp_path)
    notified, downloaded = [], []

    monkeypatch.setattr(app.ui, "notify", lambda msg, **kw: notified.append((msg, kw)))
    monkeypatch.setattr(app.ui, "download", lambda p, **kw: downloaded.append(p))

    app._download_output("/files/job-x/ghost.zh-TW.mono.pdf")

    assert downloaded == [], "檔案不存在不得觸發下載"
    assert len(notified) == 1
    assert "不存在" in notified[0][0]
    assert notified[0][1].get("type") == "warning"


def test_download_output_existing_file_downloads_real_path(monkeypatch, tmp_path):
    """#83（綠側）：檔案真實存在 → 照常下載（真實磁碟路徑，非 URL）。"""
    real = tmp_path / "job-x" / "seed.zh-TW.mono.pdf"  # /files/<job_id>/<name>
    real.parent.mkdir()
    real.write_bytes(b"%PDF-1.4 ok")
    monkeypatch.setattr(app, "OUTPUTS_DIR", tmp_path)
    notified, downloaded = [], []

    monkeypatch.setattr(app.ui, "notify", lambda msg, **kw: notified.append((msg, kw)))
    monkeypatch.setattr(app.ui, "download", lambda p, **kw: downloaded.append(p))

    app._download_output("/files/job-x/seed.zh-TW.mono.pdf")

    assert downloaded == [str(real)], "存在 → ui.download(真實路徑)"
    assert notified == []
