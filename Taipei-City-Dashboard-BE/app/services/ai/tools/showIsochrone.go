package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"strings"

	"TaipeiCityDashboardBE/global"
)

type showIsochroneArgs struct {
	Lng      string `json:"lng"`
	Lat      string `json:"lat"`
	Location string `json:"location"`
	Profile  string `json:"profile"`
	Minutes  string `json:"minutes"`
}

type geocodedOrigin struct {
	Lng  float64
	Lat  float64
	Name string
}

type mapboxGeocodeResponse struct {
	Features []struct {
		PlaceName string    `json:"place_name"`
		Center    []float64 `json:"center"`
	} `json:"features"`
}

const taipeiMetroBBox = "121.35,24.85,121.75,25.30"

func init() {
	MustRegister(
		NewTool(
			"show_isochrone",
			"在地圖上顯示指定地點的通勤圈分析（等時圈），視覺化從起點在指定時間內，以不同交通方式可到達的範圍。使用者詢問「X 地點附近 N 分鐘可到哪裡」或「通勤圈」「生活圈」時使用此工具。若使用者提供地址、路名、行政區、社區、學校、公園或其他地名，務必用 location 傳入完整地點文字，不要自行猜座標。只有使用者明確提供座標或是常用臺北地標才直接提供 lng/lat。未指定時間時預設 30 分鐘；如果指定超過 4 個時間，系統會顯示排序後前 4 個。常用臺北地標座標：臺北車站 (lng=121.5170, lat=25.0478)、台北 101 (lng=121.5645, lat=25.0339)、板橋車站 (lng=121.4628, lat=25.0143)、市政府 (lng=121.5645, lat=25.0408)、南港車站 (lng=121.6068, lat=25.0525)、新店區公所 (lng=121.5418, lat=24.9718)。",
			handleShowIsochrone,
		).
			OptionalString("location", "起點地點文字。當沒有把握座標或使用者提供地址、路名、地名時使用，例如 \"台北市信義區市府路45號\"、\"大安森林公園\"。").
			OptionalString("lng", "起點經度，例如 \"121.5170\"（臺北車站）。若提供 location 可省略。").
			OptionalString("lat", "起點緯度，例如 \"25.0478\"（臺北車站）。若提供 location 可省略。").
			OptionalStringEnum("profile", "交通模式。未指定時預設 driving-traffic。", "driving-traffic", "driving", "cycling", "walking").
			OptionalString("minutes", "等時圈時間帶，逗號分隔的分鐘數，例如 \"10\" 或 \"10,20,30\"。每個值需為 1～60，最多 4 個等時圈。未指定時預設 \"30\"。").
			Build(),
	)
}

func handleShowIsochrone(ctx context.Context, args string) (string, error) {
	var params showIsochroneArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}

	origin, err := resolveIsochroneOrigin(ctx, params)
	if err != nil {
		return "", err
	}

	if params.Profile == "" {
		params.Profile = "driving-traffic"
	}
	if !isAllowedIsochroneProfile(params.Profile) {
		return "", fmt.Errorf("profile must be one of driving-traffic, driving, cycling, walking")
	}

	minutesText := params.Minutes
	if strings.TrimSpace(minutesText) == "" {
		minutesText = "30"
	}
	minutes, err := parseIsochroneMinutes(minutesText)
	if err != nil {
		return "", err
	}

	EmitToolAction(ctx, "show_isochrone", map[string]interface{}{
		"lng":      origin.Lng,
		"lat":      origin.Lat,
		"location": origin.Name,
		"profile":  params.Profile,
		"minutes":  minutes,
	})

	result, _ := json.Marshal(map[string]interface{}{
		"success":  true,
		"lng":      origin.Lng,
		"lat":      origin.Lat,
		"location": origin.Name,
		"profile":  params.Profile,
		"minutes":  minutes,
	})
	return string(result), nil
}

func resolveIsochroneOrigin(ctx context.Context, params showIsochroneArgs) (geocodedOrigin, error) {
	location := strings.TrimSpace(params.Location)
	if location != "" {
		return geocodeTaiwanLocation(ctx, location)
	}

	lngText := strings.TrimSpace(params.Lng)
	latText := strings.TrimSpace(params.Lat)
	if lngText != "" && latText != "" {
		lng, err := strconv.ParseFloat(lngText, 64)
		if err != nil || lng < 119.0 || lng > 122.5 {
			return geocodedOrigin{}, fmt.Errorf("lng 必須是有效的台灣範圍經度（119～122.5），收到：%q", params.Lng)
		}

		lat, err := strconv.ParseFloat(latText, 64)
		if err != nil || lat < 21.5 || lat > 25.5 {
			return geocodedOrigin{}, fmt.Errorf("lat 必須是有效的台灣範圍緯度（21.5～25.5），收到：%q", params.Lat)
		}

		return geocodedOrigin{
			Lng:  lng,
			Lat:  lat,
			Name: strings.TrimSpace(params.Location),
		}, nil
	}

	return geocodedOrigin{}, fmt.Errorf("請提供 lng/lat，或提供 location 讓系統轉換座標")
}

