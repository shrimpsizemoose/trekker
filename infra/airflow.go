package infra

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

type AirflowConfig struct {
	Addr     string // host:port, no scheme
	User     string
	Password string
	Version  int // 2 or 3, default 2
}

type AirflowClient struct {
	config AirflowConfig
	client *http.Client
}

type dagRunResponse struct {
	DagRunID string `json:"dag_run_id"`
	State    string `json:"state"`
	DagID    string `json:"dag_id"`
}

type dagInfoResponse struct {
	DagID    string `json:"dag_id"`
	IsPaused bool   `json:"is_paused"`
}

type versionResponse struct {
	Version string `json:"version"`
}

func NewAirflowClient(config AirflowConfig) *AirflowClient {
	if config.Version == 0 {
		config.Version = 2
	}
	return &AirflowClient{
		config: config,
		client: &http.Client{Timeout: 10 * time.Second},
	}
}

// apiURL constructs the full API URL for the given path.
func (c *AirflowClient) apiURL(path string) string {
	addr := strings.TrimRight(c.config.Addr, "/")

	var base string
	if strings.HasPrefix(addr, "http://") || strings.HasPrefix(addr, "https://") {
		base = addr
	} else {
		base = "http://" + addr
	}

	var apiPrefix string
	switch c.config.Version {
	case 3:
		apiPrefix = "/api/v2"
	default:
		apiPrefix = "/api/v1"
	}

	return base + apiPrefix + path
}

// doRequest executes an HTTP request with auth headers.
func (c *AirflowClient) doRequest(method, path string, body io.Reader) (*http.Response, error) {
	if c.config.Version == 3 {
		// TODO: implement JWT auth for Airflow 3
		return nil, fmt.Errorf("Airflow 3 пока не поддерживается (JWT-авторизация не реализована)")
	}

	url := c.apiURL(path)
	req, err := http.NewRequest(method, url, body)
	if err != nil {
		return nil, err
	}

	req.SetBasicAuth(c.config.User, c.config.Password)
	req.Header.Set("Content-Type", "application/json")

	return c.client.Do(req)
}

// doRequestWithCreds executes an HTTP request with explicit credentials.
func (c *AirflowClient) doRequestWithCreds(method, path, user, password string) (*http.Response, error) {
	url := c.apiURL(path)
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return nil, err
	}

	req.SetBasicAuth(user, password)
	req.Header.Set("Content-Type", "application/json")

	return c.client.Do(req)
}

