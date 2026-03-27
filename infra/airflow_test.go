package infra

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func newTestServer(handler http.HandlerFunc) (*httptest.Server, AirflowConfig) {
	ts := httptest.NewServer(handler)
	addr := strings.TrimPrefix(ts.URL, "http://")
	cfg := AirflowConfig{
		Addr:     addr,
		User:     "admin",
		Password: "secret",
		Version:  2,
	}
	return ts, cfg
}

func TestAPIURL_NoScheme(t *testing.T) {
	c := NewAirflowClient(AirflowConfig{Addr: "localhost:8080", Version: 2})
	got := c.apiURL("/version")
	if got != "http://localhost:8080/api/v1/version" {
		t.Errorf("got %s", got)
	}
}

func TestAPIURL_WithScheme(t *testing.T) {
	c := NewAirflowClient(AirflowConfig{Addr: "http://localhost:8080", Version: 2})
	got := c.apiURL("/version")
	if got != "http://localhost:8080/api/v1/version" {
		t.Errorf("got %s", got)
	}
}

func TestAPIURL_TrailingSlash(t *testing.T) {
	c := NewAirflowClient(AirflowConfig{Addr: "localhost:8080/", Version: 2})
	got := c.apiURL("/version")
	if got != "http://localhost:8080/api/v1/version" {
		t.Errorf("got %s", got)
	}
}

func TestAPIURL_Version3(t *testing.T) {
	c := NewAirflowClient(AirflowConfig{Addr: "localhost:8080", Version: 3})
	got := c.apiURL("/version")
	if got != "http://localhost:8080/api/v2/version" {
		t.Errorf("got %s", got)
	}
}

func TestAPIURL_DefaultVersion(t *testing.T) {
	c := NewAirflowClient(AirflowConfig{Addr: "localhost:8080"})
	if c.config.Version != 2 {
		t.Errorf("default version should be 2, got %d", c.config.Version)
	}
	got := c.apiURL("/version")
	if got != "http://localhost:8080/api/v1/version" {
		t.Errorf("got %s", got)
	}
}

func TestGetVersion_Success(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/version") {
			t.Errorf("unexpected path: %s", r.URL.Path)
		}
		json.NewEncoder(w).Encode(versionResponse{Version: "2.8.0"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	v, err := c.GetVersion()
	if err != nil {
		t.Fatal(err)
	}
	if v != "2.8.0" {
		t.Errorf("got version %q", v)
	}
}

func TestGetVersion_Unauthorized(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(401)
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	_, err := c.GetVersion()
	if err == nil || !strings.Contains(err.Error(), "логин/пароль") {
		t.Errorf("expected auth error, got: %v", err)
	}
}

func TestDAGExists_Found(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagInfoResponse{DagID: "my_dag"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	if err := c.DAGExists("my_dag"); err != nil {
		t.Fatal(err)
	}
}

func TestDAGExists_NotFound(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	err := c.DAGExists("missing_dag")
	if err == nil || !strings.Contains(err.Error(), "не найден") {
		t.Errorf("expected not found error, got: %v", err)
	}
}

func TestDAGIsPaused_True(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagInfoResponse{DagID: "my_dag", IsPaused: true})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	paused, err := c.DAGIsPaused("my_dag")
	if err != nil {
		t.Fatal(err)
	}
	if !paused {
		t.Error("expected paused=true")
	}
}

func TestDAGIsPaused_False(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagInfoResponse{DagID: "my_dag", IsPaused: false})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	paused, err := c.DAGIsPaused("my_dag")
	if err != nil {
		t.Fatal(err)
	}
	if paused {
		t.Error("expected paused=false")
	}
}

