-- =============================================================================
-- 組件：bus_avg_estimate_by_district — dashboardmanager 差異 patch
--
-- 適用資料庫 : dashboardmanager（postgres-manager, port 5432）
-- 所有操作均為冪等，重複執行不會報錯。
-- =============================================================================


-- ── 1. component_charts ───────────────────────────────────────────────────────
INSERT INTO public.component_charts (index, color, types, unit)
VALUES (
    'bus_avg_estimate_by_district',
    '{#ef4444,#f97316,#eab308,#22c55e,#3b82f6,#8b5cf6,#ec4899,#06b6d4}',
    '{DistrictChart,ColumnChart}',
    '分'
)
ON CONFLICT (index) DO NOTHING;


-- ── 2. components ─────────────────────────────────────────────────────────────
INSERT INTO public.components (id, index, name)
VALUES (302, 'bus_avg_estimate_by_district', '行政區公車平均候車時間')
ON CONFLICT (id) DO NOTHING;


-- ── 3. component_maps（公車站點圓點圖層）──────────────────────────────────────────
-- 顏色：灰=無資料, 紅=<3分, 橙=<6分, 黃=<10分, 綠=>10分
INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property)
VALUES (
    110,
    'bus_stop_estimate_tpe',
    '公車站點',
    'circle',
    'geojson',
    NULL, NULL,
    '{"circle-radius":4,"circle-opacity":0.8,"circle-color":["case",["<",["get","nearest_estimate_min"],0],"#94a3b8",["<=",["get","nearest_estimate_min"],3],"#ef4444",["<=",["get","nearest_estimate_min"],6],"#f97316",["<=",["get","nearest_estimate_min"],10],"#eab308","#22c55e"]}',
    '[{"key":"stop_name","name":"站牌名稱"},{"key":"district","name":"行政區"},{"key":"geo_city","name":"城市"},{"key":"nearest_estimate_min","name":"最近到站(分)"}]'
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property)
VALUES (
    111,
    'bus_stop_estimate_metrotaipei',
    '公車站點',
    'circle',
    'geojson',
    NULL, NULL,
    '{"circle-radius":4,"circle-opacity":0.8,"circle-color":["case",["<",["get","nearest_estimate_min"],0],"#94a3b8",["<=",["get","nearest_estimate_min"],3],"#ef4444",["<=",["get","nearest_estimate_min"],6],"#f97316",["<=",["get","nearest_estimate_min"],10],"#eab308","#22c55e"]}',
    '[{"key":"stop_name","name":"站牌名稱"},{"key":"district","name":"行政區"},{"key":"geo_city","name":"城市"},{"key":"nearest_estimate_min","name":"最近到站(分)"}]'
)
ON CONFLICT (id) DO NOTHING;


-- ── 4. query_charts ───────────────────────────────────────────────────────────
INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'bus_avg_estimate_by_district', NULL, '{110}', NULL,
    'current', NULL, 5, 'minute',
    'tcgbusfs', '各行政區公車平均候車時間（臺北市）',
    '依行政區統計臺北市公車站牌的平均預估到站時間（僅計算有發車的班次）。',
    '可用於分析各行政區公車服務頻率與候車便利性差異。',
    '{}', '{}',
    '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00',
    'two_d',
    'SELECT bst.district AS x_axis,
       ROUND(AVG(bet.estimate_time) / 60.0, 1) AS data
FROM public.bus_estimate_time_tpe bet
JOIN public.bus_route_stops_tpe brs
     ON bet.city = brs.city AND bet.stop_id = brs.stop_id
JOIN public.bus_stop_tpe bst
     ON brs.city = bst.city AND brs.stop_location_id = bst.stop_location_id
WHERE bet.estimate_time > 0
  AND bst.geo_city = ''臺北市''
  AND bst.district IS NOT NULL
GROUP BY bst.district
ORDER BY data',
    NULL, 'taipei'
WHERE NOT EXISTS (
    SELECT 1 FROM public.query_charts
    WHERE index = 'bus_avg_estimate_by_district' AND city = 'taipei'
);

INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'bus_avg_estimate_by_district', NULL, '{110,111}', NULL,
    'current', NULL, 5, 'minute',
    'tcgbusfs/ntpcbus', '各行政區公車平均候車時間（雙北）',
    '依行政區統計雙北公車站牌的平均預估到站時間（僅計算有發車的班次）。',
    '可用於比較雙北各行政區公車服務頻率與候車便利性差異。',
    '{}', '{}',
    '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00',
    'two_d',
    'SELECT bst.district AS x_axis,
       ROUND(AVG(bet.estimate_time) / 60.0, 1) AS data
FROM public.bus_estimate_time_tpe bet
JOIN public.bus_route_stops_tpe brs
     ON bet.city = brs.city AND bet.stop_id = brs.stop_id
JOIN public.bus_stop_tpe bst
     ON brs.city = bst.city AND brs.stop_location_id = bst.stop_location_id
WHERE bet.estimate_time > 0
  AND bst.district IS NOT NULL
GROUP BY bst.district
ORDER BY data',
    NULL, 'metrotaipei'
WHERE NOT EXISTS (
    SELECT 1 FROM public.query_charts
    WHERE index = 'bus_avg_estimate_by_district' AND city = 'metrotaipei'
);


-- ── 5. dashboards ─────────────────────────────────────────────────────────────
INSERT INTO public.dashboards (id, index, name, components, icon, updated_at, created_at)
VALUES
    (372, 'bus_estimate_tpe',    '公車候車時間', '{302}', 'directions_bus',
     '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00'),
    (373, 'bus_estimate_newtpe', '公車候車時間', '{302}', 'directions_bus',
     '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00')
ON CONFLICT (id) DO NOTHING;


-- ── 6. dashboard_groups ───────────────────────────────────────────────────────
INSERT INTO public.dashboard_groups (dashboard_id, group_id)
VALUES (372, 2), (373, 3)
ON CONFLICT DO NOTHING;
