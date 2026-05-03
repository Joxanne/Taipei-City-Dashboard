"""
speeding_casualty_district/setup.py — 超速傷亡事故行政區計數組件安裝腳本

執行方式：
  python setup.py                   # 從本目錄直接執行
  python New_dashboard/setup.py speeding_casualty_district  # 由根目錄呼叫

步驟：
  1. 對 dashboardmanager 執行 patch_manager.sql
"""

import os
import sys
from pathlib import Path

import sys

ROOT = Path(__file__).parent.parent.parent
DE_PREPROCESS = ROOT / "Taipei-City-Dashboard-DE" / "data_preprocess"
FE_MAPDATA = ROOT / "Taipei-City-Dashboard-FE" / "public" / "mapData"
GEOJSON_PATH = FE_MAPDATA / "speeding_casualty_points_tpe.geojson"

sys.path.insert(0, str(DE_PREPROCESS))


import psycopg2

from config import PG_MANAGER


def _banner(title: str) -> None:
    print(f"\n{'='*52}\n  {title}\n{'='*52}")


_banner("Step 1 / 1 — Dashboard 設定寫入 dashboardmanager")

_sql = (Path(__file__).parent / "patch_manager.sql").read_text(encoding="utf-8")
_conn = psycopg2.connect(**PG_MANAGER)
_cur = _conn.cursor()
_cur.execute(_sql)
_conn.commit()
_cur.close()
_conn.close()
print("[完成] dashboardmanager patch 執行成功")


_banner("組件安裝完成：speeding_casualty_district")
print("  重新整理瀏覽器即可在側邊欄看到「超速傷亡事故」Dashboard。")
print(f"{'='*52}\n")
