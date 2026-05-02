"""
speeding_casualty_points_tpe/setup.py — 超速傷亡事故點位組件安裝腳本

執行方式：
  python setup.py
  python New_dashboard/setup.py speeding_casualty_points_tpe

步驟：
  1. 更新 public.speeding_casualty_points_tpe
  2. 匯出前端地圖 GeoJSON
  3. 對 dashboardmanager 執行 patch_manager.sql
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DE_PREPROCESS = ROOT / "Taipei-City-Dashboard-DE" / "data_preprocess"
FE_MAPDATA = ROOT / "Taipei-City-Dashboard-FE" / "public" / "mapData"
GEOJSON_PATH = FE_MAPDATA / "speeding_casualty_points_tpe.geojson"

sys.path.insert(0, str(DE_PREPROCESS))

import psycopg2
from config import PG_MANAGER
import static_speeding_casualty_points_tpe as _points


def _banner(title: str) -> None:
    print(f"\n{'=' * 52}\n  {title}\n{'=' * 52}")


def _format_accident_time(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def export_geojson(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    features = []
    for record in records:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "district": record["district"],
                    "location_text": record["location_text"],
                    "accident_time": _format_accident_time(record["accident_time"]),
                    "death_count": int(record["death_count"]),
                    "injury_count": int(record["injury_count"]),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [record["longitude"], record["latitude"]],
                },
            }
        )

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }
    output_path.write_text(json.dumps(geojson, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[完成] GeoJSON 已輸出：{output_path}")


_banner("Step 1 / 3 — 超速傷亡事故點位資料更新")
_rows = _points.crawl([112, 113, 114])
if not _rows:
    print("[錯誤] 無原始資料，結束")
    raise SystemExit(1)

_records = _points.preprocess(_rows)
if not _records:
    print("[警告] 無有效資料，跳過安裝")
    raise SystemExit(0)

_points.save_to_postgres(_records)


_banner("Step 2 / 3 — 匯出前端地圖 GeoJSON")
export_geojson(_records, GEOJSON_PATH)


_banner("Step 3 / 3 — Dashboard 設定寫入 dashboardmanager")
_sql = (Path(__file__).parent / "patch_manager.sql").read_text(encoding="utf-8")
_conn = psycopg2.connect(**PG_MANAGER)
_cur = _conn.cursor()
_cur.execute(_sql)
_conn.commit()
_cur.close()
_conn.close()
print("[完成] dashboardmanager patch 執行成功")


_banner("組件安裝完成：speeding_casualty_points_tpe")
print("  重新整理瀏覽器即可在雙北儀表板看到「超速傷亡事故點位」。")
print(f"{'=' * 52}\n")
