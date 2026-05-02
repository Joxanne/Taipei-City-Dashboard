package models

import (
	"fmt"
	"regexp"
	"sort"
	"strings"
)

type BusStop struct {
	StopSeq   int     `gorm:"column:stop_seq"  json:"stop_seq"`
	StopName  string  `gorm:"column:stop_name" json:"stop_name"`
	District  string  `gorm:"column:district"  json:"district"`
	Latitude  float64 `gorm:"column:latitude"  json:"lat"`
	Longitude float64 `gorm:"column:longitude" json:"lon"`
}

type BusRouteSimple struct {
	RouteName string `gorm:"column:route_name" json:"route_name"`
}

type BusStopOption struct {
	StopLocationID int     `gorm:"column:stop_location_id" json:"stop_location_id"`
	StopName       string  `gorm:"column:stop_name"        json:"stop_name"`
	District       string  `gorm:"column:district"         json:"district"`
	Latitude       float64 `gorm:"column:latitude"         json:"lat"`
	Longitude      float64 `gorm:"column:longitude"        json:"lon"`
}

type BusTransferRoute struct {
	RouteA       string        `gorm:"column:route_a"         json:"route_a"`
	RouteB       string        `gorm:"column:route_b"         json:"route_b"`
	TransferStop BusStopOption `gorm:"embedded"               json:"transfer_stop"`
}

type BusTopDirectStopPair struct {
	RouteCount         int    `gorm:"column:route_count"           json:"route_count"`
	FromStopLocationID int    `gorm:"column:from_stop_location_id" json:"from_stop_location_id"`
	FromStopName       string `gorm:"column:from_stop_name"        json:"from_stop_name"`
	FromDistrict       string `gorm:"column:from_district"         json:"from_district"`
	ToStopLocationID   int    `gorm:"column:to_stop_location_id"   json:"to_stop_location_id"`
	ToStopName         string `gorm:"column:to_stop_name"          json:"to_stop_name"`
	ToDistrict         string `gorm:"column:to_district"           json:"to_district"`
}

type BusRoadOption struct {
	RoadName string `json:"road_name"`
}

func normalizeCityParam(cityParam string) (string, error) {
	switch cityParam {
	case "taipei", "臺北市":
		return "臺北市", nil
	case "newtaipei", "新北市":
		return "新北市", nil
	default:
		return "", fmt.Errorf("city must be taipei or newtaipei")
	}
}

var roadNamePattern = regexp.MustCompile(`^(.+?(路|街|大道|巷|弄|段|橋|隧道|大街|公路))`)

func extractRoadName(stopName string) string {
	if stopName == "" {
		return ""
	}
	if match := roadNamePattern.FindStringSubmatch(stopName); len(match) > 1 {
		return match[1]
	}
	for _, sep := range []string{" ", "（", "(", "-", "－", "/"} {
		if idx := strings.Index(stopName, sep); idx > 0 {
			return stopName[:idx]
		}
	}
	return stopName
}

func GetBusStops(routeName, cityParam string) ([]BusStop, error) {
	query := `
		SELECT brs.stop_seq,
		       bs.stop_name,
		       COALESCE(bs.district, '') AS district,
		       COALESCE(bs.latitude,  0) AS latitude,
		       COALESCE(bs.longitude, 0) AS longitude
		FROM   public.bus_route_tpe        br
		JOIN   public.bus_route_stops_tpe  brs
		       ON  br.route_id = brs.route_id
		JOIN   public.bus_stop_tpe         bs
		       ON  brs.stop_location_id = bs.stop_location_id
		WHERE  br.route_name = ?
		  AND  brs.go_back = 0
		ORDER  BY brs.stop_seq
	`

	var stops []BusStop
	err := DBDashboard.Raw(query, routeName).Scan(&stops).Error
	return stops, err
}

func GetBusDistricts(cityParam string) ([]string, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT DISTINCT COALESCE(district, '') AS district
		FROM public.bus_stop_tpe
		WHERE geo_city = ?
		  AND district IS NOT NULL
		  AND district <> ''
		ORDER BY district
	`

	var districts []string
	err = DBDashboard.Raw(query, city).Scan(&districts).Error
	return districts, err
}

func GetBusRoutesByDistrict(cityParam, district string) ([]BusRouteSimple, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT DISTINCT br.route_name
		FROM public.bus_route_tpe br
		JOIN public.bus_route_stops_tpe brs
		  ON br.route_id = brs.route_id
		JOIN public.bus_stop_tpe bs
		  ON brs.stop_location_id = bs.stop_location_id
		WHERE bs.geo_city = ?
		  AND bs.district = ?
		ORDER BY br.route_name
	`

	var routes []BusRouteSimple
	err = DBDashboard.Raw(query, city, district).Scan(&routes).Error
	return routes, err
}

