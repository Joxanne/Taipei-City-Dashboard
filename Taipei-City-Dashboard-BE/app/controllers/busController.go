package controllers

import (
	"net/http"
	"strconv"

	"TaipeiCityDashboardBE/app/models"

	"github.com/gin-gonic/gin"
)

// GetBusStops returns ordered go-direction stops for a bus route.
// GET /api/v1/bus/stops?route=299&city=taipei
func GetBusStops(c *gin.Context) {
	routeName := c.Query("route")
	if routeName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "route parameter is required"})
		return
	}

	cityParam := c.Query("city")
	if cityParam == "" {
		cityParam = "taipei"
	}
	if cityParam != "taipei" && cityParam != "metrotaipei" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city must be taipei or metrotaipei"})
		return
	}

	stops, err := models.GetBusStops(routeName, cityParam)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "data": stops})
}

// GetBusCities returns supported city options for bus queries.
// GET /api/v1/bus/lookup/cities
func GetBusCities(c *gin.Context) {
	data := []gin.H{
		{"value": "taipei", "label": "臺北市"},
		{"value": "newtaipei", "label": "新北市"},
	}
	c.JSON(http.StatusOK, gin.H{"status": "success", "data": data})
}

// GetBusDistricts returns districts by city.
// GET /api/v1/bus/lookup/districts?city=taipei
func GetBusDistricts(c *gin.Context) {
	cityParam := c.Query("city")
	if cityParam == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city parameter is required"})
		return
	}

	districts, err := models.GetBusDistricts(cityParam)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "data": districts})
}

// GetBusRoutesByDistrict returns routes passing through a district.
// GET /api/v1/bus/lookup/routes?city=taipei&district=中正區
func GetBusRoutesByDistrict(c *gin.Context) {
	cityParam := c.Query("city")
	district := c.Query("district")
	if cityParam == "" || district == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city and district parameters are required"})
		return
	}

	routes, err := models.GetBusRoutesByDistrict(cityParam, district)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "data": routes})
}

// GetBusStopsLookup returns stops by route and district.
// GET /api/v1/bus/lookup/stops?city=taipei&district=中正區&route=299
func GetBusStopsLookup(c *gin.Context) {
	cityParam := c.Query("city")
	district := c.Query("district")
	routeName := c.Query("route")
	if cityParam == "" || district == "" || routeName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city, district and route parameters are required"})
		return
	}

	stops, err := models.GetBusStopsByRouteAndDistrict(cityParam, district, routeName)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "data": stops})
}

// GetBusRoadsByDistrict returns road names in a district.
// GET /api/v1/bus/lookup/roads?city=taipei&district=中正區
func GetBusRoadsByDistrict(c *gin.Context) {
	cityParam := c.Query("city")
	district := c.Query("district")
	if cityParam == "" || district == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city and district parameters are required"})
		return
	}

	roads, err := models.GetBusRoadsByDistrict(cityParam, district)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "data": roads})
}

// GetBusStopsByRoad returns stops under a road name in a district.
// GET /api/v1/bus/lookup/stops-by-road?city=taipei&district=中正區&road=中山路
func GetBusStopsByRoad(c *gin.Context) {
	cityParam := c.Query("city")
	district := c.Query("district")
	roadName := c.Query("road")
	if cityParam == "" || district == "" || roadName == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city, district and road parameters are required"})
		return
	}

	stops, err := models.GetBusStopsByRoad(cityParam, district, roadName)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "success", "data": stops})
}

// GetBusTransfer returns direct routes and transfer routes between two stops.
// GET /api/v1/bus/transfer?city=taipei&from_stop=123&to_stop=456&max_transfers=1
func GetBusTransfer(c *gin.Context) {
	cityParam := c.Query("city")
	toCityParam := c.DefaultQuery("to_city", c.Query("city"))
	fromStop := c.Query("from_stop")
	toStop := c.Query("to_stop")
	maxTransfersParam := c.DefaultQuery("max_transfers", "1")
	if cityParam == "" || fromStop == "" || toStop == "" {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "city, from_stop and to_stop parameters are required"})
		return
	}

	fromStopID, err := strconv.Atoi(fromStop)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "from_stop must be an integer"})
		return
	}
	toStopID, err := strconv.Atoi(toStop)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "to_stop must be an integer"})
		return
	}
	maxTransfers, err := strconv.Atoi(maxTransfersParam)
	if err != nil || maxTransfers < 0 || maxTransfers > 1 {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": "max_transfers must be 0 or 1"})
		return
	}

	directRoutes, err := models.GetDirectRoutesByStops(cityParam, toCityParam, fromStopID, toStopID)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
		return
	}

	transferRoutes := []models.BusTransferRoute{}
	if maxTransfers >= 1 {
		transferRoutes, err = models.GetTransferRoutesByStops(cityParam, fromStopID, toStopID)
		if err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"status": "error", "message": err.Error()})
			return
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"status": "success",
		"data": gin.H{
			"direct_routes":   directRoutes,
			"transfer_routes": transferRoutes,
		},
	})
}