// GetVersion returns the Airflow version string.
func (c *AirflowClient) GetVersion() (string, error) {
	resp, err := c.doRequest("GET", "/version", nil)
	if err != nil {
		return "", fmt.Errorf("Не удалось подключиться к Airflow по адресу %s: %v", c.config.Addr, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == 401 {
		return "", fmt.Errorf("Неправильный логин/пароль для Airflow")
	}
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("Airflow вернул статус %d при запросе версии", resp.StatusCode)
	}

	var v versionResponse
	if err := json.NewDecoder(resp.Body).Decode(&v); err != nil {
		return "", fmt.Errorf("не удалось прочитать ответ Airflow: %v", err)
	}

	return v.Version, nil
}

// DAGExists checks if a DAG exists via GET /dags/{dagID}.
func (c *AirflowClient) DAGExists(dagID string) error {
	resp, err := c.doRequest("GET", "/dags/"+dagID, nil)
	if err != nil {
		return fmt.Errorf("Не удалось подключиться к Airflow по адресу %s: %v", c.config.Addr, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == 401 {
		return fmt.Errorf("Неправильный логин/пароль для Airflow")
	}
	if resp.StatusCode == 404 {
		return fmt.Errorf("DAG %s не найден в Airflow", dagID)
	}
	if resp.StatusCode != 200 {
		return fmt.Errorf("Airflow вернул статус %d при проверке DAG %s", resp.StatusCode, dagID)
	}

	return nil
}

// DAGIsPaused returns true if the DAG is paused.
func (c *AirflowClient) DAGIsPaused(dagID string) (bool, error) {
	resp, err := c.doRequest("GET", "/dags/"+dagID, nil)
	if err != nil {
		return false, fmt.Errorf("Не удалось подключиться к Airflow по адресу %s: %v", c.config.Addr, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == 401 {
		return false, fmt.Errorf("Неправильный логин/пароль для Airflow")
	}
	if resp.StatusCode == 404 {
		return false, fmt.Errorf("DAG %s не найден в Airflow", dagID)
	}
	if resp.StatusCode != 200 {
		return false, fmt.Errorf("Airflow вернул статус %d при проверке DAG %s", resp.StatusCode, dagID)
	}

	var info dagInfoResponse
	if err := json.NewDecoder(resp.Body).Decode(&info); err != nil {
		return false, fmt.Errorf("не удалось прочитать ответ Airflow: %v", err)
	}

	return info.IsPaused, nil
}

// TriggerDAG triggers a DAG run with optional conf.
// Returns the dag_run_id from the response.
func (c *AirflowClient) TriggerDAG(dagID string, conf map[string]any) (string, error) {
	payload := map[string]any{}
	if conf != nil {
		payload["conf"] = conf
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("не удалось сериализовать conf: %v", err)
	}

	resp, err := c.doRequest("POST", "/dags/"+dagID+"/dagRuns", strings.NewReader(string(body)))
	if err != nil {
		return "", fmt.Errorf("Не удалось подключиться к Airflow по адресу %s: %v", c.config.Addr, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == 401 {
		return "", fmt.Errorf("Неправильный логин/пароль для Airflow")
	}
	if resp.StatusCode == 404 {
		return "", fmt.Errorf("DAG %s не найден в Airflow", dagID)
	}
	if resp.StatusCode != 200 {
		return "", fmt.Errorf("Airflow вернул статус %d при триггере DAG %s", resp.StatusCode, dagID)
	}

	var run dagRunResponse
	if err := json.NewDecoder(resp.Body).Decode(&run); err != nil {
		return "", fmt.Errorf("не удалось прочитать ответ Airflow: %v", err)
	}

	return run.DagRunID, nil
}

// WaitForRun polls a DAG run until it reaches a terminal state or timeout.
func (c *AirflowClient) WaitForRun(dagID, runID string, timeout, interval time.Duration, onPoll func(elapsed time.Duration)) error {
	start := time.Now()

	for {
		elapsed := time.Since(start)
		if elapsed >= timeout {
			return fmt.Errorf("DAG run %s не завершился за %s", runID, timeout)
		}

		resp, err := c.doRequest("GET", "/dags/"+dagID+"/dagRuns/"+runID, nil)
		if err != nil {
			return fmt.Errorf("Не удалось подключиться к Airflow по адресу %s: %v", c.config.Addr, err)
		}

		var run dagRunResponse
		err = json.NewDecoder(resp.Body).Decode(&run)
		resp.Body.Close()
		if err != nil {
			return fmt.Errorf("не удалось прочитать ответ Airflow: %v", err)
		}

		switch run.State {
		case "success":
			return nil
		case "failed":
			return fmt.Errorf("DAG run %s завершился с ошибкой (state: failed)", runID)
		}

		if onPoll != nil {
			onPoll(time.Since(start))
		}

		time.Sleep(interval)
	}
}

// CheckDefaultPassword attempts to authenticate with airflow:airflow.
// Returns nil if the default password does NOT work (good).
// Returns error if it does work (bad — student didn't change it).
func (c *AirflowClient) CheckDefaultPassword() error {
	resp, err := c.doRequestWithCreds("GET", "/dags", "airflow", "airflow")
	if err != nil {
		// Connection error — can't check, but default password isn't the issue
		return nil
	}
	defer resp.Body.Close()

	if resp.StatusCode == 200 {
		return fmt.Errorf("дефолтные креды airflow:airflow всё ещё работают, надо бы поменять пароль администратора")
	}

	return nil
}