func GetBusStopsByRouteAndDistrict(cityParam, district, routeName string) ([]BusStopOption, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT DISTINCT
		  bs.stop_location_id,
		  bs.stop_name,
		  COALESCE(bs.district, '') AS district,
		  COALESCE(bs.latitude, 0) AS latitude,
		  COALESCE(bs.longitude, 0) AS longitude
		FROM public.bus_route_tpe br
		JOIN public.bus_route_stops_tpe brs
		  ON br.route_id = brs.route_id
		JOIN public.bus_stop_tpe bs
		  ON brs.stop_location_id = bs.stop_location_id
		WHERE br.route_name = ?
		  AND bs.district = ?
		  AND bs.geo_city = ?
		ORDER BY bs.stop_name
	`

	var stops []BusStopOption
	err = DBDashboard.Raw(query, routeName, district, city).Scan(&stops).Error
	return stops, err
}

func GetBusRoadsByDistrict(cityParam, district string) ([]BusRoadOption, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT COALESCE(stop_name, '') AS stop_name
		FROM public.bus_stop_tpe
		WHERE geo_city = ?
		  AND district = ?
		  AND stop_name IS NOT NULL
		  AND stop_name <> ''
	`

	var stopNames []struct {
		StopName string `gorm:"column:stop_name"`
	}
	err = DBDashboard.Raw(query, city, district).Scan(&stopNames).Error
	if err != nil {
		return nil, err
	}

	roadMap := map[string]struct{}{}
	for _, row := range stopNames {
		road := extractRoadName(row.StopName)
		if road != "" {
			roadMap[road] = struct{}{}
		}
	}

	roads := make([]BusRoadOption, 0, len(roadMap))
	for road := range roadMap {
		roads = append(roads, BusRoadOption{RoadName: road})
	}
	sort.Slice(roads, func(i, j int) bool {
		return roads[i].RoadName < roads[j].RoadName
	})

	return roads, nil
}

func GetBusStopsByRoad(cityParam, district, roadName string) ([]BusStopOption, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT
		  bs.stop_location_id,
		  bs.stop_name,
		  COALESCE(bs.district, '') AS district,
		  COALESCE(bs.latitude, 0) AS latitude,
		  COALESCE(bs.longitude, 0) AS longitude
		FROM public.bus_stop_tpe bs
		WHERE bs.geo_city = ?
		  AND bs.district = ?
		  AND bs.stop_name IS NOT NULL
		  AND bs.stop_name <> ''
		ORDER BY bs.stop_name
	`

	var stops []BusStopOption
	err = DBDashboard.Raw(query, city, district).Scan(&stops).Error
	if err != nil {
		return nil, err
	}

	filtered := make([]BusStopOption, 0, len(stops))
	for _, stop := range stops {
		if extractRoadName(stop.StopName) == roadName {
			filtered = append(filtered, stop)
		}
	}

	return filtered, nil
}

func GetBusStopsByDistrict(cityParam, district string) ([]BusStopOption, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT
		  bs.stop_location_id,
		  bs.stop_name,
		  COALESCE(bs.district, '') AS district,
		  COALESCE(bs.latitude, 0) AS latitude,
		  COALESCE(bs.longitude, 0) AS longitude
		FROM public.bus_stop_tpe bs
		WHERE bs.geo_city = ?
		  AND bs.district = ?
		  AND bs.stop_name IS NOT NULL
		  AND bs.stop_name <> ''
		ORDER BY bs.stop_name
	`

	var stops []BusStopOption
	err = DBDashboard.Raw(query, city, district).Scan(&stops).Error
	return stops, err
}

func GetTopDirectStopPair(cityParam string) (BusTopDirectStopPair, error) {
	city, err := normalizeCityParam(cityParam)
	if err != nil {
		return BusTopDirectStopPair{}, err
	}

	query := `
		WITH stop_routes AS (
			SELECT br.route_id, bs.stop_name
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			JOIN public.bus_stop_tpe bs
			  ON brs.stop_location_id = bs.stop_location_id
			WHERE bs.geo_city = ?
			  AND bs.stop_name IS NOT NULL
			  AND bs.stop_name <> ''
		),
		pair_counts AS (
			SELECT
			  sr1.stop_name AS from_stop_name,
			  sr2.stop_name AS to_stop_name,
			  COUNT(DISTINCT sr1.route_id) AS route_count
			FROM stop_routes sr1
			JOIN stop_routes sr2
			  ON sr1.route_id = sr2.route_id
			 AND sr1.stop_name < sr2.stop_name
			GROUP BY sr1.stop_name, sr2.stop_name
		),
		stop_lookup AS (
			SELECT
			  stop_name,
			  MIN(stop_location_id) AS stop_location_id,
			  MIN(COALESCE(district, '')) AS district
			FROM public.bus_stop_tpe
			WHERE geo_city = ?
			GROUP BY stop_name
		),
		top_pair AS (
			SELECT *
			FROM pair_counts
			ORDER BY route_count DESC
			LIMIT 1
		)
		SELECT
		  tp.route_count,
		  f.stop_location_id AS from_stop_location_id,
		  f.stop_name AS from_stop_name,
		  f.district AS from_district,
		  t.stop_location_id AS to_stop_location_id,
		  t.stop_name AS to_stop_name,
		  t.district AS to_district
		FROM top_pair tp
		JOIN stop_lookup f ON f.stop_name = tp.from_stop_name
		JOIN stop_lookup t ON t.stop_name = tp.to_stop_name
		WHERE f.stop_location_id <> t.stop_location_id
	`

	var pair BusTopDirectStopPair
	err = DBDashboard.Raw(query, city, city).Scan(&pair).Error
	return pair, err
}

