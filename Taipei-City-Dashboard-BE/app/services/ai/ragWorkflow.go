package ai

import (
	"context"
	"fmt"
	"strings"

	"TaipeiCityDashboardBE/app/models"
	"TaipeiCityDashboardBE/logs"

	"github.com/tmc/langchaingo/llms"
)

const (
	ragRetrieveLimit  = 5
	ragExpandMaxToken = 80
	ragExpandPrompt   = `你是搜尋關鍵字生成器。根據用戶問題，生成 3-5 個適合搜尋城市儀表板資料的繁體中文關鍵字。每個關鍵字 2-6 個字，以空格分隔。只回傳關鍵字，不要任何說明或標點符號。`
)

// expandQuery calls LLM to generate search keywords from the user's message.
// Falls back to the original message if the call fails.
func expandQuery(ctx context.Context, userMessage string) string {
	messages := []llms.MessageContent{
		{
			Role:  llms.ChatMessageTypeSystem,
			Parts: []llms.ContentPart{llms.TextContent{Text: ragExpandPrompt}},
		},
		{
			Role:  llms.ChatMessageTypeHuman,
			Parts: []llms.ContentPart{llms.TextContent{Text: userMessage}},
		},
	}
	resp, err := twccModel.GenerateContent(ctx, messages,
		llms.WithMaxTokens(ragExpandMaxToken),
		llms.WithTemperature(0.0),
	)
	if err != nil || len(resp.Choices) == 0 || strings.TrimSpace(resp.Choices[0].Content) == "" {
		logs.FError("expandQuery failed, fallback to original: %v", err)
		return userMessage
	}
	return strings.TrimSpace(resp.Choices[0].Content)
}

// buildRAGContext formats the retrieved components into a string for system prompt injection.
func buildRAGContext(components []models.CityComponentScore) string {
	if len(components) == 0 {
		return ""
	}
	var sb strings.Builder
	sb.WriteString("\n\n以下是系統檢索到的候選儀表板元件，可能與用戶問題相關。\n請先判斷是否真的相關；只有明確相關時才引用。若與問題無關，請忽略，不要主動提及：\n")
	for i, c := range components {
		sb.WriteString(fmt.Sprintf("%d. [id=%d, index=%s] %s（城市：%s）\n", i+1, c.ID, c.Index, c.Name, c.City))
		if desc := firstNonEmpty(c.ShortDesc, c.LongDesc); desc != "" {
			sb.WriteString(fmt.Sprintf("   說明：%s\n", truncateForPrompt(normalizePromptText(desc), 180)))
		}
		if c.UseCase != "" {
			sb.WriteString(fmt.Sprintf("   用途：%s\n", truncateForPrompt(normalizePromptText(c.UseCase), 120)))
		}
	}
	return sb.String()
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}

func normalizePromptText(text string) string {
	return strings.Join(strings.Fields(text), " ")
}

func truncateForPrompt(text string, maxRunes int) string {
	runes := []rune(text)
	if len(runes) <= maxRunes {
		return text
	}
	return string(runes[:maxRunes]) + "..."
}
