import re

path = 'c:/碩士/Hackathon/Taipei-City-Dashboard/Taipei-City-Dashboard-BE/app/models/busData.go'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# GetDirectRoutesByStops
query1_old = '''		WHERE br.city = ?
		  AND brs1.stop_location_id = ?
		  AND brs2.stop_location_id = ?'''
query1_new = '''		WHERE brs1.stop_location_id = ?
		  AND brs2.stop_location_id = ?'''
content = content.replace(query1_old, query1_new)
content = content.replace('DBDashboard.Raw(query, city, fromStopLocationID, toStopLocationID)', 'DBDashboard.Raw(query, fromStopLocationID, toStopLocationID)')

# GetTransferRoutesByStops
query2_old = '''		WITH route_a AS (
			SELECT DISTINCT br.route_id, br.route_name, br.city
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			 AND br.city = brs.city
			WHERE br.city = ?
			  AND brs.stop_location_id = ?
		),
		route_b AS (
			SELECT DISTINCT br.route_id, br.route_name, br.city
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			 AND br.city = brs.city
			WHERE br.city = ?
			  AND brs.stop_location_id = ?
		),'''
query2_new = '''		WITH route_a AS (
			SELECT DISTINCT br.route_id, br.route_name, br.city
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			 AND br.city = brs.city
			WHERE brs.stop_location_id = ?
		),
		route_b AS (
			SELECT DISTINCT br.route_id, br.route_name, br.city
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			 AND br.city = brs.city
			WHERE brs.stop_location_id = ?
		),'''
content = content.replace(query2_old, query2_new)

query3_old = '''		JOIN public.bus_stop_tpe bs
		  ON bs.stop_location_id = ra.stop_location_id
		 AND bs.city = ?
		WHERE ra.route_id <> rb.route_id'''
query3_new = '''		JOIN public.bus_stop_tpe bs
		  ON bs.stop_location_id = ra.stop_location_id
		WHERE ra.route_id <> rb.route_id'''
content = content.replace(query3_old, query3_new)

scan_old = '''	err = DBDashboard.Raw(
		query,
		city,
		fromStopLocationID,
		city,
		toStopLocationID,
		city,
		fromStopLocationID,
		toStopLocationID,
	).Scan(&routes).Error'''
scan_new = '''	err = DBDashboard.Raw(
		query,
		fromStopLocationID,
		toStopLocationID,
		fromStopLocationID,
		toStopLocationID,
	).Scan(&routes).Error'''
content = content.replace(scan_old, scan_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done backend')
