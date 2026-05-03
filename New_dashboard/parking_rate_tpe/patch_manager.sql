-- =============================================================================
-- 組件：parking_rate_tpe — dashboardmanager 差異 patch
--
-- 適用資料庫 : dashboardmanager（postgres-manager, port 5432）
-- 需搭配 FE public/mapData/parking_rate_tpe.geojson 與
-- public/mapData/parking_rate_metrotaipei.geojson。
-- =============================================================================


ALTER TABLE public.component_maps
ADD COLUMN IF NOT EXISTS city varchar;


-- ── 1. component_charts ───────────────────────────────────────────────────────
INSERT INTO public.component_charts (index, color, types, unit)
VALUES (
    'parking_rate_tpe',
    '{#22C55E,#F97316,#EF4444,#94A3B8}',
    '{MapLegend}',
    '路段'
)
ON CONFLICT (index) DO UPDATE SET
    color = EXCLUDED.color,
    types = EXCLUDED.types,
    unit = EXCLUDED.unit;

INSERT INTO public.component_charts (index, color, types, unit)
VALUES (
    'parking_rate_tpe_district_median',
    '{#3B82F6,#60A5FA,#93C5FD,#BFDBFE}',
    '{DistrictChart,ColumnChart}',
    '元/時'
)
ON CONFLICT (index) DO UPDATE SET
    color = EXCLUDED.color,
    types = EXCLUDED.types,
    unit = EXCLUDED.unit;


-- ── 2. components ─────────────────────────────────────────────────────────────
INSERT INTO public.components (id, index, name)
VALUES (504, 'parking_rate_tpe', '路邊停車費率')
ON CONFLICT (id) DO UPDATE SET
    index = EXCLUDED.index,
    name = EXCLUDED.name;

INSERT INTO public.components (id, index, name)
VALUES (506, 'parking_rate_tpe_district_median', '各行政區停車費率中位數統計')
ON CONFLICT (id) DO UPDATE SET
    index = EXCLUDED.index,
    name = EXCLUDED.name;


-- ── 3. component_maps（停車費率道路線圖層）───────────────────────────────────────
INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property, city)
VALUES (
    5041,
    'parking_rate_tpe',
    '路邊停車費率',
    'line',
    'geojson',
    NULL,
    NULL,
    '{
        "line-color": ["match", ["get", "rate_bucket"], "30元以下", "#22C55E", "31-50元", "#F97316", "50元以上", "#EF4444", "無平日收費", "#94A3B8", "#3B82F6"],
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.2, 14, 3, 18, 5],
        "line-opacity": 0.88
    }'::json,
    '[
        {"key":"city","name":"城市"},
        {"key":"district","name":"行政區"},
        {"key":"road_segment","name":"路段"},
        {"key":"segment_endpoints","name":"起迄路段"},
        {"key":"weekday_rate_text","name":"平日費率"},
        {"key":"saturday_rate_text","name":"週六費率"},
        {"key":"sunday_rate_text","name":"週日費率"},
        {"key":"holiday_rate_text","name":"國定假日費率"},
        {"key":"weekday_hours_text","name":"平日收費時間"},
        {"key":"rate_bucket","name":"費率級距"},
        {"key":"geometry_note","name":"圖資說明"}
    ]'::json,
    'taipei'
)
ON CONFLICT (id) DO UPDATE SET
    index = EXCLUDED.index,
    title = EXCLUDED.title,
    type = EXCLUDED.type,
    source = EXCLUDED.source,
    size = EXCLUDED.size,
    icon = EXCLUDED.icon,
    paint = EXCLUDED.paint,
    property = EXCLUDED.property,
    city = EXCLUDED.city;

