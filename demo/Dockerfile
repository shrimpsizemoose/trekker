#####################################
#   STEP 1 build executable binary  #
#####################################
FROM golang:1.25-alpine AS builder

# git is needed to fetch the dependencies
RUN apk update && apk add --no-cache git

WORKDIR /app

COPY go.mod .
COPY go.sum .
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /app/main

#####################################
#   STEP 2 build a small image      #
#####################################
FROM scratch

LABEL org.opencontainers.image.source=https://github.com/shrimpsizemoose/trekker

COPY --from=builder /app/main /app/main

ENTRYPOINT ["/app/main"]
