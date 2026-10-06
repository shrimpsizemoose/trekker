# shrimpsizemoose/trekker

Go-библиотека и Py-кодогенератор для создания чекеров лабораторных работ.

## Структура

| Пакет | Назначение |
|-------|------------|
| `analytics/` | Отправка событий аналитики на удалённый сервер |
| `cli/` | Подтверждение действий и справка по использованию |
| `pytrekgen/` | Генерация Go-кода из YAML-конфигов (Python + Jinja2) |
| `env/` | Загрузка и валидация переменных окружения |
| `infra/` | Kafka reader/writer с батчингом |
| `logger/` | Логгеры с эмодзи-префиксами |
| `utils/` | Маскирование токенов |

## Кодогенерация (pytrekgen)

Генерация чекеров из декларативных YAML-конфигов:

```bash
cd pytrekgen
uv run pytrekgen -i examples/lab02.yaml -o build/main.go --with-gomod
```

### Установка

```bash
cd pytrekgen
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
| `http_batch` | Итерация по тестовым данным с HTTP-запросами |
| `http_batch_repeat` | Повтор batch-запросов (для проверки кэша) |
| `kafka_topic_exists` | Проверка существования топика Kafka |
| `kafka_roundtrip` | Отправка и получение сообщений через Kafka |
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
cd pytrekgen
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
          cd pytrekgen
          uv run pytrekgen -i ../checkers/lab-02/config.yaml \
            -o ../checkers/lab-02/build/main.go --with-gomod

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

## Сравнение результатов ClickHouse

`clickhouse_compare` выполняет запрос в режиме read-only и сравнивает ответ
JSONEachRow с ожидаемыми строками из JSONL-файла.

```yaml
- type: clickhouse_compare
  name: metrics
  clickhouse_addr_env: CH_ADDR
  query: |
    SELECT dataset_id, paid_orders_count, avg_paid_amount_cents
    FROM metrics WHERE dataset_id = {dataset_id:String}
  params:
    dataset_id: "${DATASET_ID}"
  expected_file_env: EXPECTED_METRICS
  match_by: [dataset_id]
  columns:
    dataset_id: string
    paid_orders_count: integer
    avg_paid_amount_cents: decimal
  timeout_seconds: 30
  request_timeout_seconds: 5
  poll_interval_ms: 500
```

Файл с ожидаемым результатом для этого запроса:

```json
{"dataset_id":"demo","paid_orders_count":4,"avg_paid_amount_cents":875.25}
```

При `env_prefix: NPL` задайте `NPL_CH_ADDR` (HTTP host:port), `NPL_DATASET_ID`
и `NPL_EXPECTED_METRICS` (путь к файлу). Если имя переменной уже начинается с `NPL_`,
чекер не добавляет его повторно. Для Basic Auth укажите `clickhouse_user_env`
и `clickhouse_pass_env`. [Полный конфиг](pytrekgen/examples/clickhouse_compare.yaml).

Чекер передаёт `params` как параметры ClickHouse, отдельно от SQL.
В значениях он раскрывает `${ENV_VAR}`, остальные `$` оставляет как есть.
Переменная должна существовать, но может быть пустой.

Укажите один источник ожидаемых строк: `expected_file_env` для пути из переменной
окружения или `expected_file_jsonl` для файла из `embedded_data`.
В первом случае файл может создать предыдущая проверка `custom`; чекер прочитает
его один раз перед запросами. Во втором файл нужен при сборке по пути
из `//go:embed`, относительно сгенерированного Go-файла.

В `columns` перечислите поля для сравнения и их типы: `string`, `integer`,
`decimal`, `boolean`. Поля из `match_by` должны входить в `columns`;
по ним чекер находит соответствующие строки. Порядок строк не влияет на результат,
лишние поля ответа чекер пропускает. Лишняя или пропущенная строка означает
расхождение, повтор ключа или отсутствие поля из `columns` вызывает ошибку.
`NULL` совпадает только с `NULL`. Пустой файл означает ноль строк.

Для `integer` и `decimal` подходят JSON-числа и строки с числами, без
экспоненциальной записи. В колонке `decimal` значения `833.670` и `"833.67"`
равны. Чекер сравнивает числа точно, без float и допуска на погрешность;
если нужно округление, добавьте его в SQL. Для `string` и `boolean`
нужны JSON-строки и значения `true`/`false` соответственно.

В примере чекер повторяет запрос с паузой 500 мс, пока строки не совпадут,
но не дольше 30 секунд. При `timeout_seconds: 0` он делает одну попытку.
`request_timeout_seconds` ограничивает время отдельного запроса.
Повторы идут только при расхождении строк или значений. Ошибки HTTP, сети,
JSON, типов, отсутствующие поля и дубли ключей сразу останавливают проверку.
При общем таймауте чекер выводит последнее расхождение, если оно было.

Оба результата хранятся в памяти; лимит каждого входного файла или ответа — 64 MiB.

## Зависимости

**pytrekgen (Python):**
- `jinja2` — шаблонизатор
- `pyyaml` — парсер YAML
- `pydantic` — валидация конфигов

**trekker (Go runtime):**
- `godotenv` — загрузка .env
- `kafka-go` — Kafka-клиент
- `lib/pq` — PostgreSQL драйвер
