"""#82 回饋迴圈（diagnosing-bugs Phase 1）：刪除確認 dialog 在 1s 輪詢重繪下必須存活。

使用者第 3 次回報：「刪除欄位顯示不到 2 秒就消失」。本測試以 User 框架鎖定
真實場景：主頁 cards 容器＋1s timer＋終態任務＋點 🗑 刪除 → dialog 開 →
2.5s（timer 觸發 ≥2 次 _refresh 全量重繪）→ dialog 必須仍在元素樹。

判讀：
- 本測試紅 → 機制確認（dialog 確實被某重繪機制刪除）→ 進入 Phase 2/3。
- 本測試綠 → 元素樹層面 dialog 存活，問題在視覺層／真實瀏覽器行為
  （Quasar overlay ／ socket 重連／timer 觸發時機）→ 轉 Playwright 真實瀏覽器重現。
"""

import asyncio

import pytest
from nicegui import ui
from nicegui.testing import user_simulation

from paper_kit.application.cost_service import CostService
from paper_kit.application.glossary_service import GlossaryService
from paper_kit.application.job_service import JobService
from paper_kit.application.settings_service import SettingsService
from paper_kit.domain.job_result import JobResult
from paper_kit.domain.translation_job import JobStatus, TranslationJob
from paper_kit.infrastructure.glossary_repo import GlossaryRepository
from paper_kit.infrastructure.memory_repo import InMemoryJobRepository
from paper_kit.infrastructure.settings_repo import SqliteSettingsRepository
from paper_kit.presentation.app import _index_page

_DELETE_DIALOG_TEXT = "確定刪除此任務（含輸出檔）？"


def _build(tmp_path) -> tuple[JobService, SettingsService, CostService, GlossaryService]:
    """終態任務 seed：COMPLETED ＋ result（下載按鈕出現）＋ engine_id（meta 顯示）。

    tokens 留 0 → usage_label 回 None（cost_service 184-186），卡片渲染無 IO 風險。
    """
    repo = InMemoryJobRepository()
    repo.add(
        TranslationJob(
            job_id="seed-done",
            source_path="seed.pdf",
            status=JobStatus.COMPLETED,
            engine_id="siliconflow",
            result=JobResult(mono_path="seed.zh.mono.pdf", dual_path="seed.zh.dual.pdf"),
        )
    )
    service = JobService(jobs=repo, outputs_dir=tmp_path / "outputs")
    settings = SettingsService(SqliteSettingsRepository(tmp_path / "pk.db"))
    cost = CostService(SqliteSettingsRepository(tmp_path / "pk.db"))
    glossaries = GlossaryService(GlossaryRepository(tmp_path / "glossaries"))
    return service, settings, cost, glossaries


def _dialog_elements(user) -> list:
    """抓 dialog 元素（不 raise——find 找不到會 raise，迴圈探測要 catch）。"""
    try:
        return list(user.find(kind=ui.dialog).elements)
    except AssertionError:
        return []


def _probe_dialog_anchor(dialog) -> str:
    """dialog 掛載元素身分：parent_slot 的 parent（元素）＋其 id/type/classes。

    Element.parent_slot 可能是 None（特殊元素）——也印出該狀態。
    """
    slot = getattr(dialog, "parent_slot", None)
    if slot is None:
        return "parent_slot=None（特殊元素或已無掛載 slot）"
    parent = slot.parent  # Slot.parent = 掛載元素（Element）
    return (f"{type(parent).__name__} id={str(parent.id)[:8]} "
            f"classes={getattr(parent, '_classes', None)} markers={getattr(parent, '_markers', None)} "
            f"slot_name={slot.name}")


