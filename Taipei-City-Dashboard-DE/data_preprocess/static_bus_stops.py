"""
static_bus_stops.py - 大臺北公車站點資料管線
資料來源:
  臺北市 - GetRoute.gz / GetStop.gz (tcgbusfs/blobbus)
  新北市 - GetRoute.gz / GetStop.gz (tcgbusfs/ntpcbus)

寫入三張表:
  bus_route_tpe       - 路線資訊（路線名稱、起終點）
  bus_stop_tpe        - 物理站點（依 stopLocationId 去重）
  bus_route_stops_tpe - 路線站序（stop_id 可 join EstimateTime.StopID）

查詢範例（299路線站別）:
  SELECT brs.go_back, brs.stop_seq, bs.stop_name
  FROM bus_route_tpe br
  JOIN bus_route_stops_tpe brs ON br.route_id = brs.route_id AND br.city = brs.city
  JOIN bus_stop_tpe bs ON brs.stop_location_id = bs.stop_location_id AND brs.city = bs.city
  WHERE br.route_name = '299'
  ORDER BY brs.go_back, brs.stop_seq;

Join 關係:
  bus_route_tpe.route_id         ←→  bus_route_stops_tpe.route_id
  bus_route_tpe.route_id         ←→  bus_shape_tpe.route_id
  bus_stop_tpe.stop_location_id  ←→  bus_route_stops_tpe.stop_location_id
  bus_route_stops_tpe.stop_id    ←→  EstimateTime.StopID（動態到站預測）
"""
import argparse
import gzip
import json
import ssl
import urllib.request

import psycopg2
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

STOP_SOURCES = {
    "臺北市": "https://tcgbusfs.blob.core.windows.net/blobbus/GetStop.gz",
    "新北市": "https://tcgbusfs.blob.core.windows.net/ntpcbus/GetStop.gz",
}

ROUTE_SOURCES = {
    "臺北市": "https://tcgbusfs.blob.core.windows.net/blobbus/GetRoute.gz",
    "新北市": "https://tcgbusfs.blob.core.windows.net/ntpcbus/GetRoute.gz",
}

HEADERS = {"User-Agent": "TaipeiDashboard/1.0"}


# ── 工具函式 ───────────────────────────────────────────────────────────────────
def _fetch_gz(url: str) -> list[dict]:
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(url, headers=HEADERS)
    res = urllib.request.urlopen(req, context=ctx, timeout=30)
    raw = gzip.decompress(res.read())
    data = json.loads(raw.decode("utf-8"))
    return data.get("BusInfo", data) if isinstance(data, dict) else data


# ── Step 1: 爬蟲 ──────────────────────────────────────────────────────────────
def crawl() -> tuple[list[dict], list[dict]]:
    """回傳 (route_rows, stop_rows)"""
    route_rows, stop_rows = [], []

    for city in ROUTE_SOURCES:
        print(f"[爬蟲] 下載 {city} 路線資料 ...")
        for r in _fetch_gz(ROUTE_SOURCES[city]):
            route_rows.append({"_city": city, **r})
        print(f"[爬蟲] {city} 路線：{sum(1 for r in route_rows if r['_city'] == city)} 筆")

        print(f"[爬蟲] 下載 {city} 站牌資料 ...")
        for r in _fetch_gz(STOP_SOURCES[city]):
            stop_rows.append({"_city": city, **r})
        print(f"[爬蟲] {city} 站牌：{sum(1 for r in stop_rows if r['_city'] == city)} 筆")

    print(f"[爬蟲] 路線合計 {len(route_rows)} 筆，站牌合計 {len(stop_rows)} 筆")
    return route_rows, stop_rows


