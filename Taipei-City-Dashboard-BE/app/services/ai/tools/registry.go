package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"TaipeiCityDashboardBE/app/models"

	"github.com/tmc/langchaingo/llms"
)

// ToolFunc defines the signature for a tool function
type ToolFunc func(ctx context.Context, args string) (string, error)

var (
	registry         = make(map[string]ToolFunc)
	toolDefinitions = make(map[string]llms.Tool)
	toolOrder       []string
)

// CurrentTimeTool defines the current time tool for the LLM.
var CurrentTimeTool = llms.Tool{
	Type: "function",
	Function: &llms.FunctionDefinition{
		Name:        "get_current_time",
		Description: "取得目前臺北時區的日期與時間。當用戶詢問現在時間、今天日期或需要以目前時間作為回答依據時使用。",
		Parameters: map[string]interface{}{
			"type":       "object",
			"properties": map[string]interface{}{},
		},
	},
}

// PopulationSummaryTool defines the population summary tool for the LLM.
var PopulationSummaryTool = llms.Tool{
	Type: "function",
	Function: &llms.FunctionDefinition{
		Name:        "get_population_summary",
		Description: "查詢臺北市或新北市指定年份的人口年齡結構統計，包含幼年、青壯年、老年與總人口。",
		Parameters: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"city": map[string]interface{}{
					"type":        "string",
					"description": "查詢城市。臺北市使用 taipei，新北市使用 new_taipei；未提供時預設臺北市。",
					"enum":        []string{"taipei", "new_taipei"},
				},
				"year": map[string]interface{}{
					"type":        "integer",
					"description": "要查詢的西元年份，例如 2024。",
				},
			},
			"required": []string{"year"},
		},
	},
}

// SearchComponentsTool defines the component hybrid search tool for the LLM.
var SearchComponentsTool = llms.Tool{
	Type: "function",
	Function: &llms.FunctionDefinition{
		Name:        "search_components_hybrid",
		Description: "搜尋臺北城市儀表板中與用戶問題相關的資料視覺化元件。當用戶想了解特定城市議題或數據時使用此工具。",
		Parameters: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"query": map[string]interface{}{
					"type":        "string",
					"description": "從用戶輸入中萃取的搜尋關鍵字，用繁體中文描述主題",
				},
				"limit": map[string]interface{}{
					"type":        "integer",
					"description": "回傳的元件數量，預設 8，最多 15",
				},
			},
			"required": []string{"query"},
		},
	},
}

func init() {
	RegisterTool(CurrentTimeTool, GetCurrentTime)
	RegisterTool(PopulationSummaryTool, GetPopulationSummary)
	RegisterTool(SearchComponentsTool, SearchComponentsHybrid)
}

// Register adds a tool to the registry
func Register(name string, fn ToolFunc) {
	registry[name] = fn
	if _, exists := toolDefinitions[name]; exists {
		return
	}

	toolDefinitions[name] = llms.Tool{
		Type: "function",
		Function: &llms.FunctionDefinition{
			Name: name,
			Parameters: map[string]interface{}{
				"type":       "object",
				"properties": map[string]interface{}{},
			},
		},
	}
	toolOrder = append(toolOrder, name)
}

// RegisterTool adds an executable tool and its LLM-facing definition to the registry.
func RegisterTool(tool llms.Tool, fn ToolFunc) {
	if tool.Function == nil || tool.Function.Name == "" {
		return
	}

	name := tool.Function.Name
	if _, exists := toolDefinitions[name]; !exists {
		toolOrder = append(toolOrder, name)
	}
	toolDefinitions[name] = tool
	Register(name, fn)
}

// RegisteredTools returns all executable tools that should be exposed to the LLM.
func RegisteredTools() []llms.Tool {
	tools := make([]llms.Tool, 0, len(toolOrder))
	for _, name := range toolOrder {
		tools = append(tools, toolDefinitions[name])
	}
	return tools
}

// Execute calls a registered tool with the given arguments
func Execute(ctx context.Context, name string, args string) (string, error) {
	fn, ok := registry[name]
	if !ok {
		return "", fmt.Errorf("tool %s not found", name)
	}
	return fn(ctx, args)
}

// PopulationArgs defines the arguments for the get_population_summary tool
type PopulationArgs struct {
	City string `json:"city"`
	Year int    `json:"year"`
}

// GetPopulationSummary queries the population age distribution from the dashboard database
func GetPopulationSummary(ctx context.Context, args string) (string, error) {
	var params PopulationArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}

	// Default to Taipei if not specified or unrecognized
	tableName := "population_age_distribution_tpe"
	cityName := "台北市"
	if params.City == "new_taipei" {
		tableName = "population_age_distribution_new_tpe"
		cityName = "新北市"
	}

	// Define result structure based on database schema
	var result struct {
		Year     int       `gorm:"column:year"`
		Young    int       `gorm:"column:young_population"`
		Working  int       `gorm:"column:working_age_population"`
		Elderly  int       `gorm:"column:elderly_population"`
		DataTime time.Time `gorm:"column:data_time"`
	}

	// Query the dashboard database
	err := models.DBDashboard.Table(tableName).
		Where("year = ?", params.Year).
		Order("data_time DESC"). // Get the latest record for that year
		First(&result).Error

	if err != nil {
		return "", fmt.Errorf("找不到 %s %d 年的人口統計資料: %v", cityName, params.Year, err)
	}

	// Format the response for the LLM
	return fmt.Sprintf(
		"【%d年 %s 人口結構概況】\n- 幼年人口 (0-14歲)：%d 人\n- 青壯年人口 (15-64歲)：%d 人\n- 老年人口 (65歲以上)：%d 人\n- 總人口： %d 人\n- 數據更新時間：%s",
		result.Year, cityName, result.Young, result.Working, result.Elderly,
		result.Young+result.Working+result.Elderly,
		result.DataTime.Format("2006-01-02"),
	), nil
}

// GetCurrentTime is a demo tool that returns the current Taipei time
func GetCurrentTime(ctx context.Context, args string) (string, error) {
	loc, err := time.LoadLocation("Asia/Taipei")
	if err != nil {
		// Fallback to UTC if timezone data is missing
		return time.Now().Format(time.RFC3339), nil
	}
	return time.Now().In(loc).Format("2006-01-02 15:04:05"), nil
}

// Helper to parse JSON arguments if needed in future tools
func parseArgs(args string, v interface{}) error {
	return json.Unmarshal([]byte(args), v)
}
