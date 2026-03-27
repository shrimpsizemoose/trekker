package utils

import (
	"strings"
	"testing"
)

func TestNewNanoIDDefaultLength(t *testing.T) {
	id, err := NewNanoID()
	if err != nil {
		t.Fatalf("NewNanoID() error: %v", err)
	}
	if len(id) != 21 {
		t.Errorf("expected length 21, got %d", len(id))
	}
}

func TestNewNanoIDSizeCustomLength(t *testing.T) {
	id, err := NewNanoIDSize(10)
	if err != nil {
		t.Fatalf("NewNanoIDSize(10) error: %v", err)
	}
	if len(id) != 10 {
		t.Errorf("expected length 10, got %d", len(id))
	}
}

func TestNewNanoIDAlphabet(t *testing.T) {
	id, err := NewNanoID()
	if err != nil {
		t.Fatalf("NewNanoID() error: %v", err)
	}
	for _, c := range id {
		if !strings.ContainsRune(DefaultAlphabet, c) {
			t.Errorf("character %q not in DefaultAlphabet", c)
		}
	}
}

func TestNewNanoIDUniqueness(t *testing.T) {
	id1, err := NewNanoID()
	if err != nil {
		t.Fatalf("first NewNanoID() error: %v", err)
	}
	id2, err := NewNanoID()
	if err != nil {
		t.Fatalf("second NewNanoID() error: %v", err)
	}
	if id1 == id2 {
		t.Errorf("two calls returned identical IDs: %s", id1)
	}
}
