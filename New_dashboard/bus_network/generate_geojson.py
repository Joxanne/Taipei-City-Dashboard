"""
bus_network/generate_geojson.py — 公車路線網路 GeoJSON 產生器

依 bus_route_tpe / bus_route_stops_tpe / bus_stop_tpe 三張表，
將每條路線的去程站牌座標依序連成 LineString，
並以與前端 BusTransferChart.vue 的 routeColor() 相同的 HSL→hex 演算法賦予繽紛色彩。

輸出：
  FE/public/mapData/bus_network_tpe.geojson        （臺北市）
  FE/public/mapData/bus_network_newtaipei.geojson  （新北市）

執行：
  python generate_geojson.py
"""

from __future__ import annotations

import colorsys
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT   = Path(__file__).parent.parent.parent
FE_MAP = ROOT / "Taipei-City-Dashboard-FE" / "public" / "mapData"

# ── 確保 config 可匯入 ──────────────────────────────────────────────────────────
_DE = ROOT / "Taipei-City-Dashboard-DE" / "data_preprocess"
if str(_DE) not in sys.path:
    sys.path.insert(0, str(_DE))

_env_path = ROOT / "docker" / ".env"
if _env_path.exists():
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())
else:
    os.environ.setdefault("DB_DASHBOARD_PASSWORD", "icta")

import psycopg2
from config import PG_DASHBOARD


def route_color(route_name: str) -> str:
    """
    前端 routeColor() 的 Python 等效版本。
    JavaScript 的位元運算為 32-bit 有號整數，須模擬溢位行為。
    """
    h = 0
    for ch in route_name:
        h = ord(ch) + ((h << 5) - h)
        h &= 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    hue = abs(h) % 360
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.55, 0.70)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


_QUERY = """
SELECT
    br.route_name,
    brs.stop_seq,
    COALESCE(bs.longitude, 0) AS lon,
    COALESCE(bs.latitude,  0) AS lat
FROM public.bus_route_tpe        br
JOIN public.bus_route_stops_tpe  brs ON br.route_id = brs.route_id
JOIN public.bus_stop_tpe         bs  ON brs.stop_location_id = bs.stop_location_id
WHERE brs.go_back = 0
  AND bs.latitude  IS NOT NULL AND bs.latitude  <> 0
  AND bs.longitude IS NOT NULL AND bs.longitude <> 0
  AND bs.geo_city = %s
ORDER BY br.route_name, brs.stop_seq
"""


def build_geojson(city_zh: str) -> dict:
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur  = conn.cursor()
    cur.execute(_QUERY, (city_zh,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    route_coords: dict[str, list[list[float]]] = defaultdict(list)
    for route_name, _seq, lon, lat in rows:
        route_coords[route_name].append([lon, lat])

    features = []
    for route_name, coords in route_coords.items():
        if len(coords) < 2:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "route_name": route_name,
                "color": route_color(route_name),
            },
            "geometry": {
                "type": "LineString",
                "coordinates": coords,
            },
        })

    return {"type": "FeatureCollection", "features": features}


def generate(city_zh: str, out_path: Path) -> None:
    print(f"  查詢 {city_zh} 路線座標…")
    geojson = build_geojson(city_zh)
    n = len(geojson["features"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(geojson, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"  [完成] {n} 條路線 → {out_path}")


if __name__ == "__main__":
    generate("臺北市", FE_MAP / "bus_network_tpe.geojson")
    generate("新北市", FE_MAP / "bus_network_newtaipei.geojson")
