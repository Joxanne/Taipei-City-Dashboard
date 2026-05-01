// Package models stores the models for the postgreSQL databases.
package models

import "strings"

// ComponentBM25Result is the PostgreSQL full-text search result for components.
type ComponentBM25Result struct {
	ID    int64   `json:"id" gorm:"column:id"`
	Index string  `json:"index" gorm:"column:index"`
	Name  string  `json:"name" gorm:"column:name"`
	City  string  `json:"city" gorm:"column:city"`
	Rank  float64 `json:"rank" gorm:"column:rank"`
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

	var results []ComponentBM25Result
	sql := `
		SELECT c.id, c.index, c.name, qc.city,
			ts_rank(
				to_tsvector(
					'simple',
					coalesce(c.name, '') || ' ' ||
					coalesce(qc.short_desc, '') || ' ' ||
					coalesce(qc.long_desc, '') || ' ' ||
					coalesce(qc.use_case, '')
				),
				plainto_tsquery('simple', ?)
			) AS rank
		FROM components c
		INNER JOIN query_charts qc ON c.index = qc.index
		WHERE to_tsvector(
			'simple',
			coalesce(c.name, '') || ' ' ||
			coalesce(qc.short_desc, '') || ' ' ||
			coalesce(qc.long_desc, '') || ' ' ||
			coalesce(qc.use_case, '')
		) @@ plainto_tsquery('simple', ?)
		ORDER BY rank DESC
		LIMIT ?
	`
	err := DBManager.Raw(sql, query, query, limit).Scan(&results).Error
	return results, err
}
