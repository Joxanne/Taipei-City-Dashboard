"""
static_wifi.py - TaipeiFree WiFi 熱點資料
"""

import argparse
import csv
import io
import ssl
import urllib.request

import psycopg2
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

# ── 資料集設定 ─────────────────────────────────────────────────────────────────
WIFI_URL = (
    "https://data.taipei/api/frontstage/tpeod/dataset/resource.download"
    "?rid=549b3a9b-eb6c-4cb1-848b-8c238735e2db"
)


# ── Step 1: 爬蟲 ──────────────────────────────────────────────────────────────
def crawl() -> list[dict]:
    print("[爬蟲] 下載 TaipeiFree WiFi CSV ...")
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(WIFI_URL, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, context=ctx, timeout=20)
    raw = res.read()

    text = None
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise RuntimeError("無法解碼 CSV 檔案")

    rows = list(csv.DictReader(io.StringIO(text)))
    print(f"[爬蟲] 取得 {len(rows)} 筆原始資料")
    return rows


# ── Step 2: 預處理 ─────────────────────────────────────────────────────────────
def preprocess(rows: list[dict]) -> list[dict]:
    print("[預處理] 清洗與正規化 ...")
    records, skipped = [], 0
    for r in rows:
        try:
            lat = float(r.get("LATITUDE") or 0)
            lon = float(r.get("LONGITUDE") or 0)
        except (ValueError, TypeError):
            skipped += 1
            continue

        # 過濾非台北大都會範圍的座標
        if not (24.9 <= lat <= 25.35 and 121.3 <= lon <= 121.75):
            skipped += 1
            continue

        site_id = (r.get("SITE_ID") or "").strip()
        name = (r.get("NAME") or r.get("E_NAME") or "").strip()
        area = (r.get("AREA") or "").strip()
        address = (r.get("ADDR") or r.get("E_ADDR") or "").strip()

        if not site_id or not name:
            skipped += 1
            continue

        records.append(
            {
                "site_id": site_id,
                "name": name,
                "area": area,
                "address": address,
                "latitude": lat,
                "longitude": lon,
            }
        )

    print(f"[預處理] 有效 {len(records)} 筆，過濾 {skipped} 筆")
    return records


# ── Step 3: 寫入 PostgreSQL ────────────────────────────────────────────────────
def save_to_postgres(records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.wifi_hotspot_tpe (
            ogc_fid    SERIAL PRIMARY KEY,
            data_time  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            site_id    VARCHAR(50) UNIQUE NOT NULL,
            name       TEXT        NOT NULL,
            area       VARCHAR(50),
            address    TEXT,
            latitude   DOUBLE PRECISION,
            longitude  DOUBLE PRECISION,
            _ctime     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    execute_batch(
        cur,
        """
        INSERT INTO public.wifi_hotspot_tpe
            (site_id, name, area, address, latitude, longitude, data_time, _mtime)
        VALUES
            (%(site_id)s, %(name)s, %(area)s, %(address)s,
             %(latitude)s, %(longitude)s,
             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (site_id) DO UPDATE SET
            name      = EXCLUDED.name,
            area      = EXCLUDED.area,
            address   = EXCLUDED.address,
            latitude  = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            data_time = EXCLUDED.data_time,
            _mtime    = EXCLUDED._mtime
    """,
        records,
        page_size=500,
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"[PostgreSQL] 寫入完成（{len(records)} 筆）")


# ── 主程式 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TaipeiFree WiFi 資料入庫管線")
    parser.add_argument(
        "--mode",
        choices=["periodic", "ondemand"],
        default="ondemand",
        help="periodic=定期排程, ondemand=手動觸發",
    )
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  WiFi Pipeline  |  mode={args.mode}")
    print(f"{'='*50}\n")

    rows = crawl()
    records = preprocess(rows)
    if not records:
        print("[警告] 無有效資料，結束。")
        raise SystemExit(0)
    save_to_postgres(records)

    print(f"\n{'='*50}")
    print("  完成！")
    print(f"{'='*50}\n")
