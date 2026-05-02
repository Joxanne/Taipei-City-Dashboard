"""
bus_stop_by_district/setup.py — 公車站牌分布組件安裝腳本

執行方式：
  python setup.py                   # 從本目錄直接執行
  python New_dashboard/setup.py bus_stop_by_district  # 由根目錄呼叫

步驟：
  1. 建立行政區界表 public.tp_district / public.tw_village
  2. 爬取雙北公車路線與站牌，寫入 public.bus_stop_tpe 等三張表
  3. 對 dashboardmanager 執行 patch_manager.sql
"""
import os
import sys
from pathlib import Path

ROOT          = Path(__file__).parent.parent.parent
DE_PREPROCESS = ROOT / "Taipei-City-Dashboard-DE" / "data_preprocess"
sys.path.insert(0, str(DE_PREPROCESS))

# docker/.env 被 .gitignore 排除，clone 後不存在；在 config 載入前先補上預設值。
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
    print("[提示] 找不到 docker/.env，使用專案預設密碼 (icta)。")
    print("       若您的密碼不同，請先設定環境變數：")
    print("         Windows: set DB_MANAGER_PASSWORD=your_password")
    print("         Linux/Mac: export DB_MANAGER_PASSWORD=your_password\n")
    os.environ.setdefault("DB_MANAGER_PASSWORD", "icta")
    os.environ.setdefault("DB_DASHBOARD_PASSWORD", "icta")

import psycopg2
from config import PG_MANAGER


def _banner(title: str) -> None:
    print(f"\n{'='*52}\n  {title}\n{'='*52}")


# ── Step 1：行政區界 ─────────────────────────────────────────────────────────────
_banner("Step 1 / 3 — 行政區界表 (tp_district / tw_village)")

import static_district_boundary as _dist
_features = _dist.load_geojson(_dist._GEOJSON_PATH)
_tpe_rec, _ntpc_rec = _dist.preprocess(_features)
_dist.save_to_postgres(_tpe_rec, _ntpc_rec)


# ── Step 2：公車站牌資料 ─────────────────────────────────────────────────────────
_banner("Step 2 / 3 — 公車路線 / 站牌資料爬取與寫入")

import static_bus_stops as _stops
_route_rows, _stop_rows    = _stops.crawl()
_route_records             = _stops.preprocess_routes(_route_rows)
_stop_records, _rs_records = _stops.preprocess_stops(_stop_rows)

if not _stop_records:
    print("[警告] 無站牌資料，跳過 Step 2。")
else:
    _stops.save_to_postgres(_route_records, _stop_records, _rs_records)


# ── Step 3：dashboardmanager patch ──────────────────────────────────────────────
_banner("Step 3 / 3 — Dashboard 設定寫入 dashboardmanager")

_sql = (Path(__file__).parent / "patch_manager.sql").read_text(encoding="utf-8")
_conn = psycopg2.connect(**PG_MANAGER)
_cur  = _conn.cursor()
_cur.execute(_sql)
_conn.commit()
_cur.close()
_conn.close()
print("[完成] dashboardmanager patch 執行成功")


_banner("組件安裝完成：bus_stop_by_district")
print("  重新整理瀏覽器即可在側邊欄看到「公車站牌分布」Dashboard。")
print(f"{'='*52}\n")
