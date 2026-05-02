package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"sort"
	"strings"
	"sync"

	"TaipeiCityDashboardBE/app/models"
)

const (
	defaultComponentSearchLimit = 3
	maxComponentSearchLimit     = 15
	vectorScoreThreshold        = 0.6
	rrfRankConstant             = 60.0
)

func init() {
	MustRegister(
		NewTool(
			"search_components_hybrid",
			"搜尋臺北城市儀表板中與用戶問題相關的資料視覺化元件。當用戶想了解特定城市議題或數據時使用此工具。",
			SearchComponentsHybrid,
		).
			RequiredString("query", "從用戶輸入中萃取的搜尋關鍵字，用繁體中文描述主題。").
			OptionalInteger("limit", "回傳的元件數量，預設 3，最多 10。").
			Build(),
	)
}

type searchComponentsArgs struct {
	Query string `json:"query"`
	Limit int    `json:"limit"`
}

type componentResult struct {
	ID    int64   `json:"id"`
	Index string  `json:"index"`
	Name  string  `json:"name"`
	City  string  `json:"city"`
	Score float64 `json:"score"`
}

// SearchComponentsHybrid searches dashboard components with BM25 and vector search, then merges them with RRF.
func SearchComponentsHybrid(ctx context.Context, args string) (string, error) {
	var params searchComponentsArgs
	if err := parseArgs(args, &params); err != nil {
		return "", fmt.Errorf("invalid arguments: %v", err)
	}

	query := strings.TrimSpace(params.Query)
	if query == "" {
		return "", fmt.Errorf("query is required")
	}

	limit := normalizeComponentSearchLimit(params.Limit)
	searchLimit := limit * 2

	if err := ctx.Err(); err != nil {
		return "", err
	}

	var textResults []models.ComponentBM25Result
	var vectorResults []models.CityComponentScore
	var textErr error
	var vectorErr error

	var wg sync.WaitGroup
	wg.Add(2)
	go func() {
		defer wg.Done()
		textResults, textErr = models.SearchComponentsByText(query, searchLimit)
	}()
	go func() {
		defer wg.Done()
		vectorResults, vectorErr = models.GetComponentByQueryVector(query, searchLimit, vectorScoreThreshold)
	}()
	wg.Wait()

	if textErr != nil && vectorErr != nil {
		return "", fmt.Errorf("text search failed: %v; vector search failed: %v", textErr, vectorErr)
	}
	if err := ctx.Err(); err != nil {
		return "", err
	}

	searchLists := make([][]componentResult, 0, 2)
	if textErr == nil {
		searchLists = append(searchLists, convertTextResults(textResults))
	}
	if vectorErr == nil {
		searchLists = append(searchLists, convertVectorResults(vectorResults))
	}

	results := reciprocalRankFusion(searchLists...)
	if len(results) > limit {
		results = results[:limit]
	}

	output, err := json.Marshal(results)
	if err != nil {
		return "", fmt.Errorf("failed to marshal component results: %v", err)
	}
	return string(output), nil
}

func normalizeComponentSearchLimit(limit int) int {
	if limit <= 0 {
		return defaultComponentSearchLimit
	}
	if limit > maxComponentSearchLimit {
		return maxComponentSearchLimit
	}
	return limit
}

func convertTextResults(results []models.ComponentBM25Result) []componentResult {
	components := make([]componentResult, 0, len(results))
	for _, result := range results {
		components = append(components, componentResult{
			ID:    result.ID,
			Index: result.Index,
			Name:  result.Name,
			City:  result.City,
			Score: result.Rank,
		})
	}
	return components
}

func convertVectorResults(results []models.CityComponentScore) []componentResult {
	components := make([]componentResult, 0, len(results))
	for _, result := range results {
		components = append(components, componentResult{
			ID:    result.ID,
			Index: result.Index,
			Name:  result.Name,
			City:  result.City,
			Score: result.Score,
		})
	}
	return components
}

func reciprocalRankFusion(lists ...[]componentResult) []componentResult {
	scores := make(map[string]float64)
	components := make(map[string]componentResult)
	sourceScores := make(map[string]float64)

	for _, list := range lists {
		for rank, component := range list {
			if component.Index == "" {
				continue
			}
			scores[component.Index] += 1.0 / (rrfRankConstant + float64(rank+1))
			if _, ok := components[component.Index]; !ok || component.Score > sourceScores[component.Index] {
				components[component.Index] = component
				sourceScores[component.Index] = component.Score
			}
		}
	}

	results := make([]componentResult, 0, len(components))
	for index, component := range components {
		component.Score = scores[index]
		results = append(results, component)
	}

	sort.SliceStable(results, func(i, j int) bool {
		if results[i].Score == results[j].Score {
			return results[i].Index < results[j].Index
		}
		return results[i].Score > results[j].Score
	})

	return results
}
