"""
periodic_bus_estimate_time.py - 大臺北公車預估到站時間資料管線

資料來源:
  臺北市 - GetEstimateTime.gz (tcgbusfs/blobbus)
  新北市 - GetEstimateTime.gz (tcgbusfs/ntpcbus)

前置條件:
  執行本腳本前，請先確認已跑過 static_bus_stops.py，
  否則 bus_route_stops_tpe / bus_stop_tpe 不存在，後續 join 將失敗。

寫入一張表:
  bus_estimate_time_tpe - 各路線各站牌預估到站時間（週期性 upsert）

EstimateTime 特殊值:
  -1: 尚未發車  -2: 交管不停靠  -3: 末班車已過  -4: 今日未營運

─── 後續查詢範例 ────────────────────────────────────────────────────────────────

[Dashboard] 各行政區平均預估到站時間（臺北市，單位：分鐘）:

  SELECT bst.district AS x_axis,
         ROUND(AVG(bet.estimate_time) / 60.0, 1) AS data
  FROM public.bus_estimate_time_tpe bet
  JOIN public.bus_route_stops_tpe brs
       ON bet.city = brs.city AND bet.stop_id = brs.stop_id
  JOIN public.bus_stop_tpe bst
       ON brs.city = bst.city AND brs.stop_location_id = bst.stop_location_id
  WHERE bet.estimate_time > 0
    AND bst.geo_city = '臺北市'
    AND bst.district IS NOT NULL
  GROUP BY bst.district
  ORDER BY data;

[Mapview] 各站點最近一班預估到站時間（秒）:

  SELECT bst.stop_name, bst.latitude, bst.longitude, bst.district,
         MIN(bet.estimate_time) AS nearest_estimate_sec
  FROM public.bus_stop_tpe bst
  JOIN public.bus_route_stops_tpe brs
       ON bst.city = brs.city AND bst.stop_location_id = brs.stop_location_id
  JOIN public.bus_estimate_time_tpe bet
       ON brs.city = bet.city AND brs.stop_id = bet.stop_id
  WHERE bet.estimate_time > 0
    AND bst.latitude IS NOT NULL
  GROUP BY bst.stop_name, bst.latitude, bst.longitude, bst.district;
"""
import argparse
import gzip
import json
import ssl
import urllib.request
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

_ROOT       = Path(__file__).parent.parent.parent
_GEOJSON_DIR = _ROOT / "Taipei-City-Dashboard-FE" / "public" / "mapData"

ESTIMATE_SOURCES = {
    "臺北市": "https://tcgbusfs.blob.core.windows.net/blobbus/GetEstimateTime.gz",
    "新北市": "https://tcgbusfs.blob.core.windows.net/ntpcbus/GetEstimateTime.gz",
}

HEADERS = {"User-Agent": "TaipeiDashboard/1.0"}


# ── 工具函式 ───────────────────────────────────────────────────────────────────
def _fetch_gz(url: str) -> list[dict]:
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url.strip(), headers=HEADERS)
    res = urllib.request.urlopen(req, context=ctx, timeout=60)
    raw = gzip.decompress(res.read())
    data = json.loads(raw.decode("utf-8"))
    return data.get("BusInfo", data) if isinstance(data, dict) else data


# ── Step 1: 爬蟲 ──────────────────────────────────────────────────────────────
def crawl() -> list[dict]:
    """回傳兩城市合併的 raw rows"""
    rows = []
    for city, url in ESTIMATE_SOURCES.items():
        print(f"[爬蟲] 下載 {city} 預估到站資料 ...")
        city_rows = _fetch_gz(url)
        for r in city_rows:
            r["_city"] = city
        rows.extend(city_rows)
        print(f"[爬蟲] {city}：{len(city_rows)} 筆")
    print(f"[爬蟲] 合計 {len(rows)} 筆")
    return rows


