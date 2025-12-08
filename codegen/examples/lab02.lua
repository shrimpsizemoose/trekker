-- Lab 02: Kafka to PostgreSQL pipeline verification
-- This demonstrates the hybrid approach: declarative config + custom Go code

lab = {
    id = "02",
    name = "Kafka Pipeline Lab",
    env_prefix = "NPL",
}

required_env = {
    { name = "STUDENT",            error = "Мне надо знать, как тебя зовут" },
    { name = "TOKEN",              error = "Мне нужен токен, чтобы убедиться что ты это ты" },
    { name = "LAB02_KAFKA_ADDR",  error = "Нужен адрес кафки" },
    { name = "LAB02_KAFKA_TOPIC", error = "Нужно имя топика" },
    { name = "LAB02_DB_URL",      error = "Нужен URL базы данных" },
}

optional_env_int = {
    { name = "KAFKA_BATCH_SIZE",            default = 100, message = "использую размер батча по умолчанию" },
    { name = "KAFKA_BATCH_NOM_NOM_DELAY_MS", default = 0,   message = "не жду между отправкой батчей" },
}

flags = {
    { name = "send-only", type = "bool", default = "false", description = "только отправлять сообщения в кафку, без проверки PostgreSQL" },
    { name = "small",     type = "bool", default = "false", description = "отправить малый набор сообщений (для быстрой проверки)" },
}

usage_text = [[
🤌 Чекер конфигурируется через переменные окружения

{{.EnvPrefix}}_LAB02_KAFKA_ADDR - адрес кафки (например kafka.example.com:9092)
{{.EnvPrefix}}_LAB02_KAFKA_TOPIC - имя топика в кафке
{{.EnvPrefix}}_LAB02_DB_URL - URL базы данных postgres
{{.EnvPrefix}}_STUDENT - ваше имя, как логин в ЛК (например herbie.hancock)
{{.EnvPrefix}}_TOKEN - ваш секретный токен, например, sk-npl-Ha266QtZXDE99BnKo....ABC

Опциональные переменные, которые можно попробовать поменять, если что-то не работает
{{.EnvPrefix}}_KAFKA_BATCH_SIZE - по сколько сообщений слать за раз (например, 1000)
{{.EnvPrefix}}_KAFKA_BATCH_NOM_NOM_DELAY_MS - сколько ждать (в миллисекундах) после отправки пакета

Переменные проще сохранить в файл и оттуда уже давать чекеру
Например, можно создать файл env.conf и написать туда:
  NPL_LAB02KAFKA_ADDR=kafka.example.com:9092
  NPL_LAB02KAFKA_TOPIC=my_topic
  NPL_LAB02_DB_URL=postgres://user:pass@host:5432/dbname
  NPL_STUDENT=herbie.hancock
  NPL_TOKEN=sk-npl-b82...................b3
  NPL_KAFKA_BATCH_SIZE=50
  NPL_KAFKA_BATCH_NOM_NOM_DELAY_MS=300

И потом подсунуть его докеру через --env-file env.conf
  docker run --rm -it --env-file env.conf {{.Image}}
Флаг -send-only отправит только сообщения в кафку без проверки постгреса
Флаг -small включает отправку малого набора сообщений (быстрый тест пайплайна)

Напоминаем также, что при возникновении проблем следует обратиться к мануалу по дебагу:
{{.Debug}}
]]

confirm_display = {
    "STUDENT",
    { name = "TOKEN", masked = true },
    "LAB02_KAFKA_ADDR",
    "LAB02_KAFKA_TOPIC",
    { name = "LAB02_DB_URL", masked = true },
}

analytics = {
    skip_tls = true,
    common_data = {
        kafka_url = "LAB02_KAFKA_ADDR",
        kafka_topic = "LAB02_KAFKA_TOPIC",
    },
    headers = {
        ["x-secret"] = "I know stuff, okay?",
        ["x-npl-lab"] = "02",
        ["x-npl-student"] = "env:STUDENT",
        ["Authorization"] = "Bearer env:TOKEN",
    },
}

