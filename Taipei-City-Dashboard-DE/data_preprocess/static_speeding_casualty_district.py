"""
static_speeding_casualty_district.py - 雙北各行政區超速傷亡事故計數資料管線

資料來源：
- 台北：https://data.taipei/dataset/detail?id=2f238b4f-1b27-4085-93e9-d684ef0e2735
        （臺北市A1及A2交通事故資料）
- 新北：https://data.gov.tw/dataset/125357
        （每月新北市A1類道路交通事故－原因及傷亡）
        CSV 直連: https://data.ntpc.gov.tw/api/datasets/ffa7ddcd-6b99-4268-a4b0-e35d8542ff45/csv/file

時間範圍：民國 112-114（三年總計），CLI 可調整

⚠️ accident_count 語義警語：
- 台北：依事故 key dedup 後 COUNT BY district，數字精確
- 新北：分局粒度資料 1:N 複製到所轄各區（PRECINCT_TO_DISTRICTS），
       全市直接 SUM 會高估，僅適合「單一行政區查詢」。
       不要直接做雙北加總統計。

新北資料限制：
- 僅 A1 類（死亡事故），無 A2 受傷統計
- 無座標、無精確行政區（只到分局）
- yearmonth 格式不一致（'103年1月' vs '114 年 12 月'）：用 regex 正規化

注意：台北民國 114 CSV 為 UTF-8（含 BOM），112/113 為 Big5；自動偵測。

寫入模式：TRUNCATE + INSERT（覆蓋）
"""
import argparse
import csv
import io
import re
from collections import defaultdict

import psycopg2
import requests
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

TPE_RIDS = {
    114: "83d6d29c-6801-41a2-95c6-47d551646db3",
    113: "1a08afea-6b2e-4c07-a7a2-17dfba7541f5",
    112: "abf81068-1bb7-414f-868e-29dffd7561bf",
}
TPE_CSV_URL_TEMPLATE = "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={rid}"
NTPC_CSV_URL = "https://data.ntpc.gov.tw/api/datasets/ffa7ddcd-6b99-4268-a4b0-e35d8542ff45/csv/file"

SPEEDING_CAUSE_CODES = {"14", "16"}  # 台北肇因碼

# 新北分局 → 行政區（1:N）。涵蓋 CSV 中觀察到的 20 個 organ 變體 + 歷史改名。
PRECINCT_TO_DISTRICTS: dict[str, list[str]] = {
    "板橋分局":      ["板橋區"],
    "海山分局":      ["板橋區", "土城區"],
    "土城分局":      ["土城區"],
    "三重分局":      ["三重區"],
    "新莊分局":      ["新莊區", "泰山區"],
    "蘆洲分局":      ["蘆洲區", "五股區", "八里區"],
    "中和分局":      ["中和區"],
    "中和一分局":    ["中和區"],
    "中和二分局":    ["中和區"],
    "中和第一分局":  ["中和區"],
    "中和第二分局":  ["中和區"],
    "永和分局":      ["永和區"],
    "新店分局":      ["新店區", "深坑區", "石碇區", "坪林區", "烏來區"],
    "樹林分局":      ["樹林區", "鶯歌區"],
    "三峽分局":      ["三峽區"],
    "林口分局":      ["林口區"],
    "淡水分局":      ["淡水區", "三芝區"],
    "金山分局":      ["金山區", "萬里區", "石門區"],
    "瑞芳分局":      ["瑞芳區", "貢寮區", "雙溪區", "平溪區"],
    "汐止分局":      ["汐止區"],
}


# ── 共用 helper ────────────────────────────────────────────────────────────────
def _decode_csv(content: bytes) -> str:
    """容錯解碼：UTF-8 (with BOM) 優先，否則 Big5（早年台北 CSV 為 Big5）。"""
    try:
        text = content.decode("utf-8-sig")
        if "發生年度" in text[:2000] or "yearmonth" in text[:2000]:
            return text
    except UnicodeDecodeError:
        pass
    return content.decode("big5", errors="replace")


def parse_district_from_qux(qux: str) -> str | None:
    """'03中山區' → '中山區'"""
    m = re.match(r"^\s*\d+\s*(.+?)\s*$", qux or "")
    return m.group(1) if m else None


# ── 台北：crawl + aggregate ───────────────────────────────────────────────────
def crawl_tpe(years: list[int]) -> list[dict]:
    all_rows: list[dict] = []
    for y in years:
        rid = TPE_RIDS.get(y)
        if not rid:
            print(f"[台北爬蟲] 民國 {y} 年 rid 未配置，跳過")
            continue
        url = TPE_CSV_URL_TEMPLATE.format(rid=rid)
        print(f"[台北爬蟲] 民國 {y} 年下載中 ...")
        try:
            res = requests.get(url, timeout=60, verify=False)
            res.raise_for_status()
            text = _decode_csv(res.content)
            rows = list(csv.DictReader(io.StringIO(text)))
            print(f"[台北爬蟲] 民國 {y} 年取得 {len(rows)} 筆")
            all_rows.extend(rows)
        except Exception as exc:
            print(f"[警告] 民國 {y} 年下載失敗：{exc}")
    return all_rows


