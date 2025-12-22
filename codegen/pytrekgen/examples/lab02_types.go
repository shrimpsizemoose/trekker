//go:build ignore

type Event struct {
	EventType string    `json:"event_type"`
	UserID    string    `json:"user_id"`
	PostID    string    `json:"post_id"`
	Timestamp time.Time `json:"timestamp"`
	UnixTime  int64     `json:"unix_time"`
}

type EventStats struct {
	HourlyPostStats map[time.Time]map[string]PostStat
	HourlyUserStats map[time.Time]map[string]UserStat
}

type PostStat struct {
	LikesCount   int
	RepostsCount int
}

type UserStat struct {
	LikesGiven      int
	LikesReceived   int
	RepostsMade     int
	RepostsReceived int
	EngagementScore int
}