@pytest.mark.asyncio
async def test_observe_dialog_lifecycle(tmp_path):
    """[DEBUG-82b] 觀察測試：click → dialog 出現 → 逐步監看存活與 slot 家族。

    不 assert（觀察輸出跑一次），回答：dialog 掛哪棵樹？誰刪的？
    """
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        await user.should_see("🗑 刪除", retries=20)

        layout = user._client.layout
        print(f"[DEBUG-82b] user client layout id={str(layout.id)[:8]} type={type(layout).__name__}")

        user.find("🗑 刪除").click()
        for _ in range(10):
            if _dialog_elements(user):
                break
            await asyncio.sleep(0.1)
        dialogs = _dialog_elements(user)
        print(f"[DEBUG-82b] click後 dialog 數={len(dialogs)}")
        if dialogs:
            print(f"[DEBUG-82b] dialog 掛載點: {_probe_dialog_anchor(dialogs[0])}")
            # 對照：cards 容器（w-full gap-4 的 Column）身分
            for el in layout.descendants():
                classes = getattr(el, "_classes", None) or []
                if type(el).__name__ == "Column" and any(
                    "gap-4" in c for c in classes
                ):
                    print(f"[DEBUG-82b] cards 容器: Column id={str(el.id)[:8]} "
                          f"classes={classes} slot_name={el.parent_slot.name if el.parent_slot else None}")
        # 每秒監看存活狀態（0.4s 間隔 × 7 ≈ 2.8s，涵蓋 2-3 次 timer fire）
        for i in range(7):
            await asyncio.sleep(0.4)
            n = len(_dialog_elements(user))
            all_dialogs = sum(1 for _ in layout.descendants()
                              if isinstance(_, ui.dialog))
            print(f"[DEBUG-82b] t={0.4 * (i + 1):.1f}s dialog(user.find)={n} "
                  f"dialog(layout.descendants)={all_dialogs}")


@pytest.mark.asyncio
async def test_delete_dialog_survives_refresh_cycle(tmp_path):
    """主頁 1s 輪詢下：點 🗑 刪除 → dialog 開 → 2.5s（≥2 次全量重繪）→ dialog 仍在。

    紅＝dialog 被重繪機制刪除或關閉（使用者「不到 2 秒就消失」的機制）；綠＝
    元素樹層面 dialog 存活，問題若仍在則轉真實瀏覽器層（Quasar overlay）。
    """
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        # user_simulation 的 root 在首個 request 才註冊路由——暖身兩次
        await user.open("/")
        await user.open("/")
        # 終態任務卡＋刪除按鈕出現（1s timer 刷新）
        await user.should_see("🗑 刪除", retries=20)
        # 點刪除 → 確認 dialog 開啟（元素存在＋model-value=True）
        user.find("🗑 刪除").click()
        for _ in range(5):
            if _dialog_elements(user):
                break
            await asyncio.sleep(0.1)
        assert _dialog_elements(user), "點刪除後 dialog 應開啟"
        # 內容文字鎖定（Label 是 TextElement，content 可匹配）
        await user.should_see(_DELETE_DIALOG_TEXT, retries=5)
        # 1s timer 已觸發 ≥2 次 cards.clear()＋全量重繪
        await asyncio.sleep(2.5)
        # 若 dialog 被重繪機制刪除，元素樹已無 dialog → 本行紅
        assert _dialog_elements(user), "1s 輪詢重繪 ≥2 次後 dialog 必須仍在元素樹且開啟"
        await user.should_see(_DELETE_DIALOG_TEXT, retries=5)


@pytest.mark.asyncio
async def test_delete_button_survives_refresh_cycle(tmp_path):
    """同場景：刪除按鈕本身在重繪後仍在（排除「按鈕重繪消失」機制）。"""
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        await user.should_see("🗑 刪除", retries=20)
        await asyncio.sleep(2.5)
        await user.should_see("🗑 刪除", retries=5)