func geocodeTaiwanLocation(ctx context.Context, location string) (geocodedOrigin, error) {
	if global.MapboxToken == "" {
		return geocodedOrigin{}, fmt.Errorf("Mapbox token not configured")
	}

	endpoint := fmt.Sprintf(
		"https://api.mapbox.com/geocoding/v5/mapbox.places/%s.json",
		url.PathEscape(normalizeTaipeiLocationQuery(location)),
	)
	values := url.Values{}
	values.Set("access_token", global.MapboxToken)
	values.Set("bbox", taipeiMetroBBox)
	values.Set("country", "tw")
	values.Set("language", "zh-Hant")
	values.Set("limit", "3")
	values.Set("proximity", "121.5654,25.0376")
	values.Set("types", "address,poi,place,locality,neighborhood")

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, endpoint+"?"+values.Encode(), nil)
	if err != nil {
		return geocodedOrigin{}, err
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return geocodedOrigin{}, fmt.Errorf("geocode failed: %v", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return geocodedOrigin{}, err
	}
	if resp.StatusCode != http.StatusOK {
		return geocodedOrigin{}, fmt.Errorf("geocode returned status %d: %s", resp.StatusCode, string(body))
	}

	var decoded mapboxGeocodeResponse
	if err := json.Unmarshal(body, &decoded); err != nil {
		return geocodedOrigin{}, fmt.Errorf("decode geocode response: %v", err)
	}
	feature, ok := firstValidTaiwanGeocodeFeature(decoded)
	if !ok {
		return geocodedOrigin{}, fmt.Errorf("找不到 %q 的座標", location)
	}

	origin := geocodedOrigin{
		Lng:  feature.Center[0],
		Lat:  feature.Center[1],
		Name: feature.PlaceName,
	}
	if origin.Name == "" {
		origin.Name = location
	}
	if origin.Lng < 119.0 || origin.Lng > 122.5 || origin.Lat < 21.5 || origin.Lat > 25.5 {
		return geocodedOrigin{}, fmt.Errorf("geocode result for %q is outside Taiwan", location)
	}
	return origin, nil
}

func normalizeTaipeiLocationQuery(location string) string {
	location = strings.TrimSpace(location)
	if strings.Contains(location, "台北") ||
		strings.Contains(location, "臺北") ||
		strings.Contains(location, "新北") ||
		strings.Contains(location, "基隆") {
		return location
	}
	return location + " 台北"
}

func firstValidTaiwanGeocodeFeature(decoded mapboxGeocodeResponse) (struct {
	PlaceName string    `json:"place_name"`
	Center    []float64 `json:"center"`
}, bool) {
	for _, feature := range decoded.Features {
		if len(feature.Center) < 2 {
			continue
		}
		lng := feature.Center[0]
		lat := feature.Center[1]
		if lng >= 119.0 && lng <= 122.5 && lat >= 21.5 && lat <= 25.5 {
			return feature, true
		}
	}
	return struct {
		PlaceName string    `json:"place_name"`
		Center    []float64 `json:"center"`
	}{}, false
}

func isAllowedIsochroneProfile(profile string) bool {
	switch profile {
	case "driving-traffic", "driving", "cycling", "walking":
		return true
	default:
		return false
	}
}

func parseIsochroneMinutes(value string) ([]int, error) {
	parts := strings.Split(value, ",")
	seen := make(map[int]struct{}, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		minute, err := strconv.Atoi(part)
		if err != nil || minute <= 0 || minute > 60 {
			return nil, fmt.Errorf("minutes 中包含無效值 %q，每個值必須是 1～60 的正整數", part)
		}
		seen[minute] = struct{}{}
	}
	if len(seen) == 0 {
		return nil, fmt.Errorf("minutes 不得為空")
	}
	minutes := make([]int, 0, len(seen))
	for minute := range seen {
		minutes = append(minutes, minute)
	}
	sort.Ints(minutes)
	if len(minutes) > 4 {
		minutes = minutes[:4]
	}
	return minutes, nil
}
