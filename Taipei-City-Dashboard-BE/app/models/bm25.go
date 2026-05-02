// Package models stores the models for the postgreSQL databases.
package models

import (
	"fmt"
	"strings"
)

// ComponentBM25Result is the PostgreSQL full-text search result for components.
type ComponentBM25Result struct {
	ID        int64   `json:"id" gorm:"column:id"`
	Index     string  `json:"index" gorm:"column:index"`
	Name      string  `json:"name" gorm:"column:name"`
	City      string  `json:"city" gorm:"column:city"`
	ShortDesc string  `json:"short_desc" gorm:"column:short_desc"`
	LongDesc  string  `json:"long_desc" gorm:"column:long_desc"`
	UseCase   string  `json:"use_case" gorm:"column:use_case"`
	Rank      float64 `json:"rank" gorm:"column:rank"`
}

// SearchComponentsByText searches components with PostgreSQL full-text search.
func SearchComponentsByText(query string, limit int) ([]ComponentBM25Result, error) {
	query = strings.TrimSpace(query)
	if query == "" {
		return []ComponentBM25Result{}, nil
	}
	if limit <= 0 {
		limit = 10
	}

	terms := uniqueSearchTerms(query)
	if len(terms) == 0 {
		return []ComponentBM25Result{}, nil
	}

	vectorExpr := `to_tsvector(
		'simple',
		coalesce(c.name, '') || ' ' ||
		coalesce(qc.short_desc, '') || ' ' ||
		coalesce(qc.long_desc, '') || ' ' ||
		coalesce(qc.use_case, '')
	)`
	rankParts := make([]string, 0, len(terms))
	whereParts := make([]string, 0, len(terms))
	args := make([]interface{}, 0, len(terms)*2+1)
	for _, term := range terms {
		rankParts = append(rankParts, fmt.Sprintf("ts_rank(%s, plainto_tsquery('simple', ?))", vectorExpr))
		args = append(args, term)
		whereParts = append(whereParts, fmt.Sprintf("%s @@ plainto_tsquery('simple', ?)", vectorExpr))
	}
	for _, term := range terms {
		args = append(args, term)
	}
	args = append(args, limit)

	sql := `
		SELECT c.id, c.index, c.name, qc.city, qc.short_desc, qc.long_desc, qc.use_case,
			(` + strings.Join(rankParts, " + ") + `) AS rank
		FROM components c
		INNER JOIN query_charts qc ON c.index = qc.index
		WHERE ` + strings.Join(whereParts, " OR ") + `
		ORDER BY rank DESC
		LIMIT ?
	`
	var results []ComponentBM25Result
	err := DBManager.Raw(sql, args...).Scan(&results).Error
	return results, err
}

func uniqueSearchTerms(query string) []string {
	fields := strings.Fields(query)
	if len(fields) == 0 {
		fields = []string{query}
	}

	seen := make(map[string]struct{}, len(fields))
	terms := make([]string, 0, len(fields))
	for _, field := range fields {
		term := strings.TrimSpace(field)
		if term == "" {
			continue
		}
		if _, ok := seen[term]; ok {
			continue
		}
		seen[term] = struct{}{}
		terms = append(terms, term)
	}
	return terms
}
