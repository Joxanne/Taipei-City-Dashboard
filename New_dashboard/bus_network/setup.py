"""
bus_network/setup.py — 公車路線網路地圖疊圖安裝腳本

執行方式：
  python setup.py                         # 從本目錄直接執行
  python New_dashboard/setup.py bus_network  # 由根目錄呼叫

步驟：
  1. 產生 bus_network_tpe.geojson / bus_network_newtaipei.geojson（連接各路線站牌座標）
  2. 對 dashboardmanager 執行 patch_manager.sql（新增地圖圖層設定、建立 bus_transfer 組件）

前置條件：
  bus_stop_by_district 組件已安裝（bus_route_tpe / bus_route_stops_tpe / bus_stop_tpe 已存在）
"""

import os
import sys
from pathlib import Path

ROOT          = Path(__file__).parent.parent.parent
DE_PREPROCESS = ROOT / "Taipei-City-Dashboard-DE" / "data_preprocess"
sys.path.insert(0, str(DE_PREPROCESS))
sys.path.insert(0, str(Path(__file__).parent))

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
import generate_geojson as _gen


def _banner(title: str) -> None:
    print(f"\n{'='*52}\n  {title}\n{'='*52}")


# ── Step 1：產生 GeoJSON ───────────────────────────────────────────────────────
_banner("Step 1 / 2 — 產生公車路線網路 GeoJSON")

_gen.generate("臺北市", _gen.FE_MAP / "bus_network_tpe.geojson")
_gen.generate("新北市", _gen.FE_MAP / "bus_network_newtaipei.geojson")


# ── Step 2：dashboardmanager patch ────────────────────────────────────────────
_banner("Step 2 / 2 — Dashboard 設定寫入 dashboardmanager")

_sql  = (Path(__file__).parent / "patch_manager.sql").read_text(encoding="utf-8")
_conn = psycopg2.connect(**PG_MANAGER)
_cur  = _conn.cursor()
_cur.execute(_sql)
_conn.commit()
_cur.close()
_conn.close()
print("[完成] dashboardmanager patch 執行成功")


_banner("組件安裝完成：bus_network")
print("  執行後請重新整理瀏覽器，在公車轉乘查詢組件開啟[地圖交叉比對]")
print("  即可看到以繽紛顏色繪製的雙北公車路線疊圖。")
print(f"{'='*52}\n")
