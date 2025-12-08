# trekker-builder: Pre-configured image for building lab checkers from Lua configs
#
# Usage in user's Dockerfile:
#   FROM ghcr.io/shrimpsizemoose/trekker-builder:latest AS builder
#   COPY lab00.lua /input/
#   RUN trekgen -input /input/lab00.lua -output /build/main.go && \
#       cd /build && go mod tidy && \
#       CGO_ENABLED=0 go build -ldflags="-s -w" -o /checker main.go
#
#   FROM alpine:3.19
#   RUN apk add --no-cache ca-certificates tzdata
#   COPY --from=builder /checker /checker
#   ENTRYPOINT ["/checker"]

FROM golang:1.24-alpine AS builder

RUN apk add --no-cache git

# Copy trekker source
COPY . /trekker

# Build trekgen
WORKDIR /trekker
RUN go build -o /usr/local/bin/trekgen ./codegen/cmd/trekgen

# Prepare build directory with go.mod template
WORKDIR /build
COPY codegen/checker.go.mod go.mod
RUN go mod download

# Final image
FROM golang:1.24-alpine

RUN apk add --no-cache git ca-certificates tzdata

# Copy trekker source (needed for replace directive)
COPY --from=builder /trekker /trekker

# Copy pre-built trekgen
COPY --from=builder /usr/local/bin/trekgen /usr/local/bin/trekgen

# Copy pre-configured build directory
COPY --from=builder /build /build

# Copy Go module cache
COPY --from=builder /go/pkg/mod /go/pkg/mod

WORKDIR /build

LABEL org.opencontainers.image.source="https://github.com/shrimpsizemoose/trekker"
LABEL org.opencontainers.image.description="Builder image for trekker lab checkers"
