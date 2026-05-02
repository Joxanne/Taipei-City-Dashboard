package controllers

import (
	"TaipeiCityDashboardBE/app/cache"
	"TaipeiCityDashboardBE/global"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

var defaultIsochroneColors = []string{"2ecc71", "f1c40f", "e67e22", "e74c3c"}

// GetIsochrone proxies the Mapbox Isochrone API and caches the response in Redis.
// Query params: lng, lat, profile (default: driving-traffic), minutes (default: 30), colors
func GetIsochrone(c *gin.Context) {
	lng := c.Query("lng")
	lat := c.Query("lat")
	profile := c.DefaultQuery("profile", "driving-traffic")
	minutes := c.DefaultQuery("minutes", "30")
	colors := c.DefaultQuery("colors", "2ecc71,f1c40f,e67e22,e74c3c")

	if lng == "" || lat == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "lng and lat are required"})
		return
	}

	if global.MapboxToken == "" {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Mapbox token not configured"})
		return
	}

	colors = normalizeIsochroneColors(minutes, colors)

	cacheKey := fmt.Sprintf("isochrone:%s:%s:%s:%s:%s", profile, lng, lat, minutes, colors)

	// Return cached response if available
	if cached, err := cache.Redis.Get(cacheKey).Bytes(); err == nil {
		c.Data(http.StatusOK, "application/json", cached)
		return
	}

	params := url.Values{}
	params.Set("contours_minutes", minutes)
	params.Set("contours_colors", colors)
	params.Set("polygons", "true")
	params.Set("generalize", "50")
	params.Set("denoise", "1")
	params.Set("access_token", global.MapboxToken)
	apiURL := fmt.Sprintf("https://api.mapbox.com/isochrone/v1/mapbox/%s/%s,%s?%s", profile, lng, lat, params.Encode())

	req, err := http.NewRequestWithContext(c.Request.Context(), http.MethodGet, apiURL, nil)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	if resp.StatusCode == http.StatusOK {
		// driving-traffic changes with congestion; cache for shorter time
		ttl := 60 * time.Minute
		if profile == "driving-traffic" {
			ttl = 10 * time.Minute
		}
		cache.Redis.Set(cacheKey, body, ttl)
	}

	c.Data(resp.StatusCode, "application/json", body)
}

func normalizeIsochroneColors(minutes string, colors string) string {
	minuteParts := splitNonEmpty(minutes)
	if len(minuteParts) == 0 {
		minuteParts = []string{"30"}
	}

	colorParts := splitNonEmpty(colors)
	if len(colorParts) == 0 {
		colorParts = defaultIsochroneColors
	}

	normalized := make([]string, 0, len(minuteParts))
	for i := range minuteParts {
		if i < len(colorParts) {
			normalized = append(normalized, colorParts[i])
		} else {
			normalized = append(normalized, defaultIsochroneColors[i%len(defaultIsochroneColors)])
		}
	}
	return strings.Join(normalized, ",")
}

func splitNonEmpty(value string) []string {
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			result = append(result, part)
		}
	}
	return result
}
