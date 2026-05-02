"""
static_speed_cameras.py - 雙北測速執法設置點資料管線
資料來源: https://data.gov.tw/dataset/7320 (測速執法設置點)
"""

import argparse
import csv
import io

import psycopg2
import requests
from psycopg2.extras import execute_batch

from config import PG_DASHBOARD

CSV_URL = (
    "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/"
    "EA5E6FCD-B82D-43B7-A5CF-E9893253187E/resource/"
    "4E5F713F-0ECC-4466-BFF3-A5C1287F7332/download"
)
TARGET_COUNTIES = {"臺北市", "新北市"}


# ── Step 1a: HTTP 抓取 ────────────────────────────────────────────────────────
def crawl() -> list[dict]:
    print("[爬蟲] 下載測速執法設置點 CSV ...")
    res = requests.get(CSV_URL, timeout=30, verify=False)
    res.raise_for_status()
    res.encoding = "utf-8-sig"  # 處理可能的 BOM
    rows = list(csv.DictReader(io.StringIO(res.text)))
    print(f"[爬蟲] 取得 {len(rows)} 筆原始資料")
    return rows


# ── Step 1b: 本地 CSV 載入（offline 測試用） ──────────────────────────────────
def load_sample(path: str) -> list[dict]:
    print(f"[Sample] 讀取本地 CSV：{path}")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ── Step 2: 預處理 ───────────────────────────────────────────────────────────
def preprocess(rows: list[dict]) -> list[dict]:
    print("[預處理] 過濾雙北 + 正規化欄位 ...")
    records, skipped = [], 0

    for r in rows:
        city = (r.get("CityName") or "").strip()
        if city not in TARGET_COUNTIES:
            skipped += 1
            continue

        district = (r.get("RegionName") or "").strip()
        address = (r.get("Address") or "").strip()
        dept = (r.get("DeptNm") or "").strip()
        branch = (r.get("BranchNm") or "").strip()
        direction = (r.get("direct") or "").strip()

        if not address or not direction:
            skipped += 1
            continue

        # 排除區間測速（測平均速度的多點系統，與點測速性質不同）
        if "區間測速" in address or "區間測速" in direction:
            skipped += 1
            continue

        try:
            speed_limit = int((r.get("limit") or "").strip())
            latitude = float((r.get("Latitude") or "").strip())
            longitude = float((r.get("Longitude") or "").strip())
        except ValueError:
            skipped += 1
            continue

        records.append(
            {
                "city": city,
                "district": district,
                "address": address,
                "dept": dept,
                "branch": branch,
                "direction": direction,
                "speed_limit": speed_limit,
                "latitude": latitude,
                "longitude": longitude,
            }
        )

    print(f"[預處理] 雙北測速照相 {len(records)} 筆，過濾 {skipped} 筆")
    return records


# ── Step 3: 寫入 PostgreSQL ──────────────────────────────────────────────────
def save_to_postgres(records: list[dict]) -> None:
    print("[PostgreSQL] 連線中 ...")
    conn = psycopg2.connect(**PG_DASHBOARD)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.speed_cameras_tpe (
            ogc_fid       SERIAL PRIMARY KEY,
            city          VARCHAR(20),
            district      VARCHAR(20),
            address       TEXT             NOT NULL,
            dept          VARCHAR(50),
            branch        VARCHAR(50),
            direction     VARCHAR(50)      NOT NULL,
            speed_limit   SMALLINT         NOT NULL,
            latitude      DOUBLE PRECISION NOT NULL,
            longitude     DOUBLE PRECISION NOT NULL,
            data_time     TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _ctime        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            _mtime        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (city, district, address, direction, speed_limit)
        )
    """)

    # 覆蓋模式：先清空、再批次寫入，整段在單一 transaction 內原子提交
    # （避免 ON CONFLICT 衝突邏輯；每次執行的表狀態 ≡ 上游當下）
    cur.execute("TRUNCATE TABLE public.speed_cameras_tpe RESTART IDENTITY")

    execute_batch(
        cur,
        """
        INSERT INTO public.speed_cameras_tpe (
            city, district, address, dept, branch,
            direction, speed_limit, latitude, longitude
        ) VALUES (
            %(city)s, %(district)s, %(address)s, %(dept)s, %(branch)s,
            %(direction)s, %(speed_limit)s, %(latitude)s, %(longitude)s
        )
    """,
        records,
        page_size=500,
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"[PostgreSQL] 寫入完成（覆蓋 {len(records)} 筆）")


# ── 主程式 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="雙北測速執法設置點資料管線")
    parser.add_argument(
        "--mode",
        choices=["ondemand", "sample"],
        default="ondemand",
        help="ondemand=HTTP 抓取（預設）, sample=讀本地 CSV",
    )
    parser.add_argument("--sample-path", default="")
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  Speed Cameras Pipeline  |  mode={args.mode}")
    print(f"{'='*50}\n")

    if args.mode == "ondemand":
        rows = crawl()
    else:
        if not args.sample_path:
            print("[錯誤] sample 模式需提供 --sample-path")
            raise SystemExit(1)
        rows = load_sample(args.sample_path)

    records = preprocess(rows)
    if not records:
        print("[警告] 無有效雙北資料，結束。")
        raise SystemExit(0)

    save_to_postgres(records)

    print(f"\n{'='*50}")
    print("  完成！")
    print(f"{'='*50}\n")
