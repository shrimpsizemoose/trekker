-- Lab 03: Kafka roundtrip with anti-cheat
-- Demonstrates new trekker features:
--   - forbidden_address check type
--   - kafka_roundtrip check type
--   - requires field for custom checks
--   - trekker: import shorthand

lab = {
    id = "03",
    name = "Kafka Roundtrip Lab",
    env_prefix = "NPL",
}

required_env = {
    { name = "STUDENT",       error = "Мне надо знать, как тебя зовут" },
    { name = "TOKEN",         error = "Мне нужен токен, чтобы убедиться что ты это ты" },
    { name = "LAB03_KAFKA",   error = "Укажи адрес кафки" },
    { name = "LAB03_TOPIC",   error = "Укажи топик для теста" },
}

usage_text = [[
🤌 Чекер конфигурируется через переменные окружения

{{.EnvPrefix}}_LAB03_KAFKA - адрес кафки в формате host:port
{{.EnvPrefix}}_LAB03_TOPIC - топик для roundtrip теста
{{.EnvPrefix}}_STUDENT - ваше имя, как логин в ЛК
{{.EnvPrefix}}_TOKEN - ваш секретный токен

Пример env.conf:
  NPL_LAB03_KAFKA=12.34.56.78:9092
  NPL_LAB03_TOPIC=my_test_topic
  NPL_STUDENT=john.doe
  NPL_TOKEN=sk-npl-xxxxx

Запуск:
  docker run --rm -it --env-file env.conf {{.Image}}

Мануал по дебагу: {{.Debug}}
]]

confirm_display = {
    "LAB03_KAFKA",
    "LAB03_TOPIC",
    "STUDENT",
    { name = "TOKEN", masked = true },
}

analytics = {
    skip_tls = true,
    common_data = {
        kafkaAddr = "LAB03_KAFKA",
        kafkaTopic = "LAB03_TOPIC",
    },
    headers = {
        ["x-npl-lab"] = "03",
        ["x-npl-student"] = "env:STUDENT",
        ["Authorization"] = "Bearer env:TOKEN",
    },
}

checks = {
    -- 1. Anti-cheat: block known shared infrastructure
    --    Uses new "forbidden_address" check type
    {
        type = "forbidden_address",
        name = "anti_cheat",
        env_var = "LAB03_KAFKA",
        forbidden = {
            "kafka.shared-infra.example.com",
            "10.0.0.100",
        },
        on_failure = {
            event = "005_cheater_detected",
            message = "Используй свою кафку, а не общую инфраструктуру!",
        },
    },

    -- 2. Verify topic exists before roundtrip
    {
        type = "kafka_topic_exists",
        name = "topic_check",
        kafka_addr_env = "LAB03_KAFKA",
        kafka_topic_env = "LAB03_TOPIC",
        on_success = {
            event = "020_topic_exists",
        },
    },

    -- 3. Full roundtrip test: produce N messages, wait, consume N
    --    Uses new "kafka_roundtrip" check type with analytics events
    {
        type = "kafka_roundtrip",
        name = "roundtrip",
        kafka_addr_env = "LAB03_KAFKA",
        kafka_topic_env = "LAB03_TOPIC",
        message_count = 5,
        wait_seconds = 2,
        message_generator = "sequential",  -- "sequential", "timestamp", or "uuid"
        analytics = {
            on_produce = "030_messages_sent",
            on_consume = "060_messages_consumed",
        },
        on_failure = {
            event = "010_roundtrip_failed",
        },
        on_success = {
            event = "070_roundtrip_complete",
        },
    },

    -- 4. Custom validation with declared dependencies
    --    Uses new "requires" field - no need for dummy built-in checks
    {
        type = "custom",
        name = "final_validation",
        func = "validateEnvironment",
        requires = { "context" },  -- ensures rootCtx is available
    },
}

success_message = "Kafka roundtrip успешен! Лаба сдана! 🎉"

custom_code = {
    -- Using trekker: shorthand for imports
    imports = {
        "regexp",
    },

    code = [[
var topicPattern = regexp.MustCompile(`^[a-zA-Z0-9_-]+$`)

func validateEnvironment(ctx context.Context) error {
    topic := os.Getenv("NPL_LAB03_TOPIC")
    if !topicPattern.MatchString(topic) {
        return fmt.Errorf("топик содержит недопустимые символы: %s", topic)
    }
    logger.Victory.Println("Финальная валидация пройдена")
    return nil
}
]],
}
