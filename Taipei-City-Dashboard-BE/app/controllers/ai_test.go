package controllers

import (
	"testing"

	aiTools "TaipeiCityDashboardBE/app/services/ai/tools"

	"github.com/tmc/langchaingo/llms"
)

func TestAIChatInputToCallOptionsIncludesRegisteredTools(t *testing.T) {
	input := &AIChatInput{}
	callOptions := llms.CallOptions{}
	for _, option := range input.ToCallOptions() {
		option(&callOptions)
	}

	expected := map[string]bool{
		"get_current_time":         false,
		"get_population_summary":   false,
		"search_components_hybrid": false,
	}
	for _, tool := range callOptions.Tools {
		if tool.Function != nil {
			if _, ok := expected[tool.Function.Name]; ok {
				expected[tool.Function.Name] = true
			}
		}
	}
	for name, found := range expected {
		if !found {
			t.Fatalf("expected ToCallOptions to include registered tool %s", name)
		}
	}
}

func TestAIChatInputToCallOptionsDeduplicatesRequestTools(t *testing.T) {
	input := &AIChatInput{}
	input.Tools = append(input.Tools, struct {
		Type     string `json:"type" binding:"required,eq=function"`
		Function struct {
			Name        string      `json:"name" binding:"required"`
			Description string      `json:"description,omitempty"`
			Parameters  interface{} `json:"parameters,omitempty"`
		} `json:"function" binding:"required"`
	}{
		Type: "function",
		Function: struct {
			Name        string      `json:"name" binding:"required"`
			Description string      `json:"description,omitempty"`
			Parameters  interface{} `json:"parameters,omitempty"`
		}{
			Name: "get_current_time",
		},
	})

	callOptions := llms.CallOptions{}
	for _, option := range input.ToCallOptions() {
		option(&callOptions)
	}

	count := 0
	for _, tool := range callOptions.Tools {
		if tool.Function != nil && tool.Function.Name == "get_current_time" {
			count++
			if tool.Function.Description == "" {
				t.Fatal("expected request tool to inherit registered description")
			}
			if tool.Function.Parameters == nil {
				t.Fatal("expected request tool to inherit registered parameters")
			}
		}
	}
	if count != 1 {
		t.Fatalf("expected get_current_time once, got %d", count)
	}
}

func TestAIChatInputToCallOptionsNoMissingDescriptionSchemas(t *testing.T) {
	input := &AIChatInput{}
	input.Tools = append(input.Tools, struct {
		Type     string `json:"type" binding:"required,eq=function"`
		Function struct {
			Name        string      `json:"name" binding:"required"`
			Description string      `json:"description,omitempty"`
			Parameters  interface{} `json:"parameters,omitempty"`
		} `json:"function" binding:"required"`
	}{
		Type: "function",
		Function: struct {
			Name        string      `json:"name" binding:"required"`
			Description string      `json:"description,omitempty"`
			Parameters  interface{} `json:"parameters,omitempty"`
		}{
			Name: "request_tool_without_schema",
		},
	})

	callOptions := llms.CallOptions{}
	for _, option := range input.ToCallOptions() {
		option(&callOptions)
	}

	if len(callOptions.Tools) < len(aiTools.RegisteredTools())+1 {
		t.Fatalf("expected request and registered tools, got %d", len(callOptions.Tools))
	}
	for _, tool := range callOptions.Tools {
		if tool.Function == nil {
			t.Fatalf("tool has nil function: %#v", tool)
		}
		if tool.Function.Name == "" {
			t.Fatal("tool missing name")
		}
		if tool.Function.Description == "" {
			t.Fatalf("tool %s missing description", tool.Function.Name)
		}
		if tool.Function.Parameters == nil {
			t.Fatalf("tool %s missing parameters", tool.Function.Name)
		}
	}
}