func TestTriggerDAG_Success(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" {
			t.Errorf("expected POST, got %s", r.Method)
		}
		var payload map[string]any
		json.NewDecoder(r.Body).Decode(&payload)
		json.NewEncoder(w).Encode(dagRunResponse{DagRunID: "run_123", State: "queued", DagID: "my_dag"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	runID, err := c.TriggerDAG("my_dag", map[string]any{"hour": 12})
	if err != nil {
		t.Fatal(err)
	}
	if runID != "run_123" {
		t.Errorf("got run_id %q", runID)
	}
}

func TestTriggerDAG_EmptyConf(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagRunResponse{DagRunID: "run_456"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	runID, err := c.TriggerDAG("my_dag", nil)
	if err != nil {
		t.Fatal(err)
	}
	if runID != "run_456" {
		t.Errorf("got run_id %q", runID)
	}
}

func TestWaitForRun_ImmediateSuccess(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagRunResponse{DagRunID: "run_1", State: "success"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	err := c.WaitForRun("my_dag", "run_1", 5*time.Second, 100*time.Millisecond, nil)
	if err != nil {
		t.Fatal(err)
	}
}

func TestWaitForRun_EventualSuccess(t *testing.T) {
	var calls atomic.Int32
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		n := calls.Add(1)
		state := "running"
		if n >= 3 {
			state = "success"
		}
		json.NewEncoder(w).Encode(dagRunResponse{DagRunID: "run_2", State: state})
	})
	defer ts.Close()

	pollCount := 0
	c := NewAirflowClient(cfg)
	err := c.WaitForRun("my_dag", "run_2", 5*time.Second, 50*time.Millisecond, func(elapsed time.Duration) {
		pollCount++
	})
	if err != nil {
		t.Fatal(err)
	}
	if pollCount < 2 {
		t.Errorf("expected at least 2 polls, got %d", pollCount)
	}
}

func TestWaitForRun_Failure(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagRunResponse{DagRunID: "run_3", State: "failed"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	err := c.WaitForRun("my_dag", "run_3", 5*time.Second, 100*time.Millisecond, nil)
	if err == nil || !strings.Contains(err.Error(), "завершился с ошибкой") {
		t.Errorf("expected failure error, got: %v", err)
	}
}

func TestWaitForRun_Timeout(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(dagRunResponse{DagRunID: "run_4", State: "running"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	err := c.WaitForRun("my_dag", "run_4", 200*time.Millisecond, 50*time.Millisecond, nil)
	if err == nil || !strings.Contains(err.Error(), "не завершился за") {
		t.Errorf("expected timeout error, got: %v", err)
	}
}

func TestCheckDefaultPassword_DefaultWorks(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		user, pass, _ := r.BasicAuth()
		if user == "airflow" && pass == "airflow" {
			w.WriteHeader(200)
			return
		}
		w.WriteHeader(401)
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	err := c.CheckDefaultPassword()
	if err == nil || !strings.Contains(err.Error(), "airflow:airflow") {
		t.Errorf("expected default password error, got: %v", err)
	}
}

func TestCheckDefaultPassword_DefaultDisabled(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		user, pass, _ := r.BasicAuth()
		if user == "airflow" && pass == "airflow" {
			w.WriteHeader(401)
			return
		}
		w.WriteHeader(200)
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	err := c.CheckDefaultPassword()
	if err != nil {
		t.Errorf("expected nil, got: %v", err)
	}
}

func TestVersion3_ReturnsError(t *testing.T) {
	c := NewAirflowClient(AirflowConfig{
		Addr:    "localhost:8080",
		Version: 3,
	})
	_, err := c.GetVersion()
	if err == nil || !strings.Contains(err.Error(), "не поддерживается") {
		t.Errorf("expected v3 not supported error, got: %v", err)
	}
}

func TestBasicAuth_Sent(t *testing.T) {
	ts, cfg := newTestServer(func(w http.ResponseWriter, r *http.Request) {
		user, pass, ok := r.BasicAuth()
		if !ok || user != "admin" || pass != "secret" {
			t.Errorf("bad auth: user=%q pass=%q ok=%v", user, pass, ok)
		}
		json.NewEncoder(w).Encode(versionResponse{Version: "2.8.0"})
	})
	defer ts.Close()

	c := NewAirflowClient(cfg)
	c.GetVersion()
}
