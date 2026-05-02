package tools

import (
	"context"
	"encoding/json"
	"testing"
)

func TestHandleShowIsochroneDefaultsToThirtyMinutes(t *testing.T) {
	var actions []ToolActionEvent
	ctx := WithToolActionSink(context.Background(), func(event ToolActionEvent) {
		actions = append(actions, event)
	})

	result, err := handleShowIsochrone(ctx, `{"lng":"121.5170","lat":"25.0478"}`)
	if err != nil {
		t.Fatalf("handleShowIsochrone: %v", err)
	}

	var decoded map[string]interface{}
	if err := json.Unmarshal([]byte(result), &decoded); err != nil {
		t.Fatalf("decode result: %v", err)
	}
	minutes := decoded["minutes"].([]interface{})
	if len(minutes) != 1 || minutes[0].(float64) != 30 {
		t.Fatalf("expected default [30], got %#v", minutes)
	}

	if len(actions) != 1 {
		t.Fatalf("expected one emitted action, got %d", len(actions))
	}
	if actions[0].Action != "show_isochrone" {
		t.Fatalf("unexpected action: %q", actions[0].Action)
	}
}

func TestParseIsochroneMinutesSortsAndDeduplicates(t *testing.T) {
	minutes, err := parseIsochroneMinutes("30,10,30,20")
	if err != nil {
		t.Fatalf("parseIsochroneMinutes: %v", err)
	}

	want := []int{10, 20, 30}
	if len(minutes) != len(want) {
		t.Fatalf("expected %v, got %v", want, minutes)
	}
	for i := range want {
		if minutes[i] != want[i] {
			t.Fatalf("expected %v, got %v", want, minutes)
		}
	}
}

func TestParseIsochroneMinutesTruncatesTooManyContours(t *testing.T) {
	minutes, err := parseIsochroneMinutes("5,10,15,20,25")
	if err != nil {
		t.Fatalf("parseIsochroneMinutes: %v", err)
	}

	want := []int{5, 10, 15, 20}
	if len(minutes) != len(want) {
		t.Fatalf("expected %v, got %v", want, minutes)
	}
	for i := range want {
		if minutes[i] != want[i] {
			t.Fatalf("expected %v, got %v", want, minutes)
		}
	}
}

func TestNormalizeTaipeiLocationQuery(t *testing.T) {
	if got := normalizeTaipeiLocationQuery("大安森林公園"); got != "大安森林公園 台北" {
		t.Fatalf("unexpected normalized query: %q", got)
	}
	if got := normalizeTaipeiLocationQuery("新北市政府"); got != "新北市政府" {
		t.Fatalf("unexpected normalized query: %q", got)
	}
}
