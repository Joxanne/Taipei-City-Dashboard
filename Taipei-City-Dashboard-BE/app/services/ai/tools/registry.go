package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"

	"github.com/tmc/langchaingo/llms"
)

// ToolFunc defines the signature for a tool function
type ToolFunc func(ctx context.Context, args string) (string, error)

// ToolRegistration contains a validated LLM-facing definition and its executor.
type ToolRegistration struct {
	tool    llms.Tool
	handler ToolFunc
}

// ToolBuilder builds the schema required to expose a tool to the LLM.
type ToolBuilder struct {
	name        string
	description string
	handler     ToolFunc
	properties  map[string]interface{}
	required    []string
}

var (
	registryMu      sync.RWMutex
	registry        = make(map[string]ToolFunc)
	toolDefinitions = make(map[string]llms.Tool)
	toolOrder       []string
)

// NewTool creates a builder for a function tool with its executor.
func NewTool(name string, description string, handler ToolFunc) *ToolBuilder {
	return &ToolBuilder{
		name:        name,
		description: description,
		handler:     handler,
		properties:  make(map[string]interface{}),
	}
}

// NoParams builds a tool definition with a valid empty object parameters schema.
func (b *ToolBuilder) NoParams() *ToolRegistration {
	return b.Build()
}

// RequiredString adds a required string parameter.
func (b *ToolBuilder) RequiredString(name string, description string) *ToolBuilder {
	return b.addProperty(name, "string", description, true)
}

// OptionalString adds an optional string parameter.
func (b *ToolBuilder) OptionalString(name string, description string) *ToolBuilder {
	return b.addProperty(name, "string", description, false)
}

// RequiredStringEnum adds a required string enum parameter.
func (b *ToolBuilder) RequiredStringEnum(name string, description string, values ...string) *ToolBuilder {
	return b.addEnumProperty(name, "string", description, true, values...)
}

// OptionalStringEnum adds an optional string enum parameter.
func (b *ToolBuilder) OptionalStringEnum(name string, description string, values ...string) *ToolBuilder {
	return b.addEnumProperty(name, "string", description, false, values...)
}

// RequiredInteger adds a required integer parameter.
func (b *ToolBuilder) RequiredInteger(name string, description string) *ToolBuilder {
	return b.addProperty(name, "integer", description, true)
}

// OptionalInteger adds an optional integer parameter.
func (b *ToolBuilder) OptionalInteger(name string, description string) *ToolBuilder {
	return b.addProperty(name, "integer", description, false)
}

// Build returns a complete tool registration with a function schema.
func (b *ToolBuilder) Build() *ToolRegistration {
	parameters := map[string]interface{}{
		"type":       "object",
		"properties": cloneMap(b.properties),
	}
	if len(b.required) > 0 {
		parameters["required"] = append([]string(nil), b.required...)
	}

	return &ToolRegistration{
		tool: llms.Tool{
			Type: "function",
			Function: &llms.FunctionDefinition{
				Name:        b.name,
				Description: b.description,
				Parameters:  parameters,
			},
		},
		handler: b.handler,
	}
}

func (b *ToolBuilder) addProperty(name string, propertyType string, description string, required bool) *ToolBuilder {
	b.properties[name] = map[string]interface{}{
		"type":        propertyType,
		"description": description,
	}
	if required {
		b.addRequired(name)
	}
	return b
}

func (b *ToolBuilder) addEnumProperty(name string, propertyType string, description string, required bool, values ...string) *ToolBuilder {
	property := map[string]interface{}{
		"type":        propertyType,
		"description": description,
		"enum":        append([]string(nil), values...),
	}
	b.properties[name] = property
	if required {
		b.addRequired(name)
	}
	return b
}

func (b *ToolBuilder) addRequired(name string) {
	for _, existing := range b.required {
		if existing == name {
			return
		}
	}
	b.required = append(b.required, name)
}

// Register adds a complete tool schema and executor to the registry.
func Register(registration *ToolRegistration) error {
	if err := validateRegistration(registration); err != nil {
		return err
	}

	tool := cloneTool(registration.tool)
	name := tool.Function.Name

	registryMu.Lock()
	defer registryMu.Unlock()

	registry[name] = registration.handler
	if _, exists := toolDefinitions[name]; !exists {
		toolOrder = append(toolOrder, name)
	}
	toolDefinitions[name] = tool
	return nil
}

// MustRegister adds a complete tool schema and executor to the registry, panicking on invalid definitions.
func MustRegister(registration *ToolRegistration) {
	if err := Register(registration); err != nil {
		panic(err)
	}
}

func validateRegistration(registration *ToolRegistration) error {
	if registration == nil {
		return fmt.Errorf("tool registration is required")
	}
	if registration.handler == nil {
		return fmt.Errorf("tool handler is required")
	}
	if registration.tool.Type != "function" {
		return fmt.Errorf("tool type must be function")
	}
	if registration.tool.Function == nil {
		return fmt.Errorf("tool function definition is required")
	}
	if registration.tool.Function.Name == "" {
		return fmt.Errorf("tool function name is required")
	}
	if registration.tool.Function.Description == "" {
		return fmt.Errorf("tool function description is required")
	}
	if registration.tool.Function.Parameters == nil {
		return fmt.Errorf("tool function parameters are required")
	}
	return nil
}

// RegisteredTools returns all executable tools that should be exposed to the LLM.
func RegisteredTools() []llms.Tool {
	registryMu.RLock()
	defer registryMu.RUnlock()

	tools := make([]llms.Tool, 0, len(toolOrder))
	for _, name := range toolOrder {
		tool, exists := toolDefinitions[name]
		if !exists {
			continue
		}
		tools = append(tools, cloneTool(tool))
	}
	return tools
}

// Execute calls a registered tool with the given arguments.
func Execute(ctx context.Context, name string, args string) (string, error) {
	registryMu.RLock()
	fn, ok := registry[name]
	registryMu.RUnlock()
	if !ok {
		return "", fmt.Errorf("tool %s not found", name)
	}
	return fn(ctx, args)
}

// Helper to parse JSON arguments if needed in future tools
func parseArgs(args string, v interface{}) error {
	return json.Unmarshal([]byte(args), v)
}

func cloneTool(tool llms.Tool) llms.Tool {
	cloned := tool
	if tool.Function != nil {
		function := *tool.Function
		function.Parameters = cloneParameters(tool.Function.Parameters)
		cloned.Function = &function
	}
	return cloned
}

func cloneParameters(parameters interface{}) interface{} {
	switch typed := parameters.(type) {
	case map[string]interface{}:
		return cloneMap(typed)
	default:
		return typed
	}
}

func cloneMap(source map[string]interface{}) map[string]interface{} {
	cloned := make(map[string]interface{}, len(source))
	for key, value := range source {
		switch typed := value.(type) {
		case map[string]interface{}:
			cloned[key] = cloneMap(typed)
		case []string:
			cloned[key] = append([]string(nil), typed...)
		case []interface{}:
			cloned[key] = append([]interface{}(nil), typed...)
		default:
			cloned[key] = value
		}
	}
	return cloned
}
