package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
)

type createComponentGroupArgs struct {
	GroupName    string `json:"group_name"`
	ComponentIDs []int  `json:"component_ids"`
}

func init() {
	MustRegister(
		NewTool(
			"create_component_group",
			"將多個組件組合成一個儀表板群組，顯示在使用者的儀表板側邊欄。請根據使用者問題取一個簡短描述性的群組名稱。",
			handleCreateComponentGroup,
		).
			RequiredString("group_name", "群組名稱，根據使用者問題取一個簡短描述性名稱。").
			RequiredIntegerArray("component_ids", "要加入群組的組件 ID 陣列，來自系統檢索到的候選儀表板元件。").
			Build(),
	)
}

func handleCreateComponentGroup(ctx context.Context, args string) (string, error) {
	var params createComponentGroupArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}

	params.GroupName = strings.TrimSpace(params.GroupName)
	if params.GroupName == "" {
		return "", fmt.Errorf("group_name is required")
	}
	if len(params.ComponentIDs) == 0 {
		return "", fmt.Errorf("component_ids must not be empty")
	}

	EmitToolAction(ctx, "create_group", map[string]interface{}{
		"group_name":    params.GroupName,
		"component_ids": params.ComponentIDs,
	})

	result, _ := json.Marshal(map[string]interface{}{
		"success":         true,
		"group_name":      params.GroupName,
		"component_count": len(params.ComponentIDs),
	})
	return string(result), nil
}
