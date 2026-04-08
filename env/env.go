package env

import (
	"os"
	"strconv"

	"github.com/joho/godotenv"
	"github.com/shrimpsizemoose/trekker/logger"
)

type EnvError struct {
	Key     string
	Message string
}

// загрузить переменные из .env файла, молча игнорируя если файла нет
func LoadEnv() {
	_ = godotenv.Load()
}

// GetEnvOrDefault("HOST", "localhost", "использую хост по умолчанию")
// -> "PORT не задан, использую порт по умолчанию: localhost"
func GetEnvOrDefault(key, defaultValue string, defaultComment string) string {
	if value, exists := os.LookupEnv(key); exists && value != "" {
		return value
	}
	if defaultComment != "" {
		logger.Warn.Printf("%s не задан, %s: %s", key, defaultComment, defaultValue)
	}
	// Persist default back into the process env so downstream checks that
	// read the variable via os.Getenv (e.g. postgres_tables_empty with
	// tables_from_env) see the same value announced in the startup banner.
	_ = os.Setenv(key, defaultValue)
	return defaultValue
}

// GetEnvIntOrDefault("PORT", 8000, "использую порт по умолчанию")
// -> "PORT не задан, использую порт по умолчанию: 8000"
// -> "PORT задан, но из 'куропаточка' не получается целое число, использую порт по умолчанию: 8000"
// (то же, что и GetEnvOrDefault, но пробует скастовать результат в int)
func GetEnvIntOrDefault(key string, defaultValue int, defaultComment string) int {
	value, exists := os.LookupEnv(key)
	if !exists {
		if defaultComment != "" {
			logger.Warn.Printf(
				"%s не задан, %s: %d",
				key,
				defaultComment,
				defaultValue,
			)
		}
		return defaultValue
	}

	num, err := strconv.Atoi(value)
	if err != nil {
		if defaultComment != "" {
			logger.Warn.Printf(
				"Ключ %s задан, но из %s не получается целое число, %s: %d",
				key,
				value,
				defaultComment,
				defaultValue,
			)
		}
		return defaultValue
	}

	return num
}

// проверяет, что нужные переменные окружения (ключи мапы) есть
// и выводит сообщения об ошибках (значения мапы) если нет
func RequireEnv(requirements map[string]string) {
	var errors []EnvError

	for k, v := range requirements {
		if _, exists := os.LookupEnv(k); !exists {
			errors = append(errors, EnvError{Key: k, Message: v})
		}
	}

	if len(errors) > 0 {
		logger.Error.Println("Мне не хватает некоторых переменных окружения 👇")
		for _, err := range errors {
			if err.Message == "" {
				logger.Error.Printf("Нет переменной окружения: %v", err.Key)
			} else {
				logger.Error.Printf("%s: %s", err.Key, err.Message)
			}
		}
		os.Exit(1)
	}
}
