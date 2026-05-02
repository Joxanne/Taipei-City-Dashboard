package tools

import (
	"context"
	"strings"
	"testing"
)

func testToolHandler(ctx context.Context, args string) (string, error) {
	return "ok:" + args, nil
}

func TestToolBuilderNoParams(t *testing.T) {
	registration := NewTool("test_no_params", "description", testToolHandler).NoParams()
	if registration == nil {
		t.Fatal("expected registration")
	}
	if registration.tool.Function == nil {
		t.Fatal("expected function definition")
	}
	if registration.tool.Function.Description != "description" {
		t.Fatalf("unexpected description: %q", registration.tool.Function.Description)
	}

	parameters, ok := registration.tool.Function.Parameters.(map[string]interface{})
	if !ok {
		t.Fatalf("expected map parameters, got %T", registration.tool.Function.Parameters)
	}
	if parameters["type"] != "object" {
		t.Fatalf("expected object parameters, got %v", parameters["type"])
	}
	properties, ok := parameters["properties"].(map[string]interface{})
	if !ok {
		t.Fatalf("expected properties map, got %T", parameters["properties"])
	}
	if len(properties) != 0 {
		t.Fatalf("expected empty properties, got %#v", properties)
	}
	if _, exists := parameters["required"]; exists {
		t.Fatalf("did not expect required for no-params schema")
	}
}

func TestToolBuilderRequiredAndOptionalParams(t *testing.T) {
	registration := NewTool("test_params", "description", testToolHandler).
		OptionalStringEnum("city", "city description", "taipei", "new_taipei").
		RequiredInteger("year", "year description").
		Build()

	parameters := registration.tool.Function.Parameters.(map[string]interface{})
	properties := parameters["properties"].(map[string]interface{})

	city := properties["city"].(map[string]interface{})
	if city["type"] != "string" || city["description"] != "city description" {
		t.Fatalf("unexpected city schema: %#v", city)
	}
	cityEnum := city["enum"].([]string)
	if len(cityEnum) != 2 || cityEnum[0] != "taipei" || cityEnum[1] != "new_taipei" {
		t.Fatalf("unexpected city enum: %#v", cityEnum)
	}

	year := properties["year"].(map[string]interface{})
	if year["type"] != "integer" || year["description"] != "year description" {
		t.Fatalf("unexpected year schema: %#v", year)
	}

	required := parameters["required"].([]string)
	if len(required) != 1 || required[0] != "year" {
		t.Fatalf("unexpected required fields: %#v", required)
	}
}

func TestRegisterValidation(t *testing.T) {
	tests := []struct {
		name         string
		registration *ToolRegistration
		wantErr      string
	}{
		{name: "nil registration", registration: nil, wantErr: "registration"},
		{name: "missing name", registration: NewTool("", "description", testToolHandler).NoParams(), wantErr: "name"},
		{name: "missing description", registration: NewTool("test_missing_description", "", testToolHandler).NoParams(), wantErr: "description"},
		{name: "missing handler", registration: NewTool("test_missing_handler", "description", nil).NoParams(), wantErr: "handler"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := Register(tt.registration)
			if err == nil {
				t.Fatal("expected error")
			}
			if !strings.Contains(err.Error(), tt.wantErr) {
				t.Fatalf("expected error containing %q, got %q", tt.wantErr, err.Error())
			}
		})
	}
}

func TestMustRegisterValidationPanics(t *testing.T) {
	defer func() {
		if recover() == nil {
			t.Fatal("expected panic")
		}
	}()

	MustRegister(NewTool("test_missing_description_panic", "", testToolHandler).NoParams())
}

func TestRegisterDeduplicatesRegisteredTools(t *testing.T) {
	name := "test_duplicate_tool"
	firstDescription := "first description"
	secondDescription := "second description"

	if err := Register(NewTool(name, firstDescription, testToolHandler).NoParams()); err != nil {
		t.Fatalf("register first: %v", err)
	}
	if err := Register(NewTool(name, secondDescription, testToolHandler).NoParams()); err != nil {
		t.Fatalf("register second: %v", err)
	}

	count := 0
	var description string
	for _, tool := range RegisteredTools() {
		if tool.Function != nil && tool.Function.Name == name {
			count++
			description = tool.Function.Description
		}
	}
	if count != 1 {
		t.Fatalf("expected one registered tool named %s, got %d", name, count)
	}
	if description != secondDescription {
		t.Fatalf("expected updated definition, got %q", description)
	}
}

func TestRegisteredToolsIncludeBuiltInsWithRequiredTWCCFields(t *testing.T) {
	expected := map[string]bool{
		"get_current_time":         false,
		"get_population_summary":   false,
		"search_components_hybrid": false,
	}

	for _, tool := range RegisteredTools() {
		if tool.Function == nil {
			t.Fatalf("tool has nil function: %#v", tool)
		}
		if _, ok := expected[tool.Function.Name]; !ok {
			continue
		}
		expected[tool.Function.Name] = true
		if tool.Type != "function" {
			t.Fatalf("tool %s has unexpected type %q", tool.Function.Name, tool.Type)
		}
		if tool.Function.Name == "" {
			t.Fatal("tool name is required")
		}
		if tool.Function.Description == "" {
			t.Fatalf("tool %s missing description", tool.Function.Name)
		}
		if tool.Function.Parameters == nil {
			t.Fatalf("tool %s missing parameters", tool.Function.Name)
		}
		parameters, ok := tool.Function.Parameters.(map[string]interface{})
		if !ok {
			t.Fatalf("tool %s parameters should be map, got %T", tool.Function.Name, tool.Function.Parameters)
		}
		if parameters["type"] != "object" {
			t.Fatalf("tool %s parameters should be object, got %v", tool.Function.Name, parameters["type"])
		}
		if _, ok := parameters["properties"].(map[string]interface{}); !ok {
			t.Fatalf("tool %s properties should be map", tool.Function.Name)
		}
	}

	for name, found := range expected {
		if !found {
			t.Fatalf("expected registered tool %s", name)
		}
	}
}

func TestExecuteRegisteredHandler(t *testing.T) {
	name := "test_execute_tool"
	if err := Register(NewTool(name, "description", testToolHandler).NoParams()); err != nil {
		t.Fatalf("register: %v", err)
	}

	got, err := Execute(context.Background(), name, `{"value":1}`)
	if err != nil {
		t.Fatalf("execute: %v", err)
	}
	if got != `ok:{"value":1}` {
		t.Fatalf("unexpected result: %q", got)
	}
}
