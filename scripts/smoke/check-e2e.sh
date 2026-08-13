#!/bin/bash
echo "== pdf2zh/babeldoc 子程序 =="
ps -eo pid,etime,cmd | grep -iE "pdf2zh|babeldoc" | grep -v grep | head -8
echo "== outputs 樹 =="
find /tmp/paperkit-e2e/outputs -maxdepth 3 2>/dev/null | head -30
echo "== 任務目錄內 =="
ls -laR /tmp/paperkit-e2e/outputs/*/ 2>/dev/null | head -40
