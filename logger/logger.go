package logger

import (
	"log"
	"os"
)

var (
	Error    = log.New(os.Stderr, "❌  ", 0)
	Info     = log.New(os.Stdout, "🤖  ", 0)
	Warn     = log.New(os.Stdout, "☝  ", 0)
	Question = log.New(os.Stdout, "❓  ", 0)
	Debug    = log.New(os.Stdout, "🚧  ", log.LstdFlags)
	Victory  = log.New(os.Stdout, "👍👍👍  ", 0)
	Waiting  = log.New(os.Stdout, "⏳  ", 0)
)
