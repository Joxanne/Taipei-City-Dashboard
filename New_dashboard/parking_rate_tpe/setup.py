"""
parking_rate_tpe/setup.py — 路邊停車費率地圖疊層組件安裝腳本

前置條件:
  public.parking_rate_tpe 已由 data_preprocess/static_parking_rate_tpe.py 匯入 dashboard DB。

步驟:
  1. 從 parking_rate_tpe 產生 GeoJSON 檔案至 FE public/mapData/
  2. 對 dashboardmanager 執行 patch_manager.sql
"""
import os
import sys
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
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


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_config = _load_module("dashboard_preprocess_config", DE_PREPROCESS / "config.py")
PG_DASHBOARD = _config.PG_DASHBOARD
PG_MANAGER = _config.PG_MANAGER


def _banner(title: str) -> None:
    print(f"\n{'='*52}\n  {title}\n{'='*52}")


def _assert_data_ready() -> None:
    with psycopg2.connect(**PG_DASHBOARD) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name   = 'parking_rate_tpe'
                )
            """)
            if not cur.fetchone()[0]:
                raise SystemExit(
                    "[錯誤] 找不到 public.parking_rate_tpe；請先匯入 parking_rate_tpe_geocoded.csv。"
                )
            cur.execute("SELECT COUNT(*) FROM public.parking_rate_tpe")
            count = cur.fetchone()[0]
            if count == 0:
                raise SystemExit("[錯誤] public.parking_rate_tpe 無資料，請先匯入 CSV。")
            print(f"[確認] public.parking_rate_tpe 目前有 {count} 筆資料。")


# ── Step 1：產生 GeoJSON ──────────────────────────────────────────────────────
_banner("Step 1 / 2 — 產生停車費率 GeoJSON（mapview 用）")
_assert_data_ready()

_parking = _load_module("static_parking_rate_tpe", DE_PREPROCESS / "static_parking_rate_tpe.py")
_parking.generate_geojson()


# ── Step 2：dashboardmanager patch ──────────────────────────────────────────────
_banner("Step 2 / 2 — Dashboard 設定寫入 dashboardmanager")

_sql = (Path(__file__).parent / "patch_manager.sql").read_text(encoding="utf-8")
_conn = psycopg2.connect(**PG_MANAGER)
_cur = _conn.cursor()
_cur.execute(_sql)
_conn.commit()
_cur.close()
_conn.close()
print("[完成] dashboardmanager patch 執行成功")


_banner("組件安裝完成：parking_rate_tpe")
print("  重新整理瀏覽器即可在側邊欄看到「路邊停車費率」Dashboard。")
print(f"{'='*52}\n")
