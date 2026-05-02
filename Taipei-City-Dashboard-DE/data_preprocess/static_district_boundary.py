"""
static_district_boundary.py - 行政區界多邊形匯入管線
資料來源: Taipei-City-Dashboard-FE/public/mapData/metrotaipei_town.geojson
寫入兩張表（供 spatial_area_mapping 與 bus_stop enrichment 使用）:
  public.tp_district  - 臺北市各區 (tname, wkb_geometry)
  public.tw_village   - 新北市各區 (town_name, county_name, wkb_geometry)
"""
import argparse
import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

_GEOJSON_PATH = (
    Path(__file__).parent.parent.parent
    / "Taipei-City-Dashboard-FE"
    / "public"
    / "mapData"
    / "metrotaipei_town.geojson"
)

_TAIPEI   = "臺北市"   # 臺北市
_NEWTAIPEI = "新北市"  # 新北市


# ── Step 1: 載入 GeoJSON ───────────────────────────────────────────────────────
def load_geojson(path: Path) -> list[dict]:
    print(f"[載入] {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    features = data.get("features", [])
    print(f"[載入] 共 {len(features)} 個行政區 feature")
    return features


# ── Step 2: 分城市預處理 ────────────────────────────────────────────────────────
def preprocess(features: list[dict]) -> tuple[list[dict], list[dict]]:
    tpe_records, ntpc_records = [], []
    for feat in features:
        props    = feat.get("properties", {})
        geom_str = json.dumps(feat["geometry"], ensure_ascii=False)
        pname    = props.get("PNAME", "")
        tname    = props.get("TNAME", "")
        if not tname or not feat.get("geometry"):
            continue
        if pname == _TAIPEI:
            tpe_records.append({"tname": tname, "geom": geom_str})
        elif pname == _NEWTAIPEI:
            ntpc_records.append({
                "town_name":   tname,
                "county_name": pname,
                "geom":        geom_str,
            })
    print(f"[預處理] 臺北市 {len(tpe_records)} 區，新北市 {len(ntpc_records)} 區")
    return tpe_records, ntpc_records


# ── Step 3: 寫入 PostgreSQL ────────────────────────────────────────────────────
def _save_tp_district(cur, records: list[dict]) -> None:
    cur.execute("DROP TABLE IF EXISTS public.tp_district")
    cur.execute("""
        CREATE TABLE public.tp_district (
            ogc_fid      SERIAL PRIMARY KEY,
            tname        VARCHAR(20) NOT NULL,
            wkb_geometry geometry(MultiPolygon, 4326),
            _ctime       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS tp_district_geom_idx ON public.tp_district USING GIST (wkb_geometry)")
    execute_batch(cur, """
        INSERT INTO public.tp_district (tname, wkb_geometry)
        VALUES (%(tname)s, ST_GeomFromGeoJSON(%(geom)s))
    """, records)
    print(f"[PostgreSQL] tp_district 寫入 {len(records)} 筆")


def _save_tw_village(cur, records: list[dict]) -> None:
    cur.execute("DROP TABLE IF EXISTS public.tw_village")
    cur.execute("""
        CREATE TABLE public.tw_village (
            ogc_fid      SERIAL PRIMARY KEY,
            town_name    VARCHAR(20) NOT NULL,
            county_name  VARCHAR(10) NOT NULL,
            wkb_geometry geometry(MultiPolygon, 4326),
            _ctime       TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS tw_village_geom_idx ON public.tw_village USING GIST (wkb_geometry)")
    execute_batch(cur, """
        INSERT INTO public.tw_village (town_name, county_name, wkb_geometry)
        VALUES (%(town_name)s, %(county_name)s, ST_GeomFromGeoJSON(%(geom)s))
    """, records)
    print(f"[PostgreSQL] tw_village 寫入 {len(records)} 筆")


def save_to_postgres(tpe_records: list[dict], ntpc_records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur  = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    _save_tp_district(cur, tpe_records)
    _save_tw_village(cur, ntpc_records)
    conn.commit()
    cur.close()
    conn.close()
    print("[PostgreSQL] 行政區界寫入完成")


# ── 主程式 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="行政區界多邊形匯入管線")
    parser.add_argument(
        "--geojson",
        default=str(_GEOJSON_PATH),
        help="metrotaipei_town.geojson 路徑（預設自動偵測）",
    )
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print("  District Boundary Pipeline")
    print(f"{'='*50}\n")

    features = load_geojson(Path(args.geojson))
    tpe_records, ntpc_records = preprocess(features)

    if not tpe_records and not ntpc_records:
        print("[警告] 無行政區資料，結束。")
        raise SystemExit(0)

    save_to_postgres(tpe_records, ntpc_records)

    print(f"\n{'='*50}")
    print("  完成！")
    print(f"{'='*50}\n")
