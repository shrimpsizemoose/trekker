package utils

import (
	"crypto/rand"
	"math"
)

const DefaultAlphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"

// NewNanoID generates a 21-character NanoID string.
func NewNanoID() (string, error) {
	return NewNanoIDSize(21)
}

// NewNanoIDSize generates a NanoID string of the specified length.
func NewNanoIDSize(size int) (string, error) {
	alphabet := DefaultAlphabet
	mask := 1
	for mask < len(alphabet) {
		mask = (mask << 1) | 1
	}
	step := int(math.Ceil(1.6 * float64(mask) * float64(size) / float64(len(alphabet))))

	id := make([]byte, size)
	buf := make([]byte, step)
	cursor := 0

	for {
		if _, err := rand.Read(buf); err != nil {
			return "", err
		}
		for i := range step {
			idx := int(buf[i]) & mask
			if idx < len(alphabet) {
				id[cursor] = alphabet[idx]
				cursor++
				if cursor == size {
					return string(id), nil
				}
			}
		}
	}
}
