#!/usr/bin/env python3
"""2026-08-13：celebras/g4f 域名解析驗證（補 probe 的連線失敗判定）。"""
import socket

for name in ["api.celebras.ai", "g4f.space", "speed.toter.me"]:
    try:
        addrs = socket.gethostbyname_ex(name)
        print(f"{name:<18} OK  {addrs[2][:4]}")
    except Exception as e:
        print(f"{name:<18} FAIL {type(e).__name__}: {e}")