def aggregate_tpe(rows: list[dict]) -> list[dict]:
    """事故粒度 dedup（不含座標）→ 篩超速 + 篩傷亡 → COUNT BY district"""
    print("[台北聚合] 分組中 ...")
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        yr = (r.get("發生年度") or "").strip()
        mo = (r.get("發生月") or "").strip()
        dy = (r.get("發生日") or "").strip()
        hr = (r.get("發生時-Hours") or "").strip()
        mn = (r.get("發生分") or "").strip()
        qux = (r.get("區序") or "").strip()
        loc = (r.get("肇事地點") or "").strip()
        if not all([yr, mo, dy, hr, mn, qux]):
            continue
        key = (yr, mo, dy, hr, mn, qux, loc)
        groups.setdefault(key, []).append(r)

    counts: dict[str, int] = defaultdict(int)
    kept = filtered = 0
    for _key, members in groups.items():
        cause_codes = {(m.get("肇因碼-個別") or "").strip() for m in members}
        if not (cause_codes & SPEEDING_CAUSE_CODES):
            filtered += 1
            continue

        first = members[0]
        try:
            d1 = int(first.get("死亡人數") or 0)
            d30 = int(first.get("2-30日死亡人數") or 0)
            inj = int(first.get("受傷人數") or 0)
        except ValueError:
            filtered += 1
            continue
        if d1 + d30 + inj <= 0:
            filtered += 1
            continue

        district = parse_district_from_qux(first.get("區序") or "")
        if not district:
            filtered += 1
            continue

        counts[district] += 1
        kept += 1

    print(f"[台北聚合] 保留 {kept} 件，過濾 {filtered} 件，分布到 {len(counts)} 區")
    return [
        {"city": "臺北市", "district": d, "accident_count": c}
        for d, c in counts.items()
    ]


# ── 新北：crawl + aggregate ───────────────────────────────────────────────────
def crawl_ntpc() -> list[dict]:
    print("[新北爬蟲] 下載 NTPC 月聚合 CSV ...")
    res = requests.get(NTPC_CSV_URL, timeout=60, verify=False)
    res.raise_for_status()
    text = _decode_csv(res.content)
    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"[新北爬蟲] 取得 {len(rows)} 筆")
    return rows


def parse_yearmonth(s: str) -> tuple[int, int] | None:
    """容錯解析 '103年1月' / '114 年 12 月' / '113年 06 月' → (民國年, 月)"""
    m = re.match(r"\s*(\d+)\s*年\s*(\d+)\s*月", s or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def aggregate_ntpc(rows: list[dict], years: list[int]) -> list[dict]:
    """篩 yearmonth 落在 years → SUM(quantity1) BY organ → mapping 展開到 district → 加總"""
    print(f"[新北聚合] 篩民國 {years} ...")
    organ_counts: dict[str, int] = defaultdict(int)
    skipped_ym = skipped_q1 = 0

    for r in rows:
        ym = parse_yearmonth(r.get("yearmonth") or "")
        if not ym:
            skipped_ym += 1
            continue
        if ym[0] not in years:
            continue
        try:
            q1 = int((r.get("quantity1") or "0").strip())
        except ValueError:
            skipped_q1 += 1
            continue
        organ = (r.get("organ") or "").strip()
        if organ:
            organ_counts[organ] += q1

    print(
        f"[新北聚合] {len(organ_counts)} 分局有資料；"
        f"yearmonth 解析失敗 {skipped_ym}、quantity1 解析失敗 {skipped_q1}"
    )

    district_counts: dict[str, int] = defaultdict(int)
    unmapped: list[tuple[str, int]] = []
    for organ, total in organ_counts.items():
        if total <= 0:
            continue
        districts = PRECINCT_TO_DISTRICTS.get(organ)
        if not districts:
            unmapped.append((organ, total))
            print(f"[警告] 分局 '{organ}' 無對應行政區，{total} 件被忽略")
            continue
        for d in districts:
            district_counts[d] += total

    print(f"[新北聚合] 展開到 {len(district_counts)} 區；無對應分局 {len(unmapped)} 個")
    return [
        {"city": "新北市", "district": d, "accident_count": c}
        for d, c in district_counts.items()
    ]


# ── 寫入 PostgreSQL ───────────────────────────────────────────────────────────
def save_to_postgres(records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.speeding_casualty_district_tpe (
            ogc_fid          SERIAL PRIMARY KEY,
            city             VARCHAR(20)  NOT NULL,
            district         VARCHAR(20)  NOT NULL,
            accident_count   INTEGER      NOT NULL,
            data_time        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (city, district)
        )
    """)

    cur.execute("TRUNCATE TABLE public.speeding_casualty_district_tpe RESTART IDENTITY")

    execute_batch(
        cur,
        """
        INSERT INTO public.speeding_casualty_district_tpe (
            city, district, accident_count
        ) VALUES (
            %(city)s, %(district)s, %(accident_count)s
        )
        """,
        records,
        page_size=500,
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"[PostgreSQL] 寫入完成（覆蓋 {len(records)} 筆）")


# ── 主程式 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="雙北超速傷亡行政區計數資料管線")
    parser.add_argument(
        "--years", type=int, nargs="+", default=[112, 113, 114],
        help="民國年清單，預設 112 113 114",
    )
    args = parser.parse_args()

    print(f"\n{'=' * 50}")
    print(f"  Speeding Casualty by District  |  years={args.years}")
    print(f"{'=' * 50}\n")

    tpe_rows = crawl_tpe(args.years)
    tpe_records = aggregate_tpe(tpe_rows)

    try:
        ntpc_rows = crawl_ntpc()
    except Exception as exc:
        print(f"[錯誤] 新北資料下載失敗：{exc}")
        raise SystemExit(1)
    ntpc_records = aggregate_ntpc(ntpc_rows, args.years)

    records = tpe_records + ntpc_records
    if not records:
        print("[警告] 無有效資料，跳過寫入（保留既有資料）")
        raise SystemExit(0)

    save_to_postgres(records)

    print(f"\n{'=' * 50}")
    print("  完成！")
    print(f"{'=' * 50}\n")
