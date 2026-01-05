package analytics

import (
	"bytes"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/shrimpsizemoose/trekker/logger"
)

type Tracker interface {
	Ping(eventType string, additionalData map[string]string)
	PingStart()
	PingFinish()
}

type Config struct {
	BaseURL       string
	SkipTLS       bool
	CommonData    map[string]string
	SecretHeaders map[string]string
}

type Analytics struct {
	config  Config
	verbose bool
}

func NewAnalytics(config Config) Tracker {
	_, verbose := os.LookupEnv("TREKKER_VERBOSE")
	return &Analytics{
		config:  config,
		verbose: verbose,
	}
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
		return fmt.Errorf("Что-то не так с аналитикой: я не смог тебя посчитать. Надо проверить сеть, а если не поможет -- напиши координатору пжлст и приложи скриншот. Спасибо 🐳.")
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusUnauthorized {
		if a.verbose {
			logger.Error.Println(resp)
		}
		return fmt.Errorf("Неправильное сочетание студента-токена, перепроверь что всё вводишь правильно. Ожидал статус 200 OK, получил - %s", resp.Status)
	}
	if resp.StatusCode != http.StatusOK {
		if a.verbose {
			logger.Error.Println(resp)
		}
		return fmt.Errorf("Ой. Я пытался тебя посчитать, но не смог убедиться что всё ок. Надо проверить сеть, а если не поможет -- напиши координатору пжлст и приложи скриншот. Я ожидал статус 200 OK, получил - %s", resp.Status)
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
}

func NewOfflineAnalytics(config Config) Tracker {
	return &OfflineAnalytics{
		commonData: config.CommonData,
	}
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

	logger.Info.Printf("(offline analytics) %s %s", eventType, pairs)
}

func (o *OfflineAnalytics) PingStart() {
	o.Ping("000_lab_start", nil)
}

func (o *OfflineAnalytics) PingFinish() {
	o.Ping("100_lab_finish", nil)
}
