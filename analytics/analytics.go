package analytics

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/shrimpsizemoose/trekker/logger"
	"github.com/shrimpsizemoose/trekker/utils"
)

type Tracker interface {
	Ping(eventType string, additionalData map[string]string)
	PingStart()
	PingFinish()
	CheckConnection() error
	RunID() string
}

type Config struct {
	BaseURL       string
	HealthURL     string
	SkipTLS       bool
	Version       string
	SHA           string
	CommonData    map[string]string
	SecretHeaders map[string]string
}

type Analytics struct {
	config  Config
	verbose bool
	runID   string
}

func generateRunID() string {
	id, err := utils.NewNanoIDSize(10)
	if err != nil {
		return fmt.Sprintf("trkkr-%d", time.Now().UnixNano())
	}
	return "trkkr-" + id
}

func NewAnalytics(config Config) Tracker {
	_, verbose := os.LookupEnv("TREKKER_VERBOSE")
	return &Analytics{
		config:  config,
		verbose: verbose,
		runID:   generateRunID(),
	}
}

func (a *Analytics) RunID() string {
	return a.runID
}

func (a *Analytics) sendEvent(eventType string, additionalData map[string]string) error {
	data := make(map[string]string)
	for k, v := range a.config.CommonData {
		data[k] = v
	}
	for k, v := range additionalData {
		data[k] = v
	}
	data["event_type"] = eventType
	data["local_datetime"] = time.Now().String()

	data["_run_id"] = a.runID
	if a.config.Version != "" {
		data["_version"] = a.config.Version
	}
	if a.config.SHA != "" {
		data["_sha"] = a.config.SHA
	}

	jsonData, err := json.Marshal(data)
	if err != nil {
		return fmt.Errorf("error marshaling JSON: %w", err)
	}

	req, err := http.NewRequest("POST", a.config.BaseURL, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("error creating request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	for k, v := range a.config.SecretHeaders {
		req.Header.Set(k, v)
	}

	transport := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: a.config.SkipTLS},
	}
	client := &http.Client{Timeout: 3 * time.Second, Transport: transport}
	resp, err := client.Do(req)
	if err != nil {
		if a.verbose {
			logger.Error.Println(err)
		}
		return fmt.Errorf("Что-то не так с аналитикой: я не смог тебя посчитать.\n\n1. Сначала попробуй запустить чекер с флагом --ping чтобы проверить соединение с сервером аналитики\n2. Если --ping не проходит, проверь что у тебя есть доступ в интернет и что VPN/firewall не блокирует соединение\n3. Если --ping прошёл, а чекер всё равно падает -- напиши координатору и приложи скриншот")
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)

	var respBody string
	var serverError string
	var parsed map[string]interface{}
	if err := json.Unmarshal(body, &parsed); err == nil {
		if errMsg, ok := parsed["error"]; ok {
			serverError = fmt.Sprintf("%v", errMsg)
		}
		if a.verbose {
			var parts []string
			for k, v := range parsed {
				parts = append(parts, fmt.Sprintf("%s: %v", k, v))
			}
			respBody = strings.Join(parts, ", ")
		}
	} else {
		respBody = string(body)
	}

	if resp.StatusCode == http.StatusUnauthorized {
		if a.verbose {
			logger.Error.Printf("Ответ сервера:\n  %s", respBody)
		}
		return fmt.Errorf("Неправильное сочетание студента-токена, перепроверь что всё вводишь правильно. Ожидал статус 200 OK, получил - %s", resp.Status)
	}
	if resp.StatusCode == http.StatusLocked {
		if serverError != "" {
			return fmt.Errorf("🔒 %s", serverError)
		}
		return fmt.Errorf("🔒 Эта версия чекера устарела. Скачай свежий образ и попробуй снова.")
	}
	if resp.StatusCode != http.StatusOK {
		if a.verbose {
			logger.Error.Printf("Ответ сервера:\n  %s", respBody)
		}
		return fmt.Errorf("Ой. Я пытался тебя посчитать, но не смог убедиться что всё ок (получил статус %s).\n\n1. Сначала попробуй запустить чекер с флагом --ping чтобы проверить соединение с сервером аналитики\n2. Если --ping не проходит, проверь что у тебя есть доступ в интернет и что VPN/firewall не блокирует соединение\n3. Если --ping прошёл, а чекер всё равно падает -- напиши координатору и приложи скриншот", resp.Status)
	}

	return nil
}

func (a *Analytics) Ping(eventType string, additionalData map[string]string) {
	err := a.sendEvent(eventType, additionalData)
	if a.verbose {
		logger.Warn.Printf("Аналитика: event %s", eventType)
	}
	if err != nil {
		if !a.verbose {
			logger.Warn.Println("Чтобы получить чуть больше информации об ошибке, запусти меня ещё раз с TREKKER_VERBOSE=da")
		}
		logger.Error.Fatalf("Failed to send analytics: %v", err)
	}
}

func (a *Analytics) CheckConnection() error {
	url := a.config.HealthURL
	if url == "" {
		url = a.config.BaseURL
	}
	if url == "" {
		return fmt.Errorf("адрес аналитики не задан (переменная окружения пустая или не указана)")
	}

	transport := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: a.config.SkipTLS},
	}
	client := &http.Client{Timeout: 5 * time.Second, Transport: transport}

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return fmt.Errorf("не удалось создать запрос к %s: %w", url, err)
	}

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("не удалось подключиться к %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		logger.Error.Printf("Сервер аналитики ответил с ошибкой\n  %s (статус: %s)", url, resp.Status)
		return fmt.Errorf("--ping не прошёл")
	}

	logger.Victory.Printf("Соединение с аналитикой установлено\n  %s (статус: %s)", url, resp.Status)
	return nil
}

func (a *Analytics) PingStart() {
	if a.verbose {
		logger.Warn.Println("Аналитика стартует")
	}
	a.Ping("000_lab_start", nil)
}

func (a *Analytics) PingFinish() {
	if a.verbose {
		logger.Warn.Println("Аналитика финиширует")
	}
	a.Ping("100_lab_finish", nil)
}

// OfflineAnalytics prints events to console instead of sending HTTP requests.
// Use for testing and development.
type OfflineAnalytics struct {
	commonData map[string]string
	runID      string
}

func NewOfflineAnalytics(config Config) Tracker {
	return &OfflineAnalytics{
		commonData: config.CommonData,
		runID:      generateRunID(),
	}
}

func (o *OfflineAnalytics) RunID() string {
	return o.runID
}

func (o *OfflineAnalytics) Ping(eventType string, additionalData map[string]string) {
	data := make(map[string]string)
	for k, v := range o.commonData {
		data[k] = v
	}
	for k, v := range additionalData {
		data[k] = v
	}

	var pairs []string
	for k, v := range data {
		pairs = append(pairs, fmt.Sprintf("%s=%s", k, v))
	}

	logger.Info.Printf("(offline analytics) [%s] %s %s", o.runID, eventType, pairs)
}

func (o *OfflineAnalytics) CheckConnection() error {
	logger.Victory.Println("(offline analytics) --ping: соединение не требуется в offline режиме")
	return nil
}

func (o *OfflineAnalytics) PingStart() {
	o.Ping("000_lab_start", nil)
}

func (o *OfflineAnalytics) PingFinish() {
	o.Ping("100_lab_finish", nil)
}