INSERT INTO public.component_maps (id, index, title, type, source, size, icon, paint, property, city)
VALUES (
    5042,
    'parking_rate_metrotaipei',
    '路邊停車費率',
    'line',
    'geojson',
    NULL,
    NULL,
    '{
        "line-color": ["match", ["get", "rate_bucket"], "30元以下", "#22C55E", "31-50元", "#F97316", "50元以上", "#EF4444", "無平日收費", "#94A3B8", "#3B82F6"],
        "line-width": ["interpolate", ["linear"], ["zoom"], 10, 1.2, 14, 3, 18, 5],
        "line-opacity": 0.88
    }'::json,
    '[
        {"key":"city","name":"城市"},
        {"key":"district","name":"行政區"},
        {"key":"road_segment","name":"路段"},
        {"key":"segment_endpoints","name":"起迄路段"},
        {"key":"weekday_rate_text","name":"平日費率"},
        {"key":"saturday_rate_text","name":"週六費率"},
        {"key":"sunday_rate_text","name":"週日費率"},
        {"key":"holiday_rate_text","name":"國定假日費率"},
        {"key":"weekday_hours_text","name":"平日收費時間"},
        {"key":"rate_bucket","name":"費率級距"},
        {"key":"geometry_note","name":"圖資說明"}
    ]'::json,
    'metrotaipei'
)
ON CONFLICT (id) DO UPDATE SET
    index = EXCLUDED.index,
    title = EXCLUDED.title,
    type = EXCLUDED.type,
    source = EXCLUDED.source,
    size = EXCLUDED.size,
    icon = EXCLUDED.icon,
    paint = EXCLUDED.paint,
    property = EXCLUDED.property,
    city = EXCLUDED.city;


-- ── 4. query_charts（用 MapLegend 控制地圖圖層篩選）───────────────────────────────
DELETE FROM public.query_charts
WHERE index = 'parking_rate_tpe' AND city = 'taipei';

INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'parking_rate_tpe', NULL, '{5041}',
    '{"mode":"byParam","byParam":{"xParam":"rate_bucket","yParam":null}}'::json,
    'static', NULL, NULL, NULL,
    '臺北市交通局', '臺北市路邊停車費率道路疊層',
    '以道路線圖呈現臺北市路邊停車費率，依平日每小時費率分級著色。',
    '可用於觀察不同行政區及路段停車費率分布，輔助停車政策與交通需求分析。',
    '{https://data.taipei/dataset/detail?id=86d2a8b6-c360-4349-956d-dd7771cccf91}', '{doit}',
    '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00',
    'map_legend',
    'WITH bucket_order AS (
        SELECT * FROM (VALUES
            (''30元以下'', 1),
            (''31-50元'', 2),
            (''50元以上'', 3),
            (''無平日收費'', 4)
        ) AS v(name, ord)
    ), bucket_counts AS (
        SELECT
            CASE
                WHEN weekday_rate IS NULL THEN ''無平日收費''
                WHEN weekday_rate <= 30 THEN ''30元以下''
                WHEN weekday_rate <= 50 THEN ''31-50元''
                ELSE ''50元以上''
            END AS name,
            COUNT(*)::double precision AS value
        FROM public.parking_rate_tpe
        WHERE city = ''臺北市''
        GROUP BY 1
    )
    SELECT
        b.name,
        ''line'' AS type,
        '''' AS icon,
        COALESCE(c.value, 0)::double precision AS value
    FROM bucket_order b
    LEFT JOIN bucket_counts c ON b.name = c.name
    ORDER BY b.ord',
    NULL, 'taipei';

DELETE FROM public.query_charts
WHERE index = 'parking_rate_tpe' AND city = 'metrotaipei';

INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'parking_rate_tpe', NULL, '{5042}',
    '{"mode":"byParam","byParam":{"xParam":"rate_bucket","yParam":null}}'::json,
    'static', NULL, NULL, NULL,
    '臺北市交通局 / 新北市政府交通局', '雙北路邊停車費率道路疊層',
    '以道路線圖呈現雙北路邊停車費率，依平日每小時費率分級著色。',
    '可用於比較雙北停車費率空間分布，支援停車供需、費率分區與交通管理分析。',
    '{https://data.taipei/dataset/detail?id=86d2a8b6-c360-4349-956d-dd7771cccf91,https://data.ntpc.gov.tw/datasets/d9f18db5-41c7-41d4-b7f0-82a335255b08}', '{doit,ntpc}',
    '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00',
    'map_legend',
    'WITH bucket_order AS (
        SELECT * FROM (VALUES
            (''30元以下'', 1),
            (''31-50元'', 2),
            (''50元以上'', 3),
            (''無平日收費'', 4)
        ) AS v(name, ord)
    ), bucket_counts AS (
        SELECT
            CASE
                WHEN weekday_rate IS NULL THEN ''無平日收費''
                WHEN weekday_rate <= 30 THEN ''30元以下''
                WHEN weekday_rate <= 50 THEN ''31-50元''
                ELSE ''50元以上''
            END AS name,
            COUNT(*)::double precision AS value
        FROM public.parking_rate_tpe
        GROUP BY 1
    )
    SELECT
        b.name,
        ''line'' AS type,
        '''' AS icon,
        COALESCE(c.value, 0)::double precision AS value
    FROM bucket_order b
    LEFT JOIN bucket_counts c ON b.name = c.name
    ORDER BY b.ord',
    NULL, 'metrotaipei';

