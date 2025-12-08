# shrimpsizemoose/trekker

Go-библиотека и кодогенератор для создания чекеров лабораторных работ.

## Структура

| Пакет | Назначение |
|-------|------------|
| `analytics/` | Отправка событий аналитики на удалённый сервер |
| `cli/` | Подтверждение действий и справка по использованию |
| `codegen/` | Генерация Go-кода из Lua-конфигов |
| `env/` | Загрузка и валидация переменных окружения |
| `infra/` | Kafka reader/writer с батчингом |
| `logger/` | Логгеры с эмодзи-префиксами |
| `utils/` | Маскирование токенов |

## Кодогенерация

Основная фича — генерация чекеров из декларативных Lua-конфигов:

```bash
go run ./codegen/cmd/trekgen -input codegen/examples/lab00.lua -output checker.go
```

Lua-конфиг описывает:
- Метаданные лабы (ID, название, префикс переменных)
- Обязательные/опциональные переменные окружения
- Проверки (параметры, HTTP, Kafka, Postgres, кастомные функции)
- Сообщения успеха/ошибки

Результат — готовый Go-бинарник, который валидирует окружение, запускает проверки и отправляет аналитику.

## Builder Image

Для сборки чекеров доступен готовый Docker-образ `ghcr.io/shrimpsizemoose/trekker-builder`, который содержит:
- Скомпилированный `trekgen`
- Go 1.24
- Исходники trekker (для replace-директивы)
- Предзагруженные зависимости

### Использование

Создайте `Dockerfile` рядом с вашим Lua-конфигом:

```dockerfile
FROM ghcr.io/shrimpsizemoose/trekker-builder:latest AS builder
COPY lab00.lua /input/
RUN trekgen -input /input/lab00.lua -output /build/main.go && \
    cd /build && go mod tidy && \
    CGO_ENABLED=0 go build -ldflags="-s -w" -o /checker main.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata

# Ваши переменные окружения
ENV MY_VAR="value"

COPY --from=builder /checker /checker
ENTRYPOINT ["/checker"]
```

### GitHub Actions

```yaml
name: Build Checker

on:
  push:
    paths:
      - 'checkers/lab-0/**'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/build-push-action@v6
        with:
          context: ./checkers/lab-0
          push: true
          tags: ghcr.io/${{ github.repository }}/lab0:${{ github.sha }}
```

### Преимущества

- Не нужно клонировать trekker
- Не нужно компилировать trekgen
- Не нужно настраивать Go
- Полный контроль над Dockerfile (ENV, LABEL, дополнительные файлы)
- Быстрая сборка за счёт кэширования

## Локальная разработка

```bash
# Генерация чекера
go run ./codegen/cmd/trekgen -input codegen/examples/lab00.lua -output checker.go

# Запуск примеров
go run ./codegen/examples/lab00.lua
```

## Зависимости

- `godotenv` — загрузка .env
- `kafka-go` — Kafka-клиент
- `gopher-lua` — парсер Lua-конфигов
