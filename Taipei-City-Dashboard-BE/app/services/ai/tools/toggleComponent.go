package tools

import (
	"context"
	"encoding/json"
	"fmt"
)

type toggleComponentArgs struct {
	ComponentID int    `json:"component_id"`
	Visible     string `json:"visible"`
}

func init() {
	MustRegister(
		NewTool(
			"toggle_component",
			"開啟或關閉指定組件的地圖圖層。開啟後組件資料會疊加顯示在地圖上。只對有地圖圖層的組件使用此工具。",
			handleToggleComponent,
		).
			RequiredInteger("component_id", "要操作的組件 ID，來自系統檢索到的候選儀表板元件。").
			RequiredStringEnum("visible", "「true」開啟圖層，「false」關閉圖層。", "true", "false").
			Build(),
	)
}

func handleToggleComponent(ctx context.Context, args string) (string, error) {
	var params toggleComponentArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}
	if params.ComponentID <= 0 {
		return "", fmt.Errorf("component_id must be positive")
	}

	isVisible := params.Visible == "true"
	EmitToolAction(ctx, "toggle_component", map[string]interface{}{
		"component_id": params.ComponentID,
		"visible":      isVisible,
	})

	result, _ := json.Marshal(map[string]interface{}{
		"success":      true,
		"component_id": params.ComponentID,
		"visible":      isVisible,
	})
	return string(result), nil
}
