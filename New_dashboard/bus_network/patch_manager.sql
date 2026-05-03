-- =============================================================================
-- 組件：bus_network — 公車路線網路地圖疊圖 patch
--
-- 適用資料庫 : dashboardmanager（postgres-manager, port 5432）
-- 所有操作均為冪等，重複執行不會報錯。
--
-- 疊圖資料來源（需先執行 generate_geojson.py 產生）：
--   FE/public/mapData/bus_network_tpe.geojson
--   FE/public/mapData/bus_network_newtaipei.geojson
-- =============================================================================


ALTER TABLE public.component_maps
ADD COLUMN IF NOT EXISTS city varchar;


-- ── 1. component_maps（公車路線線段圖層）──────────────────────────────────────────
-- 顏色取自 GeoJSON 屬性 "color"（由 generate_geojson.py 以路線名稱 hash 生成）
INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property, city)
VALUES (
    120,
    'bus_network_tpe',
    '公車路線（臺北市）',
    'line',
    'geojson',
    NULL, NULL,
    '{"line-color":["get","color"],"line-opacity":0.75}'::json,
    '[{"key":"route_name","name":"路線"}]'::json,
    'taipei'
)
ON CONFLICT (id) DO UPDATE SET
    index    = EXCLUDED.index,
    title    = EXCLUDED.title,
    type     = EXCLUDED.type,
    source   = EXCLUDED.source,
    paint    = EXCLUDED.paint,
    property = EXCLUDED.property,
    city     = EXCLUDED.city;

INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property, city)
VALUES (
    121,
    'bus_network_newtaipei',
    '公車路線（新北市）',
    'line',
    'geojson',
    NULL, NULL,
    '{"line-color":["get","color"],"line-opacity":0.75}'::json,
    '[{"key":"route_name","name":"路線"}]'::json,
    'newtaipei'
)
ON CONFLICT (id) DO UPDATE SET
    index    = EXCLUDED.index,
    title    = EXCLUDED.title,
    type     = EXCLUDED.type,
    source   = EXCLUDED.source,
    paint    = EXCLUDED.paint,
    property = EXCLUDED.property,
    city     = EXCLUDED.city;


-- ── 2. 確保 bus_transfer 的 component_charts / components 存在 ─────────────────
INSERT INTO public.component_charts (index, color, types, unit)
VALUES (
    'bus_transfer',
    '{#2979FF,#00BFA5,#FF6D00,#AA00FF,#00C853,#D50000,#2962FF,#00BCD4}',
    '{BusTransferChart}',
    ''
)
ON CONFLICT (index) DO NOTHING;

INSERT INTO public.components (id, index, name)
VALUES (305, 'bus_transfer', '公車轉乘查詢')
ON CONFLICT DO NOTHING;


-- ── 3. 將地圖疊圖連結到 bus_route query_charts（taipei）────────────────────────
UPDATE public.query_charts
SET
    map_config_ids = CASE
        WHEN map_config_ids @> ARRAY[120]::integer[] THEN map_config_ids
        WHEN map_config_ids IS NULL                  THEN ARRAY[120]::integer[]
        ELSE array_append(map_config_ids, 120)
    END,
    map_filter = '{"mode":"byParam","byParam":{"xParam":"route_name"}}'::json
WHERE index = 'bus_route' AND city = 'taipei';


-- ── 4. 將地圖疊圖連結到 bus_route query_charts（metrotaipei）──────────────────
UPDATE public.query_charts
SET
    map_config_ids = (
        SELECT ARRAY_AGG(DISTINCT x ORDER BY x)
        FROM UNNEST(COALESCE(map_config_ids, '{}') || ARRAY[120, 121]::integer[]) AS t(x)
    ),
    map_filter = '{"mode":"byParam","byParam":{"xParam":"route_name"}}'::json
WHERE index = 'bus_route' AND city = 'metrotaipei';


-- ── 5. 清除 bus_transfer 的 map_config_ids（疊圖已移到 bus_route）─────────────
UPDATE public.query_charts
SET map_config_ids = NULL
WHERE index = 'bus_transfer';


-- ── 6. dashboards（bus_transfer 轉乘查詢入口）────────────────────────────────────
INSERT INTO public.dashboards (id, index, name, components, icon, updated_at, created_at)
VALUES
    (374, 'bus_transfer_tpe',    '公車轉乘查詢', '{305}', 'alt_route',
     '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00'),
    (375, 'bus_transfer_newtpe', '公車轉乘查詢', '{305}', 'alt_route',
     '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00')
ON CONFLICT (id) DO NOTHING;


-- ── 7. dashboard_groups（group 2 = taipei, group 3 = metrotaipei）──────────────
INSERT INTO public.dashboard_groups (dashboard_id, group_id)
VALUES (374, 2), (375, 3)
ON CONFLICT DO NOTHING;
