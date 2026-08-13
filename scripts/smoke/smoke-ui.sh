#!/bin/bash
# UI 四頁冒煙
for p in / /settings /history /debug; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8080$p")
  echo "$p -> $code"
done
