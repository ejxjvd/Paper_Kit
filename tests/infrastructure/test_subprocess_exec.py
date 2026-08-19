"""subprocess_exec：**打真實子程序**的測試（架構深化候選 2，2026-08-19）。

這個檔案的存在本身就是重構的理由。舊架構下，子程序機制只能靠繼承
CliAdapterBase 取得，測試唯一的介入點是整塊替換掉 Popen（FakeProc 直接
yield str）——**解碼層從未被執行過**，於是 787 個測試全綠，卻對 cp950
崩潰完全盲目（2026-08-19 使用者實測整個產品在繁中 Windows 上不能用）。

機制成為可直接呼叫的 module 之後，就能拿真的子程序測它。下面第一個測試
若在修復前執行，會在繁中 Windows 上直接重現那個 UnicodeDecodeError。
"""

import subprocess
import sys
import time

import pytest

from paper_kit.infrastructure.subprocess_exec import collect, spawn, stream


def _py(code: str) -> list[str]:
    """跑一段 Python 的子程序命令（-u：不緩衝，串流測試才看得到即時輸出）。"""
    return [sys.executable, "-u", "-c", code]


def test_non_ascii_utf8_output_decodes(tmp_path):
    """cp950 迴歸（機制層）：子程序輸出非 ASCII 的 UTF-8，必須正確解碼。

    繁中 Windows 的系統地區編碼是 cp950；不指定 encoding 就會拿 cp950 去解
    UTF-8，讀到 0xC3 前導位元組即 UnicodeDecodeError。這裡刻意輸出 É
    （UTF-8 = C3 89，而 0x89 不在 Big5 合法後續範圍內）——正是使用者實測崩潰的形狀。
    """
    handle = spawn(_py(r"import sys; sys.stdout.buffer.write('  École\n'.encode('utf-8'))"))
    rc, output = collect(handle, timeout_seconds=30)
    assert rc == 0
    assert "École" in output, f"非 ASCII 解碼失敗，實得：{output!r}"


def test_invalid_bytes_do_not_raise():
    """保險絲：即使真的混進非 UTF-8 位元組，也只能退化成 U+FFFD，不得拋例外。

    舊架構下這種例外會殺死 reader thread，主迴圈誤判成 EOF，proc.wait()
    無限等 → 任務靜默卡死（比解碼錯誤本身嚴重）。
    """
    handle = spawn(_py(r"import sys; sys.stdout.buffer.write(b'ok \xff\xfe\x80 end\n')"))
    rc, output = collect(handle, timeout_seconds=30)
    assert rc == 0
    assert "ok" in output and "end" in output
    assert "�" in output, "壞位元組應退化成 U+FFFD"


def test_stream_reports_each_line():
    """串流語意：每一行都要即時回報（活性信號的基礎）。"""
    seen: list[str] = []
    handle = spawn(_py(r"[print(f'line {i}') for i in range(3)]"))
    rc, output = stream(
        handle, on_line=seen.append, inactivity_seconds=30, timeout_seconds=30
    )
    assert rc == 0
    assert [l.strip() for l in seen] == ["line 0", "line 1", "line 2"]
    assert output.count("line") == 3


def test_stream_kills_on_inactivity():
    """判 hang 看活性：長時間沒有輸出行就樹殺並逾時。

    子程序刻意先印一行再沉默——證明「有輸出過」不會讓它免疫，
    看的是**最後一行到現在**多久。
    """
    handle = spawn(_py(r"import time; print('started'); time.sleep(30)"))
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        stream(handle, on_line=None, inactivity_seconds=0.5, timeout_seconds=30)
    assert time.monotonic() - started < 15, "應在 inactivity 逾時後立刻收手"
    assert not handle.running, "逾時必須樹殺子程序，不得留下孤兒"


def test_stream_survives_output_after_exit():
    """子程序退出後，reader 仍要排空剩餘緩衝——否則最後幾行（含結果行）會遺失。"""
    handle = spawn(_py(r"[print(f'tail {i}') for i in range(50)]"))
    rc, output = stream(
        handle, on_line=None, inactivity_seconds=30, timeout_seconds=30
    )
    assert rc == 0
    assert "tail 49" in output, "尾端輸出不得遺失（結果行通常在最後）"


def test_collect_returns_exit_code():
    """阻塞語意：非零結束碼要如實回報（呼叫方靠它走錯誤路徑）。"""
    handle = spawn(_py(r"import sys; print('boom'); sys.exit(3)"))
    rc, output = collect(handle, timeout_seconds=30)
    assert rc == 3
    assert "boom" in output


def test_collect_times_out_and_kills():
    """阻塞語意的逾時：樹殺後丟 TimeoutExpired，不得留下孤兒行程。"""
    handle = spawn(_py(r"import time; time.sleep(30)"))
    with pytest.raises(subprocess.TimeoutExpired):
        collect(handle, timeout_seconds=0.5)
    assert not handle.running


def test_handle_kill_tree_is_callers_to_use():
    """所有權明確：呼叫方拿著 handle，隨時可以取消（cancel() 走的就是這條）。"""
    handle = spawn(_py(r"import time; time.sleep(30)"))
    assert handle.running
    handle.kill_tree()
    for _ in range(100):  # 樹殺是非同步的，給它一點時間收屍
        if not handle.running:
            break
        time.sleep(0.05)
    assert not handle.running


def test_env_extra_reaches_child():
    """呼叫方專屬環境變數要送達——引擎知識（COLUMNS/PYTHONUNBUFFERED）留在
    呼叫方，不硬編進通用機制（grilling Q7：uv 與 rich 都不是所有子程序的問題）。"""
    handle = spawn(
        _py(r"import os; print(os.environ.get('PK_TEST_MARKER', 'missing'))"),
        env_extra={"PK_TEST_MARKER": "present"},
    )
    rc, output = collect(handle, timeout_seconds=30)
    assert "present" in output


def test_decode_env_is_pinned_for_child():
    """解碼契約的寫端：子程序也要被要求輸出 UTF-8（讀寫兩端一起釘死）。"""
    handle = spawn(_py(r"import os; print(os.environ.get('PYTHONIOENCODING'), os.environ.get('PYTHONUTF8'))"))
    rc, output = collect(handle, timeout_seconds=30)
    assert "utf-8" in output and "1" in output
