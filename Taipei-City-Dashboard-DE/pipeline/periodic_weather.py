"""
periodic_weather.py - 中央氣象署 定期天氣觀測資料管線
"""

import argparse
import json
import ssl
import urllib.request

import psycopg2
from psycopg2.extras import execute_batch

from config import CWA_API_KEY, PG_DASHBOARD

# ── 資料集設定 ─────────────────────────────────────────────────────────────────
CWA_DATASET = "O-A0001-001"
CWA_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/{}?Authorization={}&format=JSON"

# 過濾範圍：臺北市 + 新北市（大臺北地區）
TARGET_COUNTIES = {"臺北市", "新北市"}

# CWA 使用 -99 / -99.0 表示缺值
_NULL = {"-99", "-99.0", ""}


def _safe_float(val, *, null_val: float | None = None) -> float | None:
    """將 CWA 字串轉 float；遇缺值回傳 null_val。"""
    s = str(val).strip()
    if s in _NULL:
        return null_val
    try:
        return float(s)
    except (ValueError, TypeError):
        return null_val


# ── Step 1: 爬蟲 ──────────────────────────────────────────────────────────────
def crawl() -> list[dict]:
    if not CWA_API_KEY:
        raise RuntimeError("缺少 CWA_API_KEY，無法下載中央氣象署資料。")

    print("[爬蟲] 下載 CWA O-A0001-001 氣象觀測資料 ...")
    ctx = ssl._create_unverified_context()
    url = CWA_URL.format(CWA_DATASET, CWA_API_KEY)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, context=ctx, timeout=20)
    data = json.loads(res.read().decode("utf-8"))
    stations = data.get("records", {}).get("Station", [])
    print(f"[爬蟲] 取得 {len(stations)} 筆氣象站原始資料")
    return stations


# ── Step 2: 預處理 ─────────────────────────────────────────────────────────────
def preprocess(stations: list[dict]) -> list[dict]:
    print("[預處理] 過濾大臺北地區並正規化欄位 ...")
    records, skipped = [], 0

    for s in stations:
        geo = s.get("GeoInfo", {})
        county = geo.get("CountyName", "").strip()

        if county not in TARGET_COUNTIES:
            skipped += 1
            continue

        # 解析座標（WGS84 優先，fallback 第一組）
        lat, lon = None, None
        for coord in geo.get("Coordinates", []):
            if coord.get("CoordinateName") == "WGS84":
                lat = _safe_float(coord.get("StationLatitude"))
                lon = _safe_float(coord.get("StationLongitude"))
                break
        if lat is None:
            coords = geo.get("Coordinates", [])
            if coords:
                lat = _safe_float(coords[0].get("StationLatitude"))
                lon = _safe_float(coords[0].get("StationLongitude"))

        station_id = s.get("StationId", "").strip()
        name = s.get("StationName", "").strip()
        if not station_id or not name:
            skipped += 1
            continue

        we = s.get("WeatherElement", {})
        records.append(
            {
                "station_id": station_id,
                "station_name": name,
                "obs_time": s.get("ObsTime", {}).get("DateTime"),
                "county": county,
                "town": geo.get("TownName", "").strip(),
                "latitude": lat,
                "longitude": lon,
                "weather_desc": we.get("Weather", "").strip(),
                "temperature": _safe_float(we.get("AirTemperature")),
                "humidity": _safe_float(we.get("RelativeHumidity")),
                "wind_speed": _safe_float(we.get("WindSpeed")),
                "wind_direction": _safe_float(we.get("WindDirection")),
                "pressure": _safe_float(we.get("AirPressure")),
                "precipitation_now": _safe_float(we.get("Now", {}).get("Precipitation")),
                "daily_high": _safe_float(
                    we.get("DailyExtreme", {}).get("DailyHigh", {}).get("AirTemperature")
                ),
                "daily_low": _safe_float(
                    we.get("DailyExtreme", {}).get("DailyLow", {}).get("AirTemperature")
                ),
            }
        )

    print(f"[預處理] 大臺北氣象站 {len(records)} 筆，過濾 {skipped} 筆")
    return records


# ── Step 3: 寫入 PostgreSQL ────────────────────────────────────────────────────
def save_to_postgres(records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.weather_station_tpe (
            ogc_fid          SERIAL PRIMARY KEY,
            station_id       VARCHAR(20) UNIQUE NOT NULL,
            station_name     TEXT        NOT NULL,
            obs_time         TIMESTAMPTZ,
            county           VARCHAR(20),
            town             VARCHAR(30),
            latitude         DOUBLE PRECISION,
            longitude        DOUBLE PRECISION,
            weather_desc     TEXT,
            temperature      REAL,
            humidity         REAL,
            wind_speed       REAL,
            wind_direction   REAL,
            pressure         REAL,
            precipitation_now REAL,
            daily_high       REAL,
            daily_low        REAL,
            data_time        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        )
    """)

    execute_batch(
        cur,
        """
        INSERT INTO public.weather_station_tpe (
            station_id, station_name, obs_time,
            county, town, latitude, longitude,
            weather_desc, temperature, humidity,
            wind_speed, wind_direction, pressure,
            precipitation_now, daily_high, daily_low,
            data_time, _mtime
        ) VALUES (
            %(station_id)s, %(station_name)s, %(obs_time)s,
            %(county)s, %(town)s, %(latitude)s, %(longitude)s,
            %(weather_desc)s, %(temperature)s, %(humidity)s,
            %(wind_speed)s, %(wind_direction)s, %(pressure)s,
            %(precipitation_now)s, %(daily_high)s, %(daily_low)s,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (station_id) DO UPDATE SET
            obs_time          = EXCLUDED.obs_time,
            weather_desc      = EXCLUDED.weather_desc,
            temperature       = EXCLUDED.temperature,
            humidity          = EXCLUDED.humidity,
            wind_speed        = EXCLUDED.wind_speed,
            wind_direction    = EXCLUDED.wind_direction,
            pressure          = EXCLUDED.pressure,
            precipitation_now = EXCLUDED.precipitation_now,
            daily_high        = EXCLUDED.daily_high,
            daily_low         = EXCLUDED.daily_low,
            data_time         = EXCLUDED.data_time,
            _mtime            = EXCLUDED._mtime
    """,
        records,
        page_size=200,
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"[PostgreSQL] 寫入完成（{len(records)} 筆）")


# ── 主程式 ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="中央氣象署天氣觀測資料入庫管線")
    parser.add_argument(
        "--mode",
        choices=["periodic", "ondemand"],
        default="ondemand",
        help="periodic=定期排程, ondemand=手動觸發",
    )
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  Weather Pipeline  |  mode={args.mode}")
    print(f"{'='*50}\n")

    stations = crawl()
    records = preprocess(stations)
    if not records:
        print("[警告] 無符合大臺北地區的氣象站資料，結束。")
        raise SystemExit(0)

    save_to_postgres(records)

    print(f"\n{'='*50}")
    print("  完成！")
    print(f"{'='*50}\n")
