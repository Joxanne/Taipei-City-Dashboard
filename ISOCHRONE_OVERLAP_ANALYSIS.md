# 等時圈重疊檢測功能 - 完整實現分析

**文件生成時間**: 2026-05-03  
**專案**: Taipei City Dashboard  
**目標**: 實現等時圈繪製後與當前圖層（公車站點、自行車路網等）的重疊項目過濾與顯示

---

## 📋 目錄

1. [功能需求](#功能需求)
2. [架構流程](#架構流程)
3. [前端檔案清單](#前端檔案清單)
4. [後端檔案清單](#後端檔案清單)
5. [演示 Dashboard](#演示-dashboard)
6. [文件修改優先級](#文件修改優先級)
7. [技術資源](#技術資源)
8. [實現步驟](#實現步驟)

---

## 功能需求

### 核心目標
使用者通過 AI Chat 詢問「X 地點附近 N 分鐘可到哪裡」時，系統應該：

1. ✅ 繪製等時圈（已完成）
2. ❌ 過濾出與當前圖層的重疊項目（需新增）
3. ❌ 在地圖上顯示重疊結果（需新增）

### 示例場景

```
使用者: "台北車站周邊 30 分鐘內可到的公車站點有哪些？"
         ↓
LLM 識別 show_isochrone 工具 + 需要過濾公車站點
         ↓
後端繪製 30 分鐘等時圈
         ↓
後端查詢 bus_stop 圖層中在等時圈內的站點
         ↓
前端同時顯示：
  • 等時圈多邊形 (fill + outline)
  • 重疊的公車站點 (新增圖層)
```

---

## 架構流程

### 完整的數據流向

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 Chat 視圖                           │
│         (Taipei-City-Dashboard-FE/src/views/MapView.vue)    │
└────────────────────┬────────────────────────────────────────┘
                     │ 使用者輸入 + 當前圖層信息
                     ↓
┌─────────────────────────────────────────────────────────────┐
│         ChatBox & ChatSidePanel 組件                        │
│  (components/dialogs/ChatBox.vue, ChatSidePanel.vue)        │
└────────────────────┬────────────────────────────────────────┘
                     │ 調用 /api/v1/ai/chat/twai
                     ↓
┌─────────────────────────────────────────────────────────────┐
│           後端 AI 服務 (ai.go 控制器)                       │
│   • 調用 TWCC LLM                                           │
│   • 執行 show_isochrone 工具                                │
│   • 【新增】調用過濾服務                                     │
└────────────────────┬────────────────────────────────────────┘
                     │ tool_actions + tool_data
                     ↓
┌─────────────────────────────────────────────────────────────┐
│         前端 chatStore (store/chatStore.js)                 │
│    • handleToolAction() 處理各個 action                     │
│    • 【新增】調用 /api/v1/isochrone/filter API             │
└────────────────────┬────────────────────────────────────────┘
                     │ 過濾結果 (GeoJSON)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│         前端 mapStore (store/mapStore.js)                   │
│    • addIsochroneOverlay() 顯示等時圈                       │
│    • 【新增】addOverlappingPOIsLayer() 顯示重疊結果         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ↓
            ┌─────────────────┐
            │  地圖視圖更新   │
            │ (MapContainer)  │
            └─────────────────┘
```

---

## 前端檔案清單

### 📍 主要頁面組件

#### 1. `Taipei-City-Dashboard-FE/src/views/MapView.vue` ⭐ 
**用途**: 主要地圖演示頁面  
**責任**: 
- 整合地圖容器、圖層面板、Chat 面板
- 管理地圖相關的路由參數
- 協調前端各個 store 的狀態

**相關程式碼**:
```vue
<script setup>
import MapContainer from "../components/map/MapContainer.vue";
import DashboardComponent from "../dashboardComponent/DashboardComponent.vue";
import { useMapStore } from "../store/mapStore";
import { useContentStore } from "../store/contentStore";
</script>
```

**修改需求**: 無需修改（作為展示頁面）

---

#### 2. `Taipei-City-Dashboard-FE/src/views/DashboardView.vue`
**用途**: 儀表板統計視圖  
**責任**: 
- 展示圖表和統計數據
- 配合地圖視圖展示相關信息

**修改需求**: 無需修改

---

#### 3. `Taipei-City-Dashboard-FE/src/components/map/MapContainer.vue` ⭐
**用途**: Mapbox 地圖容器  
**責任**:
- 初始化地圖實例
- 提供圖層控制 UI
- 處理地圖交互事件

**關鍵功能**:
```javascript
// 地圖初始化 (第 113 行)
initializeMapBox() {
  this.map = new mapboxGl.Map({...})
}

// 圖層切換功能 (第 55-73 行)
toggleDistrictLayer()
toggleVillageLayer()
```

**修改需求**: 無需修改（使用現有的 mapStore 方法）

---

### 📦 狀態管理層

#### 4. `Taipei-City-Dashboard-FE/src/store/mapStore.js` ⭐⭐⭐ **[必須修改]**

**檔案大小**: ~2750 行  
**核心狀態**:
```javascript
// 等時圈相關狀態 (第 100-106 行)
isochroneState: {
  isLoading: false,
  origin: null,
  profile: "driving-traffic",
  minutes: [15, 30, 45, 60],
  visible: false,
}

// 當前啟用的圖層 (第 65 行)
currentLayers: [],
currentVisibleLayers: [],
```

**現有方法**:
| 方法 | 行號 | 功能 |
|------|------|------|
| `addIsochroneOverlay()` | 2667-2731 | 添加等時圈圖層 |
| `removeIsochroneOverlay()` | 2732-2741 | 移除等時圈圖層 |
| `toggleIsochroneVisibility()` | 2742-2750 | 切換等時圈可見性 |

**需新增方法**:
```javascript
/**
 * 添加重疊 POI 圖層
 * @param {Object} data - 過濾結果 GeoJSON
 * @param {Array<number>} minutes - 等時圈分鐘數
 * @param {string} componentId - 組件 ID (如 'bus_stop_estimate_tpe')
 */
async addOverlappingPOIsLayer({ data, minutes, componentId }) {
  // 1. 為每個時間等級創建不同的圖層
  // 2. 設置視覺樣式 (顏色、大小、透明度)
  // 3. 添加交互事件 (popup 等)
}

/**
 * 移除重疊 POI 圖層
 */
removeOverlappingPOIsLayer() {
  // 清理圖層和數據源
}
```

**相關依賴**:
- 已引入 `@turf/turf` (第 23 行)：`import { point, distance } from "@turf/turf"`
- Mapbox GL API
- 可利用的工具函式：`calculateHaversineDistance()` (第 50 行)

---

#### 5. `Taipei-City-Dashboard-FE/src/store/chatStore.js` ⭐⭐ **[必須修改]**

**檔案大小**: ~296 行  
**關鍵方法**: `handleToolAction()` (第 181-203 行)

**現有實現**:
```javascript
const handleToolAction = (event) => {
  if (event.action === "create_group") {
    // 創建組件組
  } else if (event.action === "toggle_component") {
    // 切換組件可見性
  } else if (event.action === "show_isochrone") {
    // 【現有】顯示等時圈
    const mapStore = useMapStore();
    mapStore.addIsochroneOverlay({
      lng: parseFloat(event.payload.lng),
      lat: parseFloat(event.payload.lat),
      profile: event.payload.profile || "driving-traffic",
      minutes: event.payload.minutes,
    });
  }
};
```

**需修改部分**:
```javascript
else if (event.action === "show_isochrone") {
  const mapStore = useMapStore();
  
  // 1. 現有：顯示等時圈
  mapStore.addIsochroneOverlay({
    lng: parseFloat(event.payload.lng),
    lat: parseFloat(event.payload.lat),
    profile: event.payload.profile || "driving-traffic",
    minutes: event.payload.minutes,
  });
  
  // 2. 【新增】調用過濾 API
  const filterParams = {
    lng: event.payload.lng,
    lat: event.payload.lat,
    profile: event.payload.profile || "driving-traffic",
    minutes: event.payload.minutes,
    componentIds: event.payload.componentIds, // 需要後端提供
  };
  
  try {
    const response = await http.post(
      "/api/v1/isochrone/filter",
      filterParams
    );
    
    if (response.data?.data) {
      // 3. 添加重疊結果圖層
      mapStore.addOverlappingPOIsLayer({
        data: response.data.data,
        minutes: event.payload.minutes,
        componentId: event.payload.componentId,
      });
    }
  } catch (error) {
    console.error("Filter isochrone overlaps failed:", error);
  }
}
```

**需訪問的方法**:
- `http.post()` - 已配置的 axios 實例 (第 3 行)
- `useMapStore()` - 地圖狀態 (第 6 行)

---

#### 6. `Taipei-City-Dashboard-FE/src/store/contentStore.js` ⭐

**檔案大小**: ~1000+ 行  
**主要責任**: 管理 dashboard 和組件配置  

**相關狀態**:
```javascript
// 當前啟用的圖層
mapLayers: [],
currentVisibleLayers: [],

// 所有組件
components: [],
allMapLayers: [],

// 當前 dashboard
currentDashboard: {
  components: null,  // 組件陣列
}
```

**可利用的方法**:
```javascript
// 查詢當前 dashboard 中哪些組件是地圖圖層
const mapLayerComponents = this.currentDashboard.components.filter(
  item => item.map_config && item.map_config.length > 0
);
```

**修改需求**: 無需修改（只讀取現有數據）

---

### 🛠️ 工具函式層

#### 7. `Taipei-City-Dashboard-FE/src/assets/utilityFunctions/geometryUtils.js` ⭐

**用途**: 幾何計算工具  
**建議**:
- 查看現有實現
- 可新增重疊檢測工具函式（如果前端實現過濾）

**修改需求**: 可選修改

---

#### 8. `Taipei-City-Dashboard-FE/src/assets/utilityFunctions/calculateHaversineDistance.js`

**用途**: 哈弗賽因距離計算  
**可用於**: 檢查點到等時圈邊界的距離（輔助）

---

### 📋 其他相關前端檔案

#### 9. `Taipei-City-Dashboard-FE/src/components/dialogs/ChatBox.vue`

**用途**: Chat 輸入框  
**責任**: 收集使用者輸入，調用 `chatStore.addQueryData()`

**修改需求**: 無需修改

---

#### 10. `Taipei-City-Dashboard-FE/src/components/dialogs/ChatSidePanel.vue`

**用途**: Chat 側邊面板  
**責任**: 展示聊天歷史，管理會話

**修改需求**: 無需修改

---

#### 11. `Taipei-City-Dashboard-FE/src/router/axios.js`

**用途**: HTTP 請求實例  
**狀態**: 已配置，可直接使用

**修改需求**: 無需修改

---

## 後端檔案清單

### 🎮 主控制層

#### 1. `Taipei-City-Dashboard-BE/app/controllers/ai.go` ⭐⭐ 

**檔案大小**: ~330 行  
**關鍵方法**: `ChatWithTWCC()` (第 66-159 行)

**現有結構**:
```go
type AIChatInput struct {
  SessionID string
  Stream bool
  Messages []struct{...}  // 聊天訊息
  Tools []struct{...}     // 可用工具定義
  // 其他 LLM 參數
}

// 回應格式 (第 140-158 行)
c.JSON(http.StatusOK, gin.H{
  "status": "success",
  "data": gin.H{
    "content": logEntry.Answer,
    "tool_used": logEntry.ToolUsed,
    "tools": logEntry.Tools,
    "tool_actions": logEntry.ToolActions,  // 這裡傳遞 action
    "components": logEntry.Components,
  },
})
```

**修改需求**: 無需修改（已支持 tool_actions）

---

#### 2. `Taipei-City-Dashboard-BE/app/controllers/isochrone.go` ⭐⭐ **[必須擴展]**

**檔案大小**: ~120 行  
**現有功能**:
```go
// GetIsochrone - 代理 Mapbox Isochrone API
func GetIsochrone(c *gin.Context) {
  // 參數：lng, lat, profile, minutes, colors
  // 功能：快取和代理 Isochrone API
  // 返回：GeoJSON 多邊形
}
```

**現有程式碼**:
```go
const defaultIsochroneColors = []string{"2ecc71", "f97316", "e67e22", "e74c3c"}

func GetIsochrone(c *gin.Context) {
  lng := c.Query("lng")
  lat := c.Query("lat")
  profile := c.DefaultQuery("profile", "driving-traffic")
  minutes := c.DefaultQuery("minutes", "30")
  
  // 1. 參數驗證
  if lng == "" || lat == "" {
    c.JSON(http.StatusBadRequest, gin.H{"error": "lng and lat are required"})
    return
  }
  
  // 2. 從 Redis 快取查詢
  cacheKey := fmt.Sprintf("isochrone:%s:%s:%s:%s:%s", profile, lng, lat, minutes, colors)
  if cached, err := cache.Redis.Get(cacheKey).Bytes(); err == nil {
    c.Data(http.StatusOK, "application/json", cached)
    return
  }
  
  // 3. 調用 Mapbox API
  // 4. 快取結果
  // 5. 返回 GeoJSON
}
```

**需新增方法**:
```go
/**
 * FilterIsochroneOverlaps - 過濾等時圈內的 POI
 * 
 * 請求參數:
 * - lng: 中心點經度
 * - lat: 中心點緯度  
 * - profile: 交通模式 (driving-traffic, cycling, walking)
 * - minutes: 等時圈時間（逗號分隔）
 * - component_ids: 目標組件 ID（逗號分隔，如 "110,111"）
 * 
 * 返回格式:
 * {
 *   "success": true,
 *   "data": {
 *     "15": [...POIs within 15 min],
 *     "30": [...POIs within 30 min],
 *   }
 * }
 */
func FilterIsochroneOverlaps(c *gin.Context) {
  // 1. 解析參數
  // 2. 獲取等時圈 GeoJSON
  // 3. 查詢組件對應的 POI 數據
  // 4. 檢測重疊
  // 5. 返回結果
}
```

---

### 🧠 AI 工具層

#### 3. `Taipei-City-Dashboard-BE/app/services/ai/tools/showIsochrone.go` ⭐

**檔案大小**: ~258 行  
**主要功能**: 解析參數、驗證座標、發送 action

**關鍵方法**:
```go
func handleShowIsochrone(ctx context.Context, args string) (string, error) {
  // 1. 解析參數
  var params showIsochroneArgs
  
  // 2. 解析地點或座標
  origin, err := resolveIsochroneOrigin(ctx, params)
  
  // 3. 驗證參數
  
  // 4. 發送 action 到前端
  EmitToolAction(ctx, "show_isochrone", map[string]interface{}{
    "lng": origin.Lng,
    "lat": origin.Lat,
    "location": origin.Name,
    "profile": params.Profile,
    "minutes": minutes,
  })
  
  // 5. 返回結果
}
```

**修改建議**: 可在 action payload 中新增 `componentIds` 欄位
```go
EmitToolAction(ctx, "show_isochrone", map[string]interface{}{
  "lng": origin.Lng,
  "lat": origin.Lat,
  "location": origin.Name,
  "profile": params.Profile,
  "minutes": minutes,
  // 【新增】根據 LLM 上下文識別的組件
  // "componentIds": []int{110, 111},  
})
```

**修改需求**: 建議修改（但非必須，可在前端讀取）

---

#### 4. `Taipei-City-Dashboard-BE/app/services/ai/tools/registry.go`

**用途**: 工具註冊表  
**現有工具**:
- `show_isochrone`
- `create_group`
- `toggle_component`
- `search_components`
- `current_time`
- `population_summary`

**修改需求**: 如新增過濾工具則需要註冊

---

### 📊 數據模型層

#### 5. `Taipei-City-Dashboard-BE/app/models/componentConfig.go` ⭐

**檔案大小**: ~1000+ 行  
**關鍵結構**:
```go
type Component struct {
  ID int64
  Index string  // 組件編號，如 'bus_stop_by_district'
  Name string   // 組件名稱
}

type QueryCharts struct {
  Index string
  MapConfigIDs pq.Int64Array  // 地圖配置 ID 陣列
  QueryChart string           // SQL 查詢語句
  TimeFrom string             // 數據源類型
  Source string               // 數據源名稱
}
```

**可利用方法**:
```go
// 查詢組件信息
func GetComponentByID(id int, city string) (CityComponent, error)

// 查詢組件的 SQL 查詢
func GetComponentChartDataQuery(id int, city string) (queryType, queryString string, err error)
```

**修改需求**: 無需修改

---

#### 6. `Taipei-City-Dashboard-BE/app/models/componentData.go`

**用途**: 執行 SQL 查詢獲取組件數據  
**關鍵功能**:
```go
func GetComponentChartData(id int, city string) (data []ChartData, err error) {
  // 執行 SQL 查詢並返回數據
}
```

**可利用**: 建立類似的方法來查詢地理空間數據

**修改需求**: 無需修改

---

### 🛣️ 路由層

#### 7. `Taipei-City-Dashboard-BE/app/routes/router.go` ⭐⭐ **[必須修改]**

**檔案大小**: ~250 行  
**現有路由配置**:

```go
func configureIsochroneRoutes() {
  isoRoutes := RouterGroup.Group("/isochrone")
  isoRoutes.Use(middleware.LimitAPIRequests(...))
  isoRoutes.Use(middleware.LimitTotalRequests(...))
  {
    isoRoutes.GET("/", controllers.GetIsochrone)
  }
}
```

**需修改**:
```go
func configureIsochroneRoutes() {
  isoRoutes := RouterGroup.Group("/isochrone")
  isoRoutes.Use(middleware.LimitAPIRequests(...))
  isoRoutes.Use(middleware.LimitTotalRequests(...))
  {
    isoRoutes.GET("/", controllers.GetIsochrone)
    // 【新增】過濾端點
    isoRoutes.POST("/filter", controllers.FilterIsochroneOverlaps)
  }
}
```

---

### 🔧 新增服務層

#### 8. `Taipei-City-Dashboard-BE/app/services/isochroneFilter.go` ⭐⭐⭐ **[新建必須]**

**檔案大小**: TBD  
**責任**: 重疊檢測核心邏輯

**建議實現結構**:
```go
package services

import (
  "database/sql"
  "encoding/json"
  "fmt"
)

// IsochroneFilterRequest 過濾請求參數
type IsochroneFilterRequest struct {
  Lng          string `json:"lng"`
  Lat          string `json:"lat"`
  Profile      string `json:"profile"`
  Minutes      string `json:"minutes"`      // 逗號分隔
  ComponentIDs string `json:"component_ids"` // 逗號分隔
}

// FilterResult 過濾結果
type FilterResult struct {
  Minutes string      `json:"minutes"`      // 等時圈分鐘數
  POIs    []POI       `json:"pois"`         // 重疊的 POI
  Count   int         `json:"count"`
}

type POI struct {
  ID        int64   `json:"id"`
  Name      string  `json:"name"`
  Latitude  float64 `json:"lat"`
  Longitude float64 `json:"lng"`
  // 其他屬性
}

/**
 * GetIsochroneOverlappingPOIs - 獲取等時圈內的重疊 POI
 * 
 * 流程：
 * 1. 調用 Mapbox Isochrone API 獲取等時圈 polygon
 * 2. 根據 componentIDs 查詢組件對應的 SQL 查詢
 * 3. 執行查詢獲取 POI 座標
 * 4. 使用 PostGIS ST_Contains 檢測重疊
 * 5. 返回結果
 */
func GetIsochroneOverlappingPOIs(
  ctx context.Context,
  req IsochroneFilterRequest,
) (map[string][]POI, error) {
  // 實現細節...
}

/**
 * ParseComponentQuery - 解析組件 SQL 查詢
 * 
 * 從 component_maps 表中查詢對應的地理查詢
 */
func ParseComponentQuery(componentID int64) (query string, sourceType string, err error) {
  // 實現細節...
}

/**
 * ExecuteOverlapQuery - 使用 PostGIS 執行重疊查詢
 * 
 * 支持兩種方式：
 * 1. 直接在 PostgreSQL 中使用 ST_Contains (推薦，性能佳)
 * 2. 在應用層進行計算 (備用方案)
 */
func ExecuteOverlapQuery(
  ctx context.Context,
  isochroneGeoJSON string,
  minutes []int,
  componentID int64,
) ([]POI, error) {
  // 實現細節...
}
```

**建議技術**:
- **PostgreSQL PostGIS**: `ST_Contains()` 檢測點在多邊形內
- **SQL 示例**:
```sql
SELECT poi_id, poi_name, ST_AsGeoJSON(geometry) AS geom
FROM bus_stops
WHERE ST_Contains(
  ST_GeomFromGeoJSON($1),  -- 等時圈 polygon GeoJSON
  geometry
)
AND district = $2;
```

---

### 📝 其他後端檔案

#### 9. `Taipei-City-Dashboard-BE/app/services/ai/ai_service.go`

**用途**: AI 服務核心邏輯  
**責任**: 調用 LLM、處理工具執行

**修改需求**: 無需修改

---

#### 10. `Taipei-City-Dashboard-BE/app/cache/redis.go`

**用途**: Redis 快取  
**現有用法**: 等時圈結果快取

**可利用**: 快取過濾結果

**修改需求**: 無需修改

---

## 演示 Dashboard

### 📊 現有演示組件

#### 1. **公車站點分布** (Component ID: 301)

| 項目 | 詳情 |
|------|------|
| **Dashboard Index** | `bus_stop_tpe` (臺北市) / `bus_stop_newtpe` (雙北) |
| **Dashboard ID** | 370 / 371 |
| **數據表** | `public.bus_stop_tpe` |
| **圖表類型** | DistrictChart, ColumnChart |
| **數據來源** | tcgbusfs / tcgbusfs+ntpcbus |
| **更新頻率** | 靜態 (static) |
| **查詢語句** | 按行政區統計公車站牌數量 |

**配置檔案**:
```
/New_dashboard/bus_stop_by_district/patch_manager.sql
/New_dashboard/bus_stop_by_district/setup.py
```

---

#### 2. **公車候車時間** (Component ID: 302) ⭐ **[推薦使用]**

| 項目 | 詳情 |
|------|------|
| **Dashboard Index** | `bus_estimate_tpe` (臺北市) / `bus_estimate_newtpe` (雙北) |
| **Dashboard ID** | 372 / 373 |
| **圖層配置 ID** | 110 (臺北) / 111 (雙北) |
| **圖層類型** | Circle (點圖) |
| **數據表** | `bus_estimate_time_tpe`, `bus_route_stops_tpe`, `bus_stop_tpe` |
| **地圖顯示** | 按候車時間著色的公車站點 |
| **更新頻率** | 每 5 分鐘 (current) |
| **顏色編碼** | 灰=無資料, 紅=<3分, 橙=<6分, 黃=<10分, 綠=≥10分 |

**關鍵特性**:
- ✅ 已有座標數據 (latitude, longitude)
- ✅ 已有時間戳記（實時更新）
- ✅ 已定義視覺樣式
- ✅ 最適合演示重疊檢測

**配置檔案**:
```
/New_dashboard/bus_avg_estimate_by_district/patch_manager.sql
/New_dashboard/bus_avg_estimate_by_district/setup.py
```

**地圖配置 SQL**:
```sql
INSERT INTO public.component_maps (id, index, title, type, source, paint, property)
VALUES (
    110,
    'bus_stop_estimate_tpe',
    '公車站點',
    'circle',
    'geojson',
    '{"circle-radius":4,"circle-opacity":0.8,"circle-color":[...]}'
    '[{"key":"stop_name","name":"站牌名稱"},...,"nearest_estimate_min","name":"最近到站(分)"]'
);
```

---

### 🗄️ 演示數據源

#### SQL 初始化檔案
```
/db-sample-data/dashboard-demo.sql           (2.4 MB - 完整示範數據)
/db-sample-data/dashboardmanager-demo.sql    (46 KB - 管理員配置)
```

#### 主要表結構
```
bus_stop_tpe
├── stop_location_id
├── stop_name
├── district
├── geo_city
├── latitude
├── longitude
└── ...

bus_estimate_time_tpe
├── stop_id
├── estimate_time (秒)
├── city
└── ...

bus_route_stops_tpe
├── stop_id
├── stop_location_id
├── city
└── ...
```

---

### 🎯 推薦演示場景

**最佳演示 Dashboard**: `bus_estimate_tpe` (公車候車時間 - 臺北市)

**演示步驟**:
1. 打開 MapView，選擇 "公車候車時間" dashboard
2. 地圖自動加載公車站點圖層（圓點顯示，按候車時間著色）
3. 打開 Chat 面板
4. 輸入: **"台北車站周邊 30 分鐘內可到的公車站點有哪些?"**
5. 預期結果:
   - 等時圈多邊形在地圖上繪製
   - 站點列表在 chat 中顯示
   - 重疊的公車站點高亮顯示（可選：不同顏色或加粗邊框）

**預期數據量**:
- 等時圈半徑: ~10km (30 分鐘開車)
- 公車站點數: ~50-150 個
- 重疊站點: ~20-50 個

---

## 文件修改優先級

### 🔴 必須修改 (Critical Path)

| # | 檔案 | 類型 | 影響 | 工時估計 |
|---|------|------|------|----------|
| 1 | `isochrone.go` | 後端控制器 | 新增 `/filter` 端點 | 4h |
| 2 | `isochroneFilter.go` | 後端服務 | 核心重疊檢測邏輯 | 6-8h |
| 3 | `router.go` | 後端路由 | 註冊新端點 | 0.5h |
| 4 | `mapStore.js` | 前端狀態 | 顯示重疊結果圖層 | 3-4h |
| 5 | `chatStore.js` | 前端狀態 | 調用過濾 API | 2-3h |

**總工時估計**: 15-20 小時

---

### 🟡 建議修改 (Enhancement)

| # | 檔案 | 類型 | 理由 |
|---|------|------|------|
| 1 | `showIsochrone.go` | 後端工具 | 在 action 中新增 `componentIds` 欄位 |
| 2 | `geometryUtils.js` | 前端工具 | 新增重疊檢測工具函式（前端備用方案） |
| 3 | `MapContainer.vue` | 前端組件 | 新增重疊結果圖層切換 UI |

---

### 🟢 無需修改

| # | 檔案 | 類型 | 原因 |
|---|------|------|------|
| 1 | `ai.go` | 後端控制器 | 已支持 tool_actions |
| 2 | `componentConfig.go` | 後端模型 | 只需讀取 |
| 3 | `contentStore.js` | 前端狀態 | 只需查詢 |
| 4 | `MapView.vue` | 前端組件 | 作為展示層，無需改動 |

---

## 技術資源

### 🎮 前端可用庫

| 庫 | 版本 | 用途 | 狀態 |
|----|------|------|------|
| `@turf/turf` | ✅ | 地理計算 (point, distance, booleanPointInPolygon) | 已引入 |
| `mapbox-gl` | ✅ | 地圖引擎 | 已集成 |
| `vue` 3 | ✅ | 前端框架 | 已配置 |
| `pinia` | ✅ | 狀態管理 | 已配置 |
| `axios` | ✅ | HTTP 客戶端 | 已配置 |

**前端地理計算建議**:
```javascript
import { booleanPointInPolygon, intersect, feature } from '@turf/turf';

// 檢測點在多邊形內
const pt = point([lng, lat]);
const poly = feature(isochroneGeoJSON.features[0].geometry);
if (booleanPointInPolygon(pt, poly)) {
  // 點在多邊形內
}
```

---

### 🗄️ 後端可用資源

| 資源 | 版本 | 用途 | 狀態 |
|------|------|------|------|
| PostgreSQL | 12+ | 空間數據庫 | ✅ 已配置 |
| PostGIS | 3.0+ | 空間查詢 | ✅ 可用 |
| GORM | 1.24+ | ORM 框架 | ✅ 已使用 |
| Go `database/sql` | - | 原始 SQL | ✅ 可用 |
| Redis | - | 快取 | ✅ 已集成 |

**後端空間查詢建議**:
```sql
-- PostGIS 方法（最高效）
SELECT * FROM bus_stops
WHERE ST_Contains(
  ST_GeomFromGeoJSON($1),  -- 等時圈 polygon
  ST_Point(longitude, latitude)
);

-- 或使用 ST_DWithin 檢測距離
SELECT * FROM bus_stops
WHERE ST_DWithin(
  ST_GeomFromGeoJSON($1),
  ST_Point(longitude, latitude),
  0  -- 邊界內
);
```

---

### 🔌 現有 API 端點

| 端點 | 方法 | 用途 | 狀態 |
|------|------|------|------|
| `/api/v1/isochrone` | GET | 獲取等時圈 | ✅ 已實現 |
| `/api/v1/ai/chat/twai` | POST | LLM 聊天 | ✅ 已實現 |
| `/api/v1/component` | GET | 查詢組件 | ✅ 已實現 |
| `/api/v1/isochrone/filter` | POST | 過濾重疊 POI | ❌ 需新增 |

---

## 實現步驟

### Phase 1: 規劃與設計 (1-2 天)

- [ ] 確認數據庫中是否有 PostGIS 擴展
- [ ] 確認公車站點表的空間索引設置
- [ ] 設計 API 契約（請求/響應格式）
- [ ] 確定前端重疊結果的視覺呈現方式
- [ ] 確定是否需要自行車路網等其他圖層

**關鍵決策**:
1. **計算位置**: 後端 (推薦) vs 前端
2. **快取策略**: 等時圈快取時間、過濾結果快取
3. **性能考量**: 批量查詢 vs 逐個檢測

---

### Phase 2: 後端實現 (3-4 天)

#### Step 1: 新建過濾服務
```bash
# 新建檔案
touch app/services/isochroneFilter.go
```

**實現內容**:
- [ ] 定義請求/響應結構
- [ ] 實現 `FilterIsochroneOverlaps()` 主函數
- [ ] 實現 PostGIS 空間查詢
- [ ] 添加錯誤處理和日誌

#### Step 2: 新增控制器方法
**檔案**: `app/controllers/isochrone.go`
- [ ] 新增 `FilterIsochroneOverlaps()` 方法
- [ ] 參數驗證
- [ ] 調用過濾服務
- [ ] 結果快取

#### Step 3: 註冊路由
**檔案**: `app/routes/router.go`
- [ ] 在 `configureIsochroneRoutes()` 中新增 POST `/filter` 路由
- [ ] 應用中間件 (限流、認證等)

#### Step 4: 單元測試
```bash
# 新建測試檔案
touch app/services/isochroneFilter_test.go
```
- [ ] 測試重疊檢測邏輯
- [ ] 測試邊界情況
- [ ] 測試性能

---

### Phase 3: 前端實現 (2-3 天)

#### Step 1: 修改 mapStore
**檔案**: `src/store/mapStore.js`
- [ ] 新增 `isochroneOverlaps` 狀態
- [ ] 實現 `addOverlappingPOIsLayer()` 方法
- [ ] 實現 `removeOverlappingPOIsLayer()` 方法
- [ ] 實現 `toggleOverlapLayerVisibility()` 方法

#### Step 2: 修改 chatStore
**檔案**: `src/store/chatStore.js`
- [ ] 在 `handleToolAction()` 中調用過濾 API
- [ ] 處理 API 回應
- [ ] 調用 mapStore 顯示結果

#### Step 3: 視覺呈現
**檔案**: `src/store/mapStore.js`
- [ ] 為不同時間等級的重疊結果設置不同顏色
- [ ] 新增 popup 顯示 POI 詳細信息
- [ ] 新增圖層切換控制 UI

#### Step 4: 集成測試
- [ ] 從 Chat 輸入測試完整流程
- [ ] 測試不同的公車站點組件
- [ ] 測試不同的等時圈時間

---

### Phase 4: 優化與部署 (1-2 天)

- [ ] 性能測試和優化
- [ ] 快取策略優化
- [ ] 錯誤處理完善
- [ ] 文件編寫
- [ ] 代碼審查
- [ ] 部署到測試環境

---

## 附錄: 快速參考

### 📊 Component ID 對應表

| 編號 | Index | 名稱 | 類型 | 數據表 | 地圖配置 ID |
|------|-------|------|------|--------|------------|
| 301 | bus_stop_by_district | 公車站牌數量 | 柱狀圖 | bus_stop_tpe | - |
| 302 | bus_avg_estimate_by_district | 公車候車時間 | 柱狀圖 + 地圖 | bus_estimate_time_tpe | 110/111 |

---

### 🗺️ Dashboard 對應表

| Dashboard Index | 城市 | Component IDs | 適用場景 |
|-----------------|------|--------------|---------|
| bus_stop_tpe | 臺北市 | 301 | 查看各區公車站牌分布 |
| bus_stop_newtpe | 雙北 | 301 | 查看雙北公車站牌分布 |
| bus_estimate_tpe | 臺北市 | 302 | 查看各區公車候車時間 **⭐** |
| bus_estimate_newtpe | 雙北 | 302 | 查看雙北公車候車時間 **⭐** |

---

### 🔗 相關 URLs

| 資源 | 鏈接 |
|------|------|
| Mapbox Isochrone API | https://docs.mapbox.com/api/navigation/isochrone/ |
| Turf.js 文檔 | https://turfjs.org/ |
| PostGIS 空間查詢 | https://postgis.net/docs/ |
| GORM 文檔 | https://gorm.io/docs/ |
| Mapbox GL JS | https://docs.mapbox.com/mapbox-gl-js/ |

---

## 結論

該文檔提供了完整的實現路線圖，涵蓋了 **5 個必須修改的檔案** 和 **3 個建議修改的檔案**。

**建議優先級**:
1. 確定演示 Dashboard (`bus_estimate_tpe`)
2. 實現後端過濾服務 (~6-8h)
3. 新增前端圖層顯示 (~3-4h)
4. 集成測試與優化 (~2-3h)

**預期完成時間**: 15-20 小時（一個開發者，2-3 天）

---

**文檔編製日期**: 2026-05-03  
**版本**: 1.0  
**作者**: Claude Code Analysis