def load_sample(path: str) -> list[dict]:
    print(f"[Sample] 讀取本地 JSON：{path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Step 2: 預處理 ─────────────────────────────────────────────────────────────
def preprocess(rows: list[dict]) -> list[dict]:
    print("[預處理] 整理預估到站資料 ...")
    records = []
    for r in rows:
        route_id = r.get("RouteID")
        stop_id  = r.get("StopID")
        if not route_id or not stop_id:
            continue
        try:
            estimate_time = int(r.get("EstimateTime", -1))
        except (ValueError, TypeError):
            estimate_time = -1
        try:
            go_back = int(r.get("GoBack", 0))
        except (ValueError, TypeError):
            go_back = 0
        records.append({
            "city":          r["_city"],
            "route_id":      int(route_id),
            "stop_id":       int(stop_id),
            "estimate_time": estimate_time,
            "go_back":       go_back,
        })
    print(f"[預處理] {len(records)} 筆")
    return records


# ── Step 3: 寫入 PostgreSQL ────────────────────────────────────────────────────
def save_to_postgres(records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.bus_estimate_time_tpe (
            ogc_fid       SERIAL PRIMARY KEY,
            city          VARCHAR(10)  NOT NULL,
            route_id      INTEGER      NOT NULL,
            stop_id       INTEGER      NOT NULL,
            estimate_time INTEGER,
            go_back       SMALLINT,
            data_time     TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
            _ctime        TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
            _mtime        TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (city, route_id, stop_id, go_back)
        )
    """)

    execute_batch(cur, """
        INSERT INTO public.bus_estimate_time_tpe
            (city, route_id, stop_id, estimate_time, go_back, data_time, _mtime)
        VALUES
            (%(city)s, %(route_id)s, %(stop_id)s, %(estimate_time)s, %(go_back)s,
             CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (city, route_id, stop_id, go_back) DO UPDATE SET
            estimate_time = EXCLUDED.estimate_time,
            data_time     = EXCLUDED.data_time,
            _mtime        = EXCLUDED._mtime
    """, records, page_size=1000)

    conn.commit()
    cur.close()
    conn.close()
    print(f"[PostgreSQL] bus_estimate_time_tpe 寫入/更新 {len(records)} 筆")


# ── Step 4: 產生 GeoJSON（供 mapview 使用）────────────────────────────────────────
_GEOJSON_QUERY = """
    SELECT
        bst.stop_name,
        bst.longitude,
        bst.latitude,
        COALESCE(bst.district, '')  AS district,
        COALESCE(bst.geo_city, '')  AS geo_city,
        COALESCE(
            ROUND(
                MIN(CASE WHEN bet.estimate_time > 0
                         THEN bet.estimate_time::NUMERIC ELSE NULL END
                ) / 60.0, 1
            ),
            -1
        )::FLOAT AS nearest_estimate_min
    FROM public.bus_stop_tpe bst
    LEFT JOIN public.bus_route_stops_tpe brs
           ON bst.city = brs.city AND bst.stop_location_id = brs.stop_location_id
    LEFT JOIN public.bus_estimate_time_tpe bet
           ON brs.city = bet.city AND brs.stop_id = bet.stop_id
    WHERE bst.latitude  IS NOT NULL
      AND bst.longitude IS NOT NULL
      {where_extra}
    GROUP BY bst.stop_name, bst.longitude, bst.latitude, bst.district, bst.geo_city
"""


def generate_geojson() -> None:
    """從 DB 產生公車站點 GeoJSON，寫入 FE public/mapData/。"""
    if not _GEOJSON_DIR.exists():
        print(f"[GeoJSON] 找不到 FE mapData 目錄：{_GEOJSON_DIR}，跳過。")
        return

    conn = psycopg2.connect(**PG_DASHBOARD)
    cur  = conn.cursor()

    # 確認 bus_estimate_time_tpe 存在
    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name   = 'bus_estimate_time_tpe'
        )
    """)
    if not cur.fetchone()[0]:
        print("[GeoJSON] bus_estimate_time_tpe 尚未建立，跳過。")
        cur.close(); conn.close()
        return

    for label, where_extra, filename in [
        ("臺北市",  "AND bst.geo_city = '臺北市'", "bus_stop_estimate_tpe.geojson"),
        ("雙北",    "",                             "bus_stop_estimate_metrotaipei.geojson"),
    ]:
        print(f"[GeoJSON] 產生 {label} 站點資料 ...")
        cur.execute(_GEOJSON_QUERY.format(where_extra=where_extra))
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

        features = []
        for row in rows:
            r = dict(zip(cols, row))
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [r["longitude"], r["latitude"]],
                },
                "properties": {
                    "stop_name":           r["stop_name"],
                    "district":            r["district"],
                    "geo_city":            r["geo_city"],
                    "nearest_estimate_min": r["nearest_estimate_min"],
                },
            })

        geojson = {"type": "FeatureCollection", "features": features}
        out_path = _GEOJSON_DIR / filename
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False)
        print(f"[GeoJSON] {filename}：{len(features)} 個站點 → {out_path}")

    cur.close()
    conn.close()


# ── 主程式 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="大臺北公車預估到站時間資料管線")
    parser.add_argument(
        "--mode",
        choices=["periodic", "ondemand", "sample"],
        default="periodic",
        help="periodic=定期排程, ondemand=AI觸發, sample=本地JSON",
    )
    parser.add_argument("--sample-path", default="", help="sample 模式下的 JSON 檔案路徑")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  Bus Estimate Time Pipeline  |  mode={args.mode}")
    print(f"{'='*50}\n")

    if args.mode in ("periodic", "ondemand"):
        rows = crawl()
    else:
        if not args.sample_path:
            print("[錯誤] sample 模式需提供 --sample-path")
            raise SystemExit(1)
        rows = load_sample(args.sample_path)

    records = preprocess(rows)

    if not records:
        print("[警告] 無資料，結束。")
        raise SystemExit(0)

    save_to_postgres(records)
    generate_geojson()

    print(f"\n{'='*50}")
    print("  完成！")
    print(f"{'='*50}\n")
