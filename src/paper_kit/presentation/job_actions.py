"""任務操作（重試／取消／刪除，單筆與批量）——index 與 history 共用。"""

import logging

from nicegui import ui

from paper_kit.application.errors import to_user_message
from paper_kit.application.job_service import JobService
from paper_kit.application.ports import EngineError
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.translation_job import InvalidTransition
from paper_kit.presentation.composition import sensitive_blocked

logger = logging.getLogger("paper_kit.presentation.job_actions")


def _retry_job(service: JobService, settings: SettingsService, job_id: str) -> None:
    """票 08：失敗任務重試（回 queued 再跑，不需重新上傳）。"""
    try:
        engine = settings.resolve_engine()
    except EngineError as exc:
        ui.notify(to_user_message(exc), type="negative")
        return
    try:
        engine_id = settings.engine_id()
        # 票 10：機密任務重試也用目前的引擎判定（視覺引擎 → ValueError 拒絕）。
        # 卡③：fail-closed 語意收斂 registry 單點（未知引擎視為不支援機密）
        service.retry(
            job_id, engine, engine_id=engine_id,
            engine_allows_sensitive=not sensitive_blocked(
                engine_id, True, unknown_sensitive_ok=False),
        )
        ui.notify("已重新排隊", type="positive")
    except InvalidTransition as exc:
        ui.notify(to_user_message(exc), type="negative")
    except ValueError as exc:
        ui.notify(to_user_message(exc), type="negative")  # 票 10：機密＋視覺引擎（統一入口）
    except KeyError:
        ui.notify("找不到此任務", type="negative")  # KeyError 語境由呼叫端決定（票 09 review）


def _delete_jobs(service: JobService, ids: list[str]) -> tuple[int, int]:
    """票 18：批量刪除——回傳 (成功數, 執行中被拒數)；執行中跳過不中斷其餘。

    module-level（standards review：巢狀 handler 的迴圈邏輯不可測；UI 層只
    notify＋重繪）。執行中任務維持原狀，由呼叫端提示。
    """
    deleted = blocked = 0
    for jid in ids:
        try:
            service.delete(jid)
            deleted += 1
        except ValueError:
            blocked += 1
    return deleted, blocked


def _confirm_delete_one(
    service: JobService, job_id: str, dialog, state: dict
) -> None:
    """#74：主頁卡片單一刪除——頁面級確認 dialog 的開啟（破壞性：含輸出檔）。

    #82 修復：dialog 為 `_index_page` 建置的**頁面級單例**（重複使用）。
    舊版在此 handler 內 `with ui.dialog()` 建立——NiceGUI handle_event 以
    sender 的 parent slot（＝卡片 slot，events.py）執行 handler，Dialog
    建構時的 canary 元素掛該 slot；卡片每 1s 被 _refresh 的 cards.clear()
    刪除 → canary finalize 連坐 dialog.delete()＝「刪除欄位不到 2 秒就消失」
    （使用者 3 次回報）。頁面級單例的 canary 掛 content slot（永存）不隨
    卡片死；執行中任務理論上不會出現此按鈕（view.can_delete 已擋），
    service.delete 紅線仍會兜底。
    """
    state["job_id"] = job_id
    dialog.open()


def _do_delete_one(service: JobService, job_id: str) -> None:
    """#74：單一刪除執行——重用 _delete_jobs 的 (deleted, blocked) 語義。"""
    deleted, blocked = _delete_jobs(service, [job_id])
    if blocked:
        ui.notify("執行中的任務無法刪除", type="warning")
    elif deleted:
        ui.notify("已刪除任務", type="positive")


def _batch_retry(service: JobService, settings: SettingsService, ids: list[str]) -> int:
    """票 18：批量重試——只處理可重試任務（can_retry），回傳重試數。"""
    retried = 0
    for jid in ids:
        job = next((j for j in service.list_jobs() if j.job_id == jid), None)
        if job is not None and job.can_retry:
            _retry_job(service, settings, jid)
            retried += 1
    return retried


def _batch_cancel(service: JobService, ids: list[str]) -> int:
    """票 18：批量取消——只處理可取消任務（can_cancel），回傳取消數。"""
    cancelled = 0
    for jid in ids:
        job = next((j for j in service.list_jobs() if j.job_id == jid), None)
        if job is not None and job.can_cancel:
            _cancel_job(service, jid)
            cancelled += 1
    return cancelled


def _cancel_job(service: JobService, job_id: str) -> None:
    """票 08：進行中任務取消（狀態→cancelled、產出拋棄）。"""
    try:
        service.cancel(job_id)
        ui.notify("已取消", type="warning")
    except InvalidTransition as exc:
        ui.notify(to_user_message(exc), type="negative")
    except KeyError:
        ui.notify("找不到此任務", type="negative")  # KeyError 語境由呼叫端決定（票 09 review）
