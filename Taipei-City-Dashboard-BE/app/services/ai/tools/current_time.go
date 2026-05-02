package tools

import (
	"context"
	"time"
)

func init() {
	MustRegister(
		NewTool(
			"get_current_time",
			"取得目前臺北時區的日期與時間。當用戶詢問現在時間、今天日期或需要以目前時間作為回答依據時使用。",
			GetCurrentTime,
		).NoParams(),
	)
}

// GetCurrentTime returns the current Taipei time.
func GetCurrentTime(ctx context.Context, args string) (string, error) {
	loc, err := time.LoadLocation("Asia/Taipei")
	if err != nil {
		// Fallback to UTC if timezone data is missing.
		return time.Now().Format(time.RFC3339), nil
	}
	return time.Now().In(loc).Format("2006-01-02 15:04:05"), nil
}
