# shrimpsizemoose/trekker

Go-библиотека и Py-кодогенератор для создания чекеров лабораторных работ.

## Структура

| Пакет | Назначение |
|-------|------------|
| `analytics/` | Отправка событий аналитики на удалённый сервер |
| `cli/` | Подтверждение действий и справка по использованию |
| `codegen/pytrekgen/` | Генерация Go-кода из YAML-конфигов (Python + Jinja2) |
| `codegen/` | ~~Go-кодогенератор из Lua~~ (deprecated) |
| `env/` | Загрузка и валидация переменных окружения |
| `infra/` | Kafka reader/writer с батчингом |
| `logger/` | Логгеры с эмодзи-префиксами |
| `utils/` | Маскирование токенов |

## Кодогенерация (pytrekgen)

Генерация чекеров из декларативных YAML-конфигов:

```bash
cd codegen/pytrekgen
uv run pytrekgen -i examples/lab02.yaml -o build/main.go --with-gomod
```

### Установка

```bash
cd codegen/pytrekgen
uv sync  # или pip install -e .
```

### YAML-конфиг

```yaml
lab:
  id: "02"
  name: "Kafka Pipeline Lab"
  env_prefix: "NPL"

build:
  module: github.com/newprolab/de_labs/checkers/lab-02
  go_version: "1.23"

required_env:
  - name: STUDENT
    error: "Мне надо знать, как тебя зовут"
  - name: TOKEN
    error: "Мне нужен токен"

optional_env:
  - name: PORT
    default: "8080"
    message: "использую порт по умолчанию"

usage_header: |
  Чекер конфигурируется через переменные окружения

usage_vars: |
  ${ENV_PREFIX}_STUDENT - ваше имя
  ${ENV_PREFIX}_TOKEN - ваш токен

usage_docker: |
  docker run --env-file env.conf ${IMAGE}

usage_debug: |
  Мануал по дебагу: ${DEBUG}

checks:
  - type: param_equals
    env_var: SOME_PARAM
    expected: "expected_value"
    on_failure:
      event: "check_failed"
      message: "Параметр не совпадает"

  - type: http_get
    url: "http://${HOST}:${PORT}/health"
    expected_status: 200
    message_before: "Проверяю health endpoint"
    message_success: "OK"

  - type: kafka_topic_exists
    kafka_addr_env: KAFKA_ADDR
    kafka_topic_env: KAFKA_TOPIC

  - type: postgres_connect
    postgres_url_env: DB_URL

  - type: custom
    func: myCustomCheck

success_message: "Все проверки пройдены!"

custom_code:
  imports:
    - encoding/json
  code: |
    func myCustomCheck(ctx context.Context) error {
        // custom logic
        return nil
    }
```

### Поддерживаемые типы проверок

| Тип | Описание |
|-----|----------|
| `param_equals` | Проверка переменной окружения на равенство значению |
| `http_get` | HTTP GET запрос с проверкой статуса |
| `http_get_random_path` | HTTP GET с рандомным путём (для проверки 404) |
| `http_request` | Полный HTTP запрос с методом, телом, авторизацией |
| `kafka_topic_exists` | Проверка существования топика Kafka |
| `postgres_connect` | Проверка подключения к PostgreSQL |
| `postgres_tables_empty` | Проверка что таблицы пустые |
| `custom` | Вызов кастомной Go-функции |

### CLI опции

```
pytrekgen -i config.yaml [-o output.go] [--with-gomod] [--debug]

  -i, --input      Входной YAML-конфиг (обязательно)
  -o, --output     Выходной Go-файл (по умолчанию stdout)
  --with-gomod     Генерировать go.mod рядом с выходным файлом
  --debug          Включить debug-логирование
```

## Сборка чекера

```bash
# Генерация
cd codegen/pytrekgen
uv run pytrekgen -i examples/lab02.yaml -o /tmp/checker/main.go --with-gomod

# Сборка
cd /tmp/checker
go mod tidy
go build -o checker .
```

### Dockerfile

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /build

# Копируем сгенерированные файлы
COPY main.go go.mod ./
RUN go mod tidy && \
    CGO_ENABLED=0 go build -ldflags="-s -w" -o /checker main.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata
COPY --from=builder /checker /checker
ENTRYPOINT ["/checker"]
```

### GitHub Actions

```yaml
name: Build Checker

on:
  push:
    paths:
      - 'checkers/lab-02/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v4

      - name: Generate checker
        run: |
          cd codegen/pytrekgen
          uv run pytrekgen -i ../../checkers/lab-02/config.yaml \
            -o ../../checkers/lab-02/build/main.go --with-gomod

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v6
        with:
          context: ./checkers/lab-02/build
          push: true
          tags: ghcr.io/${{ github.repository }}/lab-02:${{ github.sha }}
```

## Legacy: Lua + Go codegen

> **Deprecated**: Кодогенератор на Go (`codegen/cmd/trekgen`) и Lua-конфиги устарели.
> All cool kids use pytrekgen (YAML + Python) для новых чекеров.
> Legacy-код пока оставлен, но щащаща я допилю всё и выкину его

```bash
# не надо!!
go run ./codegen/cmd/trekgen -input codegen/examples/lab00.lua -output checker.go
```

Builder image для legacy подхода: `ghcr.io/shrimpsizemoose/trekker-builder`

## Зависимости

**pytrekgen (Python):**
- `jinja2` — шаблонизатор
- `pyyaml` — парсер YAML
- `pydantic` — валидация конфигов

**trekker (Go runtime):**
- `godotenv` — загрузка .env
- `kafka-go` — Kafka-клиент
- `lib/pq` — PostgreSQL драйвер
