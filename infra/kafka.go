package infra

import (
	"context"
	"fmt"
	"sync"
	"time"

	kafka "github.com/segmentio/kafka-go"
	"github.com/shrimpsizemoose/trekker/logger"
)

type KafkaConfig struct {
	Addr             string
	Topic            string
	BatchSize        int
	BatchDelayPeriod time.Duration
}

type WriterStats struct {
	MessagesSent int
	BytesSent    int64
	BatchesSent  int
	Errors       int
	LastSentAt   time.Time
	mu           sync.Mutex
}

type KafkaWriter struct {
	writer           *kafka.Writer
	stats            WriterStats
	batchSize        int
	batchDelayPeriod time.Duration
	lastBatchSentAt  time.Time
}

func NewKafkaWriter(cfg KafkaConfig) *KafkaWriter {
	batchSize := cfg.BatchSize
	if batchSize <= 0 {
		batchSize = 100		fmt.Printf("Использую размер батча по умолчанию %d messages\n", batchSize)
	}

	batchDelayPeriod := cfg.BatchDelayPeriod
	if batchDelayPeriod <= 0 {
		batchDelayPeriod = 0 // No delay by default
	}

	return &KafkaWriter{
		writer: &kafka.Writer{
			Addr:     kafka.TCP(cfg.Addr),
			Topic:    cfg.Topic,
			Balancer: &kafka.LeastBytes{},
		},
		stats:            WriterStats{},
		batchSize:        batchSize,
		batchDelayPeriod: batchDelayPeriod,
		lastBatchSentAt:  time.Now().Add(-batchDelayPeriod),
	}
}

func (w *KafkaWriter) WriteMessages(ctx context.Context, messages [][]byte) error {
	if len(messages) == 0 {
		return nil
	}

	var batches [][][]byte
	for i := 0; i < len(messages); i += w.batchSize {
		end := i + w.batchSize
		if end > len(messages) {
			end = len(messages)
		}
		batches = append(batches, messages[i:end])
	}

	totalErrors := 0
	for _, batch := range batches {
		if w.batchDelayPeriod > 0 {
			timeSinceLastBatch := time.Since(w.lastBatchSentAt)
			if timeSinceLastBatch < w.batchDelayPeriod {
				waitTime := w.batchDelayPeriod - timeSinceLastBatch
				fmt.Printf("Waiting %v before sending next batch\n", waitTime)

				timer := time.NewTimer(waitTime)
				select {
				case <-timer.C:
				case <-ctx.Done():
					if !timer.Stop() {
						<-timer.C
					}
					return ctx.Err()
				}
			}
		}

		kafkaMessages := make([]kafka.Message, len(batch))
		for i, msg := range batch {
			kafkaMessages[i] = kafka.Message{Value: msg}
		}

		err := w.writer.WriteMessages(ctx, kafkaMessages...)

		now := time.Now()
		w.lastBatchSentAt = now

		w.stats.mu.Lock()

		if err != nil {
			w.stats.Errors++
			totalErrors++
			fmt.Printf("не удалось записать сообщения в Kafka: %w", err)
		} else {
			w.stats.MessagesSent += len(batch)
			w.stats.BatchesSent++
			w.stats.LastSentAt = now

			var batchBytes int64
			for _, msg := range batch {
				batchBytes += int64(len(msg))

			}

			w.stats.BytesSent += batchBytes

			fmt.Printf("Sent batch of %d messages (%d bytes)\n", len(batch), batchBytes)
		}

		w.stats.mu.Unlock()
	}

	if totalErrors > 0 {
		return fmt.Errorf("Не смог отправить %d (из %d) батчей в Kafka", totalErrors, len(batches))
	}

	return nil
}

func (w *KafkaWriter) GetStats() WriterStats {
	w.stats.mu.Lock()
	defer w.stats.mu.Unlock()

	return WriterStats{
		MessagesSent: w.stats.MessagesSent,
		BytesSent:    w.stats.BytesSent,
		Errors:       w.stats.Errors,
		LastSentAt:   w.stats.LastSentAt,
	}
}

func (w *KafkaWriter) LogStats() {
	stats := w.GetStats()
	logger.Info.Printf(
		"[Kafka Writer Stats] Отправлено сообщений: %d, байт: %d bytes; Ошибок: %d\n",
		stats.MessagesSent,
		stats.BytesSent,
		stats.Errors,
	)
	logger.Info.Printf(
		"Последнее отправленное: %v",
		stats.LastSentAt.Format("2006-Jan-02 15:04:05.000 MST"),
,
	)
}

func (w *KafkaWriter) Close() error {
	w.LogStats()
	return w.writer.Close()
}

type KafkaReader struct {
	reader *kafka.Reader
}

func NewKafkaReader(cfg KafkaConfig) *KafkaReader {
	return &KafkaReader{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers: []string{cfg.Addr},
			Topic:   cfg.Topic,
		}),
	}
}

func (r *KafkaReader) ReadMessage(ctx context.Context) ([]byte, error) {
	msg, err := r.reader.ReadMessage(ctx)
	if err != nil {
		return nil, fmt.Errorf("Kafka: не удалось прочитать: %w", err)
	}
	return msg.Value, nil
}

func (r *KafkaReader) Close() error {
	return r.reader.Close()
}

func CheckKafkaTopic(addr, topic string) (bool, error) {
	conn, err := kafka.Dial("tcp", addr)
	if err != nil {
		return false, fmt.Errorf("[Kafka] не удалось подключиться: %w", err)
	}
	defer conn.Close()

	partitions, err := conn.ReadPartitions()
	if err != nil {
		return false, fmt.Errorf("[Kafka] не удалось прочитать партиции: %w", err)
	}

	for _, p := range partitions {
		if p.Topic == topic {
			return true, nil
		}
	}

	return false, nil
}

func WaitForKafka(addr string, timeout time.Duration) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	for {
		select {
		case <-ctx.Done():
			return fmt.Errorf("не дождался связи с Kafka")
		default:
			conn, err := kafka.Dial("tcp", addr)
			if err == nil {
				conn.Close()
				return nil
			}
			time.Sleep(1 * time.Second)
		}
	}
}