def load_sample(path: str) -> tuple[list[dict], list[dict]]:
    print(f"[Sample] 讀取本地 JSON：{path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("routes", []), data.get("stops", [])


# ── Step 2: 預處理 ─────────────────────────────────────────────────────────────
def preprocess_routes(route_rows: list[dict]) -> list[dict]:
    print("[預處理] 整理路線資料 ...")
    records = []
    for r in route_rows:
        route_id = r.get("Id")
        if not route_id:
            continue
        records.append({
            "city":          r["_city"],
            "route_id":      route_id,
            "uni_route_id":  r.get("NId", ""),
            "route_name":    r.get("nameZh", ""),
            "route_name_en": r.get("nameEn", ""),
            "departure":     r.get("departureZh", ""),
            "destination":   r.get("destinationZh", ""),
        })
    print(f"[預處理] 路線 {len(records)} 筆")
    return records


def preprocess_stops(stop_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """回傳 (stop_records, route_stop_records)"""
    print("[預處理] 整理站點與路線站序 ...")

    seen_stops: dict[tuple, dict] = {}
    route_stop_records: list[dict] = []

    for r in stop_rows:
        city             = r["_city"]
        stop_location_id = r.get("stopLocationId")
        stop_id          = r.get("Id")
        route_id         = r.get("routeId")

        if not stop_location_id or not stop_id or not route_id:
            continue

        try:
            lat = float(r["latitude"])  if r.get("latitude")  else None
            lon = float(r["longitude"]) if r.get("longitude") else None
        except (ValueError, TypeError):
            lat, lon = None, None

        try:
            seq     = int(r.get("seqNo",  0))
            go_back = int(r.get("goBack", 0))
        except (ValueError, TypeError):
            seq, go_back = 0, 0

        key = (city, stop_location_id)
        if key not in seen_stops:
            seen_stops[key] = {
                "city":             city,
                "stop_location_id": stop_location_id,
                "stop_name":        r.get("nameZh", ""),
                "stop_name_en":     r.get("nameEn", ""),
                "latitude":         lat,
                "longitude":        lon,
            }

        route_stop_records.append({
            "city":             city,
            "route_id":         route_id,
            "stop_id":          stop_id,
            "stop_location_id": stop_location_id,
            "stop_seq":         seq,
            "go_back":          go_back,
        })

    stop_records = list(seen_stops.values())
    print(f"[預處理] 物理站點 {len(stop_records)} 個，路線站序 {len(route_stop_records)} 筆")
    return stop_records, route_stop_records


# ── Step 3: 寫入 PostgreSQL ────────────────────────────────────────────────────
def _save_routes(cur, records: list[dict]) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.bus_route_tpe (
            ogc_fid        SERIAL PRIMARY KEY,
            city           VARCHAR(10)  NOT NULL,
            route_id       INTEGER      NOT NULL,
            uni_route_id   VARCHAR(20),
            route_name     VARCHAR(50),
            route_name_en  VARCHAR(100),
            departure      VARCHAR(50),
            destination    VARCHAR(100),
            data_time      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime         TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (city, route_id)
        )
    """)
    execute_batch(cur, """
        INSERT INTO public.bus_route_tpe (
            city, route_id, uni_route_id, route_name, route_name_en,
            departure, destination, data_time, _mtime
        ) VALUES (
            %(city)s, %(route_id)s, %(uni_route_id)s, %(route_name)s, %(route_name_en)s,
            %(departure)s, %(destination)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (city, route_id) DO UPDATE SET
            uni_route_id  = EXCLUDED.uni_route_id,
            route_name    = EXCLUDED.route_name,
            route_name_en = EXCLUDED.route_name_en,
            departure     = EXCLUDED.departure,
            destination   = EXCLUDED.destination,
            data_time     = EXCLUDED.data_time,
            _mtime        = EXCLUDED._mtime
    """, records, page_size=500)
    print(f"[PostgreSQL] bus_route_tpe 寫入 {len(records)} 筆")


def _save_stops(cur, records: list[dict]) -> None:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.bus_stop_tpe (
            ogc_fid          SERIAL PRIMARY KEY,
            city             VARCHAR(10)      NOT NULL,
            stop_location_id INTEGER          NOT NULL,
            stop_name        VARCHAR(100),
            stop_name_en     VARCHAR(200),
            latitude         DOUBLE PRECISION,
            longitude        DOUBLE PRECISION,
            data_time        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (city, stop_location_id)
        )
    """)
    execute_batch(cur, """
        INSERT INTO public.bus_stop_tpe (
            city, stop_location_id, stop_name, stop_name_en,
            latitude, longitude, data_time, _mtime
        ) VALUES (
            %(city)s, %(stop_location_id)s, %(stop_name)s, %(stop_name_en)s,
            %(latitude)s, %(longitude)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (city, stop_location_id) DO UPDATE SET
            stop_name    = EXCLUDED.stop_name,
            stop_name_en = EXCLUDED.stop_name_en,
            latitude     = EXCLUDED.latitude,
            longitude    = EXCLUDED.longitude,
            data_time    = EXCLUDED.data_time,
            _mtime       = EXCLUDED._mtime
    """, records, page_size=500)
    print(f"[PostgreSQL] bus_stop_tpe 寫入 {len(records)} 筆")


def _save_route_stops(cur, records: list[dict]) -> None:
    # DROP + 重建取代 static_bus_shape.py 的 Overpass 版本（schema 不相容）
    cur.execute("DROP TABLE IF EXISTS public.bus_route_stops_tpe")
    cur.execute("""
        CREATE TABLE public.bus_route_stops_tpe (
            ogc_fid          SERIAL PRIMARY KEY,
            city             VARCHAR(10)  NOT NULL,
            route_id         INTEGER      NOT NULL,
            stop_id          INTEGER      NOT NULL,
            stop_location_id INTEGER,
            stop_seq         SMALLINT,
            go_back          SMALLINT,
            data_time        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (city, stop_id)
        )
    """)
    execute_batch(cur, """
        INSERT INTO public.bus_route_stops_tpe (
            city, route_id, stop_id, stop_location_id,
            stop_seq, go_back, data_time, _mtime
        ) VALUES (
            %(city)s, %(route_id)s, %(stop_id)s, %(stop_location_id)s,
            %(stop_seq)s, %(go_back)s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (city, stop_id) DO NOTHING
    """, records, page_size=500)
    print(f"[PostgreSQL] bus_route_stops_tpe 寫入 {len(records)} 筆")


def save_to_postgres(route_records: list[dict],
                     stop_records: list[dict],
                     route_stop_records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur  = conn.cursor()
    _save_routes(cur, route_records)
    _save_stops(cur, stop_records)
    _save_route_stops(cur, route_stop_records)
    conn.commit()
    cur.close()
    conn.close()
    print("[PostgreSQL] 所有資料寫入完成")


# ── 主程式 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="大臺北公車站點資料管線")
    parser.add_argument(
        "--mode",
        choices=["periodic", "ondemand", "sample"],
        default="ondemand",
        help="periodic=定期排程, ondemand=AI觸發, sample=本地JSON",
    )
    parser.add_argument("--sample-path", default="", help="sample 模式下的 JSON 檔案路徑")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  Bus Stops Pipeline  |  mode={args.mode}")
    print(f"{'='*50}\n")

    if args.mode in ("periodic", "ondemand"):
        route_rows, stop_rows = crawl()
    else:
        if not args.sample_path:
            print("[錯誤] sample 模式需提供 --sample-path")
            raise SystemExit(1)
        route_rows, stop_rows = load_sample(args.sample_path)

    route_records                    = preprocess_routes(route_rows)
    stop_records, route_stop_records = preprocess_stops(stop_rows)

    if not stop_records:
        print("[警告] 無站點資料，結束。")
        raise SystemExit(0)

    save_to_postgres(route_records, stop_records, route_stop_records)

    print(f"\n{'='*50}")
    print("  完成！")
    print(f"{'='*50}\n")
