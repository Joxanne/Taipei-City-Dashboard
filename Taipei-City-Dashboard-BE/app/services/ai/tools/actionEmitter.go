package tools

import (
	"context"
	"encoding/json"
	"fmt"
)

type contextKey string

const (
	streamingFuncKey  contextKey = "streaming_func"
	toolActionSinkKey contextKey = "tool_action_sink"
)

// ToolActionEvent is a structured UI action emitted by an AI tool.
type ToolActionEvent struct {
	Type    string      `json:"type"`
	Action  string      `json:"action"`
	Payload interface{} `json:"payload"`
}

// WithStreamingFunc injects a streaming function into context for tool UI events.
func WithStreamingFunc(ctx context.Context, fn func(context.Context, []byte) error) context.Context {
	return context.WithValue(ctx, streamingFuncKey, fn)
}

// WithToolActionSink injects a collector for non-streaming tool UI events.
func WithToolActionSink(ctx context.Context, fn func(ToolActionEvent)) context.Context {
	return context.WithValue(ctx, toolActionSinkKey, fn)
}

// EmitToolAction records a structured tool_action event and streams it when SSE is active.
func EmitToolAction(ctx context.Context, action string, payload interface{}) {
	event := ToolActionEvent{
		Type:    "tool_action",
		Action:  action,
		Payload: payload,
	}

	if sink, ok := ctx.Value(toolActionSinkKey).(func(ToolActionEvent)); ok && sink != nil {
		sink(event)
	}

	fn, ok := ctx.Value(streamingFuncKey).(func(context.Context, []byte) error)
	if !ok || fn == nil {
		return
	}

	data, err := json.Marshal(event)
	if err != nil {
		return
	}
	_ = fn(ctx, []byte(fmt.Sprintf("data: %s\n\n", data)))
}
