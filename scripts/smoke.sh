#!/usr/bin/env bash
# 冒煙測試（票 18 驗收）：起真實 app、curl 各頁＋zip 路由、清 process。
# 注意：pkill pattern 不得含裸 app 名（-f 會連包裝 bash 一起殺）——
# 本檔是執行檔本身，pattern 用 [p] 技巧只匹配 python 程序。
set -u
cd "$(dirname "$0")/.."
pkill -f 'paper_kit.presentation.ap[p]' || true
sleep 1
.venv/bin/python -u -m paper_kit.presentation.app > /tmp/pk_smoke.log 2>&1 &
APP_PID=$!
# NiceGUI 起服＋SQLite 初始化可能較慢——輪詢直到聽 8080（最多 15s）
for i in $(seq 1 30); do
    if curl -s -o /dev/null http://127.0.0.1:8080/; then break; fi
    sleep 0.5
done
for u in / /history /settings /debug; do
    printf '%-12s ' "$u"
    curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:8080$u"
done
printf '%-12s ' "zip-none"
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8080/download-batch?ids=deadbeef&kind=mono'
printf '%-12s ' "zip-badkind"
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8080/download-batch?ids=deadbeef&kind=exe'
kill "$APP_PID" 2>/dev/null || true
wait "$APP_PID" 2>/dev/null || true
echo "--- smoke done ---"