@pytest.mark.asyncio
async def test_preview_dialog_survives_refresh_cycle(tmp_path):
    """#82 同機制回歸：預覽 dialog 為頁面級單例（ui.html＋iframe 取代不存在的 ui.pdf）——
    點「瀏覽器內預覽」→ iframe 注入＋dialog 開 → 2.5s 重繪 ≥2 次 → dialog 仍在且內容保留。
    """
    service, settings, cost, glossaries = _build(tmp_path)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await user.open("/")
        await user.open("/")
        await user.should_see("瀏覽器內預覽", retries=20)
        user.find("瀏覽器內預覽").click()
        for _ in range(10):
            if _dialog_elements(user):
                break
            await asyncio.sleep(0.1)
        dialogs = _dialog_elements(user)
        assert dialogs, "點預覽後 dialog 應開啟"
        # iframe 內容注入：ui.html 的 innerHTML 須含 iframe＋preview URL
        try:
            htmls = list(user.find(kind=ui.html).elements)
        except AssertionError:
            htmls = []
        injected = [h for h in htmls if "iframe" in h._props.get("innerHTML", "")]
        assert injected, "預覽 dialog 內應有注入 iframe 的 ui.html 容器"
        assert "seed.zh.mono.pdf" in injected[0]._props["innerHTML"], "iframe src 應指向 mono 預覽 URL"
        await asyncio.sleep(2.5)
        assert _dialog_elements(user), "重繪 ≥2 次後預覽 dialog 必須仍在元素樹"


# ── Phase 3 假說檢驗：誰殺 dialog？一次一變數（monkeypatch _refresh） ──

import paper_kit.presentation.app as app_mod  # noqa: E402


async def _open_with_job_card(user, service, settings, cost, glossaries) -> None:
    await user.open("/")
    await user.open("/")
    await user.should_see("🗑 刪除", retries=20)


async def _click_delete_and_wait(user) -> None:
    user.find("🗑 刪除").click()
    for _ in range(10):
        if _dialog_elements(user):
            break
        await asyncio.sleep(0.1)
    assert _dialog_elements(user), "點刪除後 dialog 應開啟"


@pytest.mark.asyncio
async def test_refresh_without_clear_keeps_dialog(tmp_path, monkeypatch):
    """實驗 A：_refresh 只重繪不清除（不呼叫 cards.clear()）→ dialog 必須活。

    死＝cards.clear() 不是唯一殺手（重繪本身也殺）；活＝clear 是必要條件。
    """
    service, settings, cost, glossaries = _build(tmp_path)

    def _no_clear_refresh(cards, svc, cost_svc, settings_svc, memo, *extra, **kwargs):
        # 原 _refresh 只刪 cards.clear() 一行；其餘照舊（重繪仍在）
        engine_labels = app_mod._engine_label_map()
        for job in svc.list_jobs():
            with cards:
                app_mod._render_card(
                    app_mod.build_job_card(job, memo.get(job.job_id), None, engine_labels),
                    svc,
                    settings_svc,
                )

    monkeypatch.setattr(app_mod, "_refresh", _no_clear_refresh)

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        await _open_with_job_card(user, service, settings, cost, glossaries)
        await _click_delete_and_wait(user)
        await asyncio.sleep(2.5)
        assert _dialog_elements(user), "不 clear 版 _refresh 下 dialog 必須存活"


@pytest.mark.asyncio
async def test_refresh_clear_without_redraw_keeps_dialog(tmp_path, monkeypatch):
    """實驗 B：_refresh 只 cards.clear() 不重繪 → dialog 必須活。

    死＝cards.clear() 本身對 layout 上的 dialog 有全域副作用（NiceGUI 層 bug）；
    活＝clear 無辜，殺手在「清除＋重繪」的組合或重繪。
    """
    service, settings, cost, glossaries = _build(tmp_path)

    def _clear_only_refresh(cards, svc, cost_svc, settings_svc, memo, *extra):
        cards.clear()

    async with user_simulation(
        root=lambda: _index_page(service, settings, cost, glossaries)
    ) as user:
        # 先以真實 _refresh 暖身：卡片＋刪除按鈕出現後才切 clear-only
        #（setup 假陰性：patch 先行 → 按鈕永不渲染 → should_see 失敗）
        await _open_with_job_card(user, service, settings, cost, glossaries)
        monkeypatch.setattr(app_mod, "_refresh", _clear_only_refresh)
        await _click_delete_and_wait(user)
        await asyncio.sleep(2.5)
        assert _dialog_elements(user), "只 clear 版 _refresh 下 dialog 必須存活"