func GetDirectRoutesByStops(fromCityParam, toCityParam string, fromStopLocationID, toStopLocationID int) ([]BusRouteSimple, error) {
	fromCity, err := normalizeCityParam(fromCityParam)
	if err != nil {
		return nil, err
	}
	toCity, err := normalizeCityParam(toCityParam)
	if err != nil {
		return nil, err
	}

	query := `
		SELECT DISTINCT br.route_name
		FROM public.bus_route_tpe br
		JOIN public.bus_route_stops_tpe brs1 ON br.route_id = brs1.route_id
		JOIN public.bus_stop_tpe bs1 ON brs1.stop_location_id = bs1.stop_location_id
		JOIN public.bus_route_stops_tpe brs2 ON br.route_id = brs2.route_id
		JOIN public.bus_stop_tpe bs2 ON brs2.stop_location_id = bs2.stop_location_id
		WHERE bs1.geo_city = ?
		  AND bs1.stop_name = (
		    SELECT stop_name FROM public.bus_stop_tpe
		    WHERE stop_location_id = ? AND geo_city = ?
		    LIMIT 1
		  )
		  AND bs2.geo_city = ?
		  AND bs2.stop_name = (
		    SELECT stop_name FROM public.bus_stop_tpe
		    WHERE stop_location_id = ? AND geo_city = ?
		    LIMIT 1
		  )
		ORDER BY br.route_name
	`

	var routes []BusRouteSimple
	err = DBDashboard.Raw(query, fromCity, fromStopLocationID, fromCity, toCity, toStopLocationID, toCity).Scan(&routes).Error
	return routes, err
}

func GetTransferRoutesByStops(cityParam string, fromStopLocationID, toStopLocationID int) ([]BusTransferRoute, error) {
	if _, e := normalizeCityParam(cityParam); e != nil {
		return nil, e
	}

	query := `
		WITH route_a AS (
			SELECT DISTINCT br.route_id, br.route_name
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			WHERE brs.stop_location_id = ?
		),
		route_b AS (
			SELECT DISTINCT br.route_id, br.route_name
			FROM public.bus_route_tpe br
			JOIN public.bus_route_stops_tpe brs
			  ON br.route_id = brs.route_id
			WHERE brs.stop_location_id = ?
		),
		route_a_stops AS (
			SELECT ra.route_id, ra.route_name, brs.stop_location_id
			FROM route_a ra
			JOIN public.bus_route_stops_tpe brs
			  ON ra.route_id = brs.route_id
		),
		route_b_stops AS (
			SELECT rb.route_id, rb.route_name, brs.stop_location_id
			FROM route_b rb
			JOIN public.bus_route_stops_tpe brs
			  ON rb.route_id = brs.route_id
		)
		SELECT DISTINCT
		  ra.route_name AS route_a,
		  rb.route_name AS route_b,
		  bs.stop_location_id,
		  bs.stop_name,
		  COALESCE(bs.district, '') AS district,
		  COALESCE(bs.latitude, 0) AS latitude,
		  COALESCE(bs.longitude, 0) AS longitude
		FROM route_a_stops ra
		JOIN route_b_stops rb
		  ON ra.stop_location_id = rb.stop_location_id
		JOIN public.bus_stop_tpe bs
		  ON bs.stop_location_id = ra.stop_location_id
		WHERE ra.route_id <> rb.route_id
		  AND ra.stop_location_id NOT IN (?, ?)
		ORDER BY route_a, route_b, bs.stop_name
	`

	var routes []BusTransferRoute
	err := DBDashboard.Raw(
		query,
		fromStopLocationID,
		toStopLocationID,
		fromStopLocationID,
		toStopLocationID,
	).Scan(&routes).Error
	return routes, err
}
