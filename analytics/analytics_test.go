package analytics

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSendEventResponseStatus(t *testing.T) {
	tests := []struct {
		name    string
		status  int
		body    string
		wantErr string
	}{
		{name: "OK empty", status: http.StatusOK},
		{name: "OK JSON", status: http.StatusOK, body: `{"ok":true}`},
		{name: "Created empty", status: http.StatusCreated},
		{name: "Created JSON", status: http.StatusCreated, body: `{"ok":true}`},
		{name: "Accepted", status: http.StatusAccepted, wantErr: "получил статус 202 Accepted"},
		{name: "No Content", status: http.StatusNoContent, wantErr: "получил статус 204 No Content"},
		{name: "Bad Request", status: http.StatusBadRequest, wantErr: "получил статус 400 Bad Request"},
		{
			name:    "Unauthorized",
			status:  http.StatusUnauthorized,
			wantErr: "Неправильное сочетание студента-токена, перепроверь что всё вводишь правильно. Ожидал статус 200 OK, получил - 401 Unauthorized",
		},
		{name: "Locked explanation", status: http.StatusLocked, body: `{"error":"checker outdated"}`, wantErr: "🔒 checker outdated"},
		{name: "Locked fallback", status: http.StatusLocked, wantErr: "🔒 Эта версия чекера устарела. Скачай свежий образ и попробуй снова."},
		{name: "Internal Server Error", status: http.StatusInternalServerError, wantErr: "получил статус 500 Internal Server Error"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != http.MethodPost {
					t.Errorf("request method = %s, want POST", r.Method)
				}
				w.WriteHeader(tt.status)
				_, _ = io.WriteString(w, tt.body)
			}))
			defer server.Close()

			a := &Analytics{config: Config{BaseURL: server.URL}, runID: "test-run"}
			err := a.sendEvent("test_event", nil)
			if tt.wantErr == "" {
				if err != nil {
					t.Fatalf("sendEvent() = %v, want nil", err)
				}
				return
			}
			if err == nil || !strings.Contains(err.Error(), tt.wantErr) {
				t.Fatalf("sendEvent() = %v, want error containing %q", err, tt.wantErr)
			}
		})
	}
}
