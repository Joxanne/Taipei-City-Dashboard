-- =============================================================================
-- 組件：bus_stop_by_district — dashboardmanager 差異 patch
--
-- 適用資料庫 : dashboardmanager（postgres-manager, port 5432）
-- 可在 pgAdmin (http://localhost:8889) 開啟對應資料庫後直接貼上執行，
-- 或由 setup.py / 根目錄 setup.py 自動呼叫。
-- 所有 INSERT 均為冪等操作，重複執行不會報錯。
-- =============================================================================


-- ── 1. component_charts ───────────────────────────────────────────────────────
INSERT INTO public.component_charts (index, color, types, unit)
VALUES (
    'bus_stop_by_district',
    '{#0EA5E9,#0284C7,#0369A1,#075985,#0C4A6E,#BAE6FD,#7DD3FC,#38BDF8}',
    '{DistrictChart,ColumnChart}',
    '站'
)
ON CONFLICT (index) DO NOTHING;


-- ── 2. components ─────────────────────────────────────────────────────────────
INSERT INTO public.components (id, index, name)
VALUES (301, 'bus_stop_by_district', '行政區公車站牌數量')
ON CONFLICT (id) DO NOTHING;


-- ── 3. query_charts（用 WHERE NOT EXISTS，因為該表無唯一索引）────────────────────
INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'bus_stop_by_district', NULL, NULL, NULL,
    'static', NULL, NULL, NULL,
    'tcgbusfs', '各行政區公車站牌數量（臺北市）',
    '依行政區統計臺北市公車物理站牌數量，反映各區公車服務覆蓋密度。',
    '可用於分析各行政區的公車服務分布情形，輔助交通資源規劃。',
    '{}', '{}',
    '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00',
    'two_d',
    'SELECT district AS x_axis, COUNT(*) AS data
FROM public.bus_stop_tpe
WHERE city = ''臺北市'' AND district IS NOT NULL
GROUP BY district ORDER BY data DESC',
    NULL, 'taipei'
WHERE NOT EXISTS (
    SELECT 1 FROM public.query_charts
    WHERE index = 'bus_stop_by_district' AND city = 'taipei'
);

INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'bus_stop_by_district', NULL, NULL, NULL,
    'static', NULL, NULL, NULL,
    'tcgbusfs/ntpcbus', '各行政區公車站牌數量（雙北）',
    '依行政區統計雙北公車物理站牌數量，反映各區公車服務覆蓋密度。',
    '可用於分析各行政區的公車服務分布情形，輔助交通資源規劃。',
    '{}', '{}',
    '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00',
    'two_d',
    'SELECT district AS x_axis, COUNT(*) AS data
FROM public.bus_stop_tpe
WHERE district IS NOT NULL
GROUP BY district ORDER BY data DESC',
    NULL, 'metrotaipei'
WHERE NOT EXISTS (
    SELECT 1 FROM public.query_charts
    WHERE index = 'bus_stop_by_district' AND city = 'metrotaipei'
);


-- ── 4. dashboards ─────────────────────────────────────────────────────────────
INSERT INTO public.dashboards (id, index, name, components, icon, updated_at, created_at)
VALUES
    (370, 'bus_stop_tpe',    '公車站牌分布', '{301}', 'directions_bus',
     '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00'),
    (371, 'bus_stop_newtpe', '公車站牌分布', '{301}', 'directions_bus',
     '2025-01-01 00:00:00+00', '2025-01-01 00:00:00+00')
ON CONFLICT (id) DO NOTHING;


-- ── 5. dashboard_groups ───────────────────────────────────────────────────────
-- group 2 = taipei（臺北市）、group 3 = metrotaipei（雙北）
INSERT INTO public.dashboard_groups (dashboard_id, group_id)
VALUES (370, 2), (371, 3)
ON CONFLICT DO NOTHING;
