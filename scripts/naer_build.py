#!/usr/bin/env python3
"""樂詞網學術名詞 → Paper_Kit `naer-core` 詞表生成器（一次性工具，可重現）。

來源：國家教育研究院 樂詞網（https://terms.naer.edu.tw/）「下載專區」zip——
      電子計算機名詞／電機工程名詞／食品科技／魚類（2026-08-14 實測下載專區
      開放的 4 個非音樂領域；音樂 6 包與 Paper_Kit 論文翻譯無關不入選）。
授權：**政府資料開放授權條款-第1版**（可再授權、商業可用、僅需顯名聲明——
      本檔檔頭＋builtin_glossary.py docstring＋NOTICE 即為顯名聲明）。
      research 查證見 docs/research/2026-08-14-Paper_Kit-研究-GitHub術語庫全面掃描-查證.md。
產出：src/paper_kit/infrastructure/data/naer_core.csv.gz
      （三欄 CSV source,target,tgt_lng；tgt_lng 全 zh-TW）。
選取準則（2026-08-14 定案，v1 單詞層）：
  - source：全小寫、單詞（無空格）、字母開頭、無括號/大括號註記（()（）[]{}）
  - target：無括號註記、無「格式檔案」類、簡體字形黑名單過濾（實測 0 命中——
    NAER 官方品質；保留為生成期防線）
  - 長度：source ≤ 40、target ≤ 40
  - 同 source 跨領域：以第一個（電子計算機優先）為準
用法：uv run python scripts/naer_build.py [--download-dir /tmp/naer]
      （預設下載目錄 /tmp/naer，已存在之 zip 不重下載）
"""

import csv
import gzip
import html
import io
import re
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT = REPO_ROOT / "src" / "paper_kit" / "infrastructure" / "data" / "naer_core.csv.gz"

# 2026-08-14 樂詞網下載專區非音樂 zip（URL 檔名保留後綴隨機 token，勿改）
ZIPS = [
    "https://terms.naer.edu.tw/media/terms_data/1/%E9%9B%BB%E5%AD%90%E8%A8%88%E7%AE%97%E6%A9%9F%E5%90%8D%E8%A9%9E%E5%A3%93%E7%B8%AE%E6%AA%94_YJvKcWY.zip",
    "https://terms.naer.edu.tw/media/terms_data/1/%E9%9B%BB%E6%A9%9F%E5%B7%A5%E7%A8%8B%E5%90%8D%E8%A9%9E%E5%A3%93%E7%B8%AE%E6%AA%94_RuYWQfB.zip",
    "https://terms.naer.edu.tw/media/terms_data/1/%E9%A3%9F%E5%93%81%E7%A7%91%E6%8A%80%E5%A3%93%E7%B8%AE%E6%AA%94.zip",
    "https://terms.naer.edu.tw/media/terms_data/1/%E9%AD%9A%E9%A1%9E%E5%A3%93%E7%B8%AE%E6%AA%94.zip",
]

# 無歧義簡體字形（正體詞表不該出現；排除繁簡同形字如 程/題/問）
_SIMPL = set("关网练验识录优办卫华协单叶号诉讲设许证词论该诸议评责财产质转软较过进远运选邮错长问题页须监库处输导执维现报础构调试统结备则级层实际机达启动击异预")


def _has_simpl(zh: str) -> bool:
    return any(c in _SIMPL for c in zh)


def _download(zip_url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  已有 {dest.name}（{dest.stat().st_size} bytes），跳過下載")
        return
    print(f"  下載 {urllib.parse.unquote(zip_url.rsplit('/', 1)[-1])} …")
    urllib.request.urlretrieve(zip_url, dest)  # noqa: S310 樂詞網官方 https


def _parse_ods(path: Path) -> list[tuple[str, str]]:
    """ODS（zip 內 content.xml）→ (英文, 中文) 列。欄位：ID|英文名稱|中文名稱|圖片|更新日期。"""
    z = zipfile.ZipFile(path)
    xml = z.read("content.xml").decode("utf-8", errors="replace")
    rows = re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", xml, re.S)
    out = []
    for r in rows[1:]:  # 跳表頭
        cells = re.findall(r"<text:p[^>]*>(.*?)</text:p>", r, re.S)
        if len(cells) >= 3:
            en, zh = cells[1].strip(), cells[2].strip()
            if en and zh:
                out.append((en, zh))
    return out


def _keep(en: str, zh: str) -> bool:
    en = html.unescape(en).strip()
    zh = html.unescape(zh).strip()
    if not en or not zh:
        return False
    if re.search(r"[()（）\[\]{}]", en) or re.search(r"[()（）\[\]{}]", zh):
        return False  # ISO 括號註記（(2,7) code）與 [See …] 註記
    if '"' in en or '"' in zh or "," in zh:
        return False  # 引號/逗號破壞 naive CSV 相容（`"^"；ASCII 94 字元` 定義類噪音）
    if len(en) > 40 or len(zh) > 40:
        return False
    if " " in en:
        return False  # v1 單詞層（雙詞層留待 0.1.9.1 實測引擎效能後擴）
    if not re.match(r"^[a-z]", en):
        return False  # 濾 .shtml/1080p/@stake 檔名與代碼噪音
    if "格式檔案" in zh:
        return False
    if _has_simpl(zh):
        return False  # 實測 0 命中（官方品質），生成期防線
    return True


def main() -> int:
    dl_dir = Path(sys.argv[sys.argv.index("--download-dir") + 1]) if "--download-dir" in sys.argv else Path("/tmp/naer")
    dl_dir.mkdir(parents=True, exist_ok=True)

    print(f"1/2 下載樂詞網 zip（{len(ZIPS)} 包 → {dl_dir}）")
    zip_paths = []
    for url in ZIPS:
        name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        dest = dl_dir / name
        _download(url, dest)
        zip_paths.append(dest)

    print("2/2 解析 ODS → 過濾 → 寫 gzip")
    seen: set[str] = set()
    terms: list[tuple[str, str]] = []
    raw = 0
    for zp in zip_paths:
        z = zipfile.ZipFile(zp)
        for info in z.infolist():
            if not info.filename.endswith(".ods"):
                continue
            with z.open(info) as f:
                tmp = dl_dir / info.filename
                tmp.write_bytes(f.read())
            for en, zh in _parse_ods(tmp):
                raw += 1
                en = html.unescape(en).strip()
                zh = html.unescape(zh).strip()
                # 同義詞 source（如 `aisle,corridor`）拆分為獨立條目（naive CSV 相容）
                for part in re.split(r"\s*,\s*", en):
                    if part in seen:
                        continue
                    if _keep(part, zh):
                        seen.add(part)
                        terms.append((part, zh))
            tmp.unlink()

    terms.sort()
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["source", "target", "tgt_lng"])
    for en, zh in terms:
        w.writerow([en, zh, "zh-TW"])
    data = buf.getvalue().encode("utf-8")
    gz = gzip.compress(data, compresslevel=9)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(gz)
    print(f"\nraw 列數（含重複/跨域）: {raw}")
    print(f"naer-core v1 條數: {len(terms)}")
    print(f"CSV 原大小: {len(data)/1e6:.2f} MB；gzip: {len(gz)/1e6:.2f} MB")
    print(f"寫出: {OUT}")
    print("\n抽樣（前 20）：")
    for en, zh in terms[:20]:
        print(f"  {en} | {zh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