DELETE FROM public.query_charts
WHERE index = 'parking_rate_tpe_district_median' AND city = 'taipei';

INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'parking_rate_tpe_district_median', NULL, NULL,
    NULL,
    'static', NULL, NULL, NULL,
    '臺北市交通局', '各行政區路邊停車費率中位數（臺北市）',
    '以行政區統計臺北市路邊停車平日費率中位數。',
    '可用於觀察各行政區路邊停車費率分布差異，輔助停車收費政策分析。',
    '{https://data.taipei/dataset/detail?id=86d2a8b6-c360-4349-956d-dd7771cccf91}', '{doit}',
    '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00',
    'two_d',
    'SELECT
        district AS x_axis,
        ROUND(
            percentile_cont(0.5) WITHIN GROUP (ORDER BY weekday_rate)::numeric,
            1
        )::double precision AS data
    FROM public.parking_rate_tpe
    WHERE city = ''臺北市''
      AND district IS NOT NULL
      AND weekday_rate IS NOT NULL
    GROUP BY district
    ORDER BY data DESC, district',
    NULL, 'taipei';

DELETE FROM public.query_charts
WHERE index = 'parking_rate_tpe_district_median' AND city = 'metrotaipei';

INSERT INTO public.query_charts (
    index, history_config, map_config_ids, map_filter,
    time_from, time_to, update_freq, update_freq_unit,
    source, short_desc, long_desc, use_case,
    links, contributors, created_at, updated_at,
    query_type, query_chart, query_history, city
)
SELECT
    'parking_rate_tpe_district_median', NULL, NULL,
    NULL,
    'static', NULL, NULL, NULL,
    '臺北市交通局 / 新北市政府交通局', '各行政區路邊停車費率中位數（雙北）',
    '以行政區統計雙北路邊停車平日費率中位數。',
    '可用於比較雙北各行政區路邊停車費率差異，輔助停車收費政策分析。',
    '{https://data.taipei/dataset/detail?id=86d2a8b6-c360-4349-956d-dd7771cccf91,https://data.ntpc.gov.tw/datasets/d9f18db5-41c7-41d4-b7f0-82a335255b08}', '{doit,ntpc}',
    '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00',
    'two_d',
    'SELECT
        district AS x_axis,
        ROUND(
            percentile_cont(0.5) WITHIN GROUP (ORDER BY weekday_rate)::numeric,
            1
        )::double precision AS data
    FROM public.parking_rate_tpe
    WHERE district IS NOT NULL
      AND weekday_rate IS NOT NULL
    GROUP BY district
    ORDER BY data DESC, district',
    NULL, 'metrotaipei';


-- ── 5. dashboards ─────────────────────────────────────────────────────────────
INSERT INTO public.dashboards (id, index, name, components, icon, updated_at, created_at)
VALUES
    (504, 'parking_rate_tpe', '路邊停車費率', '{504,506}', 'local_parking',
     '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00'),
    (505, 'parking_rate_metrotaipei', '路邊停車費率', '{504,506}', 'local_parking',
     '2026-05-03 00:00:00+00', '2026-05-03 00:00:00+00')
ON CONFLICT (id) DO UPDATE SET
    index = EXCLUDED.index,
    name = EXCLUDED.name,
    components = EXCLUDED.components,
    icon = EXCLUDED.icon,
    updated_at = EXCLUDED.updated_at;


-- ── 6. dashboard_groups ───────────────────────────────────────────────────────
-- group 2 = taipei（臺北市）、group 3 = metrotaipei（雙北）
INSERT INTO public.dashboard_groups (dashboard_id, group_id)
VALUES (504, 2), (505, 3)
ON CONFLICT DO NOTHING;