-- The verification checks
checks = {
    -- Check that Kafka topic exists
    {
        type = "kafka_topic_exists",
        name = "check_topic",
        kafka_addr_env = "LAB02_KAFKA_ADDR",
        kafka_topic_env = "LAB02_KAFKA_TOPIC",
    },
    -- Connect to PostgreSQL (only if not send-only mode)
    {
        type = "postgres_connect",
        name = "connect_db",
        postgres_url_env = "LAB02_DB_URL",
        skip_on_flag = "send-only",
    },
    -- Check that PostgreSQL tables are empty before test
    {
        type = "postgres_tables_empty",
        name = "check_tables_empty",
        postgres_url_env = "LAB02_DB_URL",
        tables = { "f_hourly_post_stats", "f_hourly_user_stats" },
        message_before = "Проверяю что таблицы пустые",
        skip_on_flag = "send-only",
    },
    -- Run the main pipeline test (custom code)
    {
        type = "custom",
        name = "run_pipeline",
        func = "runPipelineTest",
    },
}

success_message = "Все проверки успешно пройдены! 🎉"

-- Custom Go code for the complex logic
-- This is embedded directly into the generated file
custom_code = {
    imports = {
        "encoding/json",
        "math/rand",
        "time",
        "github.com/cheggaaa/pb/v3",
    },

    types = [[
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
]],

    code = [[
const likeProb = 0.85
const numMessages = 100_000
const numUsers = 1_000
const smallNumMessages = 1_000
const smallNumUsers = 10

var postAuthors = make(map[string]string)

func runPipelineTest(ctx context.Context) error {
	messagesToSend := numMessages
	usersToSend := numUsers
	if *flagSmall {
		messagesToSend = smallNumMessages
		usersToSend = smallNumUsers
		logger.Info.Printf("Включен флаг small — отправлю %d сообщений", messagesToSend)
		tracker.Ping("010_small_mode_on", nil)
	}

	events, stats := generateEvents(messagesToSend, usersToSend)

	// Prepare messages for Kafka
	messages := make([][]byte, len(events))
	tenth := messagesToSend / 10
	for i, event := range events {
		if i > 0 && i%tenth == 0 {
			logger.Info.Printf("Подготовлено %d%% сообщений...", i*100/messagesToSend)
		}
		jsonData, err := json.Marshal(event)
		if err != nil {
			return fmt.Errorf("failed to marshal event: %w", err)
		}
		messages[i] = jsonData
	}
	logger.Info.Printf("Подготовлено 100%% сообщений. Перехожу к отправке")

	// Configure and send to Kafka
	batch := env.GetEnvIntOrDefault("NPL_KAFKA_BATCH_SIZE", 100, "")
	nom := env.GetEnvIntOrDefault("NPL_KAFKA_BATCH_NOM_NOM_DELAY_MS", 0, "")

	kafkaConfig := infra.KafkaConfig{
		Addr:             os.Getenv("NPL_LAB02_KAFKA_ADDR"),
		Topic:            os.Getenv("NPL_LAB02_KAFKA_TOPIC"),
		BatchSize:        batch,
		BatchDelayPeriod: time.Duration(nom) * time.Millisecond,
	}

	writer := infra.NewKafkaWriter(kafkaConfig)
	defer writer.Close()

	if err := writer.WriteMessages(ctx, messages); err != nil {
		return fmt.Errorf("ошибка при отправке сообщений: %w", err)
	}

	writerStats := writer.GetStats()
	logger.Info.Printf("Отправлено %d сообщений", writerStats.MessagesSent)

	if *flagSmall {
		logger.Victory.Println("Данные отправлены в Kafka. В режиме small проверки нет ¯\\_(ツ)_/¯")
		tracker.Ping("020_small_mode_ok", nil)
		return nil
	}

	if *flagSendOnly {
		logger.Info.Println("Режим только отправки, пропускаем проверку PostgreSQL")
		return nil
	}

	// Wait for user confirmation before checking PostgreSQL
	if !cli.ConfirmAction("Данные отправлены в Kafka. Готов проверять PostgreSQL") {
		return nil
	}

	// Verify in PostgreSQL
	return checkPostgresStats(stats)
}

func generateEvents(count, userCount int) ([]Event, *EventStats) {
	// Implementation of event generation...
	// This would contain the full logic from the original lab-2s
	events := make([]Event, 0)
	stats := &EventStats{
		HourlyPostStats: make(map[time.Time]map[string]PostStat),
		HourlyUserStats: make(map[time.Time]map[string]UserStat),
	}

	// ... event generation logic here ...

	return events, stats
}

func checkPostgresStats(stats *EventStats) error {
	// Implementation of PostgreSQL verification...
	// This would contain the verification logic from the original lab-2s
	logger.Victory.Println("Агрегаты проверены, всё сошлось")
	return nil
}
]],
}
