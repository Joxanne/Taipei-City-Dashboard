"""
static_speeding_casualty_points_tpe.py - 台北市超速傷亡事件點位資料管線

資料來源: 臺北市A1及A2交通事故資料
        https://data.taipei/dataset/detail?id=2f238b4f-1b27-4085-93e9-d684ef0e2735

功能：抓取民國 112-114 年事故 CSV，篩出超速 (肇因碼-個別 ∈ {14, 16})
     且有傷亡的事故，dedup 為事故粒度，寫入 speeding_casualty_points_tpe 表。

注意：
- 民國 114 CSV 為 UTF-8（含 BOM），112/113 為 Big5。腳本自動偵測。
- 寫入模式：TRUNCATE + INSERT（覆蓋）。
"""
import argparse
import csv
import io
import re
from datetime import datetime

import psycopg2
import requests
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

TPE_RIDS = {
    114: "83d6d29c-6801-41a2-95c6-47d551646db3",
    113: "1a08afea-6b2e-4c07-a7a2-17dfba7541f5",
    112: "abf81068-1bb7-414f-868e-29dffd7561bf",
}
CSV_URL_TEMPLATE = "https://data.taipei/api/frontstage/tpeod/dataset/resource.download?rid={rid}"

# 14=超速失控, 16=未依規定減速；與新北 quantity1 「超速失控_含未減速」口徑一致
SPEEDING_CAUSE_CODES = {"14", "16"}


def _decode_csv(content: bytes) -> str:
    """容錯解碼：UTF-8 (with BOM) 優先，否則 Big5（早年 CSV 為 Big5）。"""
    try:
        text = content.decode("utf-8-sig")
        if "發生年度" in text[:2000]:
            return text
    except UnicodeDecodeError:
        pass
    return content.decode("big5", errors="replace")


# ── Step 1: HTTP 抓取 ──────────────────────────────────────────────────────────
def crawl(years: list[int]) -> list[dict]:
    all_rows: list[dict] = []
    for y in years:
        rid = TPE_RIDS.get(y)
        if not rid:
            print(f"[爬蟲] 民國 {y} 年 rid 未配置，跳過")
            continue
        url = CSV_URL_TEMPLATE.format(rid=rid)
        print(f"[爬蟲] 民國 {y} 年下載中 ...")
        try:
            res = requests.get(url, timeout=60, verify=False)
            res.raise_for_status()
            text = _decode_csv(res.content)
            rows = list(csv.DictReader(io.StringIO(text)))
            print(f"[爬蟲] 民國 {y} 年取得 {len(rows)} 筆")
            all_rows.extend(rows)
        except Exception as exc:
            print(f"[警告] 民國 {y} 年下載失敗：{exc}，跳過")
    return all_rows


# ── Step 2: 預處理 ─────────────────────────────────────────────────────────────
def parse_district(qux: str) -> str | None:
    """'03中山區' → '中山區'"""
    m = re.match(r"^\s*\d+\s*(.+?)\s*$", qux or "")
    return m.group(1) if m else None


def preprocess(rows: list[dict]) -> list[dict]:
    print("[預處理] 依事故 key 分組 ...")
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        yr = (r.get("發生年度") or "").strip()
        mo = (r.get("發生月") or "").strip()
        dy = (r.get("發生日") or "").strip()
        hr = (r.get("發生時-Hours") or "").strip()
        mn = (r.get("發生分") or "").strip()
        if not all([yr, mo, dy, hr, mn]):
            continue
        x = (r.get("座標-X") or "").strip()
        y = (r.get("座標-Y") or "").strip()
        loc = (r.get("肇事地點") or "").strip()
        key = (yr, mo, dy, hr, mn, x, y, loc)
        groups.setdefault(key, []).append(r)

    print(f"[預處理] 共 {len(groups)} 件事故")

    records: list[dict] = []
    filtered_speed = filtered_coord = filtered_casualty = filtered_district = 0

    for key, members in groups.items():
        cause_codes = {(m.get("肇因碼-個別") or "").strip() for m in members}
        if not (cause_codes & SPEEDING_CAUSE_CODES):
            filtered_speed += 1
            continue

        first = members[0]

        try:
            lon = float(first.get("座標-X") or "")
            lat = float(first.get("座標-Y") or "")
            if lon == 0 or lat == 0:
                raise ValueError("zero coord")
        except ValueError:
            filtered_coord += 1
            continue

        try:
            d1 = int(first.get("死亡人數") or 0)
            d30 = int(first.get("2-30日死亡人數") or 0)
            inj = int(first.get("受傷人數") or 0)
        except ValueError:
            filtered_casualty += 1
            continue
        if d1 + d30 + inj <= 0:
            filtered_casualty += 1
            continue

        district = parse_district(first.get("區序") or "")
        if not district:
            filtered_district += 1
            continue

        try:
            accident_time = datetime(
                int(key[0]) + 1911,
                int(key[1]),
                int(key[2]),
                int(key[3]),
                int(key[4]),
            )
        except (ValueError, OverflowError):
            filtered_casualty += 1
            continue

        records.append({
            "accident_time": accident_time,
            "district": district,
            "location_text": first.get("肇事地點") or "",
            "longitude": lon,
            "latitude": lat,
            "death_count": d1 + d30,
            "injury_count": inj,
        })

    print(
        f"[預處理] 保留 {len(records)} 件；過濾："
        f"非超速 {filtered_speed}、座標無效 {filtered_coord}、"
        f"無傷亡 {filtered_casualty}、區序解析失敗 {filtered_district}"
    )
    return records


# ── Step 3: 寫入 PostgreSQL ────────────────────────────────────────────────────
def save_to_postgres(records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.speeding_casualty_points_tpe (
            ogc_fid          SERIAL PRIMARY KEY,
            accident_time    TIMESTAMP        NOT NULL,
            district         VARCHAR(20)      NOT NULL,
            location_text    TEXT             NOT NULL,
            longitude        DOUBLE PRECISION NOT NULL,
            latitude         DOUBLE PRECISION NOT NULL,
            death_count      SMALLINT         NOT NULL,
            injury_count     SMALLINT         NOT NULL,
            data_time        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (accident_time, longitude, latitude, location_text)
        )
    """)

    cur.execute("TRUNCATE TABLE public.speeding_casualty_points_tpe RESTART IDENTITY")

    execute_batch(
        cur,
        """
        INSERT INTO public.speeding_casualty_points_tpe (
            accident_time, district, location_text,
            longitude, latitude, death_count, injury_count
        ) VALUES (
            %(accident_time)s, %(district)s, %(location_text)s,
            %(longitude)s, %(latitude)s, %(death_count)s, %(injury_count)s
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
    parser = argparse.ArgumentParser(description="台北超速傷亡事故點位資料管線")
    parser.add_argument(
        "--years", type=int, nargs="+", default=[112, 113, 114],
        help="民國年清單，預設 112 113 114",
    )
    args = parser.parse_args()

    print(f"\n{'=' * 50}")
    print(f"  Speeding Casualty Points (TPE)  |  years={args.years}")
    print(f"{'=' * 50}\n")

    rows = crawl(args.years)
    if not rows:
        print("[錯誤] 無原始資料，結束")
        raise SystemExit(1)

    records = preprocess(rows)
    if not records:
        print("[警告] 無有效資料，跳過寫入（保留既有資料）")
        raise SystemExit(0)

    save_to_postgres(records)

    print(f"\n{'=' * 50}")
    print("  完成！")
    print(f"{'=' * 50}\n")
