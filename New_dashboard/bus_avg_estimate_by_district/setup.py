"""
bus_avg_estimate_by_district/setup.py — 行政區公車平均候車時間組件安裝腳本

前置條件:
  bus_stop_by_district 組件已安裝（bus_stop_tpe / bus_route_stops_tpe 已存在）。

步驟:
  1. 爬取雙北公車預估到站時間，寫入 bus_estimate_time_tpe
  2. 產生 GeoJSON 檔案至 FE public/mapData/
  3. 對 dashboardmanager 執行 patch_manager.sql
"""
import os
import sys
from pathlib import Path

ROOT          = Path(__file__).parent.parent.parent
DE_PREPROCESS = ROOT / "Taipei-City-Dashboard-DE" / "data_preprocess"
sys.path.insert(0, str(DE_PREPROCESS))

# 載入 docker/.env（被 .gitignore 排除；找不到時回退預設密碼 icta）
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
    print("[提示] 找不到 docker/.env，使用預設密碼 (icta)。")
    os.environ.setdefault("DB_MANAGER_PASSWORD", "icta")
    os.environ.setdefault("DB_DASHBOARD_PASSWORD", "icta")

import psycopg2
from config import PG_MANAGER


def _banner(title: str) -> None:
    print(f"\n{'='*52}\n  {title}\n{'='*52}")


# ── Step 1：公車預估到站時間 ──────────────────────────────────────────────────────
_banner("Step 1 / 3 — 公車預估到站時間爬取與寫入")

import periodic_bus_estimate_time as _est
_rows    = _est.crawl()
_records = _est.preprocess(_rows)
if not _records:
    print("[警告] 無預估到站資料，跳過 Step 1。")
else:
    _est.save_to_postgres(_records)


# ── Step 2：產生 GeoJSON ──────────────────────────────────────────────────────
_banner("Step 2 / 3 — 產生公車站點 GeoJSON（mapview 用）")
_est.generate_geojson()


# ── Step 3：dashboardmanager patch ──────────────────────────────────────────────
_banner("Step 3 / 3 — Dashboard 設定寫入 dashboardmanager")

_sql  = (Path(__file__).parent / "patch_manager.sql").read_text(encoding="utf-8")
_conn = psycopg2.connect(**PG_MANAGER)
_cur  = _conn.cursor()
_cur.execute(_sql)
_conn.commit()
_cur.close()
_conn.close()
print("[完成] dashboardmanager patch 執行成功")


_banner("組件安裝完成：bus_avg_estimate_by_district")
print("  重新整理瀏覽器即可在側邊欄看到「公車候車時間」Dashboard。")
print(f"{'='*52}\n")
