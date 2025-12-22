package codegen

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

// TestParseAllExamples verifies all example Lua configs can be parsed
func TestParseAllExamples(t *testing.T) {
	examples, err := filepath.Glob("examples/lab*.lua")
	if err != nil {
		t.Fatalf("failed to glob examples: %v", err)
	}

	if len(examples) == 0 {
		t.Fatal("no example files found")
	}

	for _, example := range examples {
		t.Run(filepath.Base(example), func(t *testing.T) {
			config, err := ParseLuaConfig(example)
			if err != nil {
				t.Fatalf("failed to parse %s: %v", example, err)
			}

			if config.ID == "" {
				t.Error("config.ID should not be empty")
			}
			if config.EnvPrefix == "" {
				t.Error("config.EnvPrefix should not be empty")
			}
		})
	}
}

// TestGenerateAllExamples verifies all example Lua configs generate valid Go code
func TestGenerateAllExamples(t *testing.T) {
	examples, err := filepath.Glob("examples/lab*.lua")
	if err != nil {
		t.Fatalf("failed to glob examples: %v", err)
	}

	for _, example := range examples {
		t.Run(filepath.Base(example), func(t *testing.T) {
			config, err := ParseLuaConfig(example)
			if err != nil {
				t.Fatalf("failed to parse %s: %v", example, err)
			}

			code, err := Generate(config)
			if err != nil {
				t.Fatalf("failed to generate from %s: %v", example, err)
			}

			if !strings.Contains(code, "package main") {
				t.Error("generated code should contain 'package main'")
			}
			if !strings.Contains(code, "func main()") {
				t.Error("generated code should contain 'func main()'")
			}
		})
	}
}

// TestHTTPBatchParsing verifies http_batch specific parsing
func TestHTTPBatchParsing(t *testing.T) {
	config, err := ParseLuaConfig("examples/lab04.lua")
	if err != nil {
		t.Fatalf("failed to parse lab04.lua: %v", err)
	}

	if !config.HasHTTPBatchChecks {
		t.Error("HasHTTPBatchChecks should be true for lab04")
	}

	if !config.HasHTTPRequestChecks {
		t.Error("HasHTTPRequestChecks should be true for lab04")
	}

	if len(config.EmbeddedData) == 0 {
		t.Error("EmbeddedData should not be empty for lab04")
	}

	// Find the http_batch check
	var batchCheck *Check
	var repeatCheck *Check
	for i := range config.Checks {
		if config.Checks[i].Type == "http_batch" {
			batchCheck = &config.Checks[i]
		}
		if config.Checks[i].Type == "http_batch_repeat" {
			repeatCheck = &config.Checks[i]
		}
	}

	if batchCheck == nil {
		t.Fatal("http_batch check not found")
	}

	if batchCheck.Name != "predictions" {
		t.Errorf("expected batch name 'predictions', got %q", batchCheck.Name)
	}

	if batchCheck.HTTPBatch.TestData != "predictions" {
		t.Errorf("expected test_data 'predictions', got %q", batchCheck.HTTPBatch.TestData)
	}

	if len(batchCheck.ResponseChecks) != 2 {
		t.Errorf("expected 2 response checks, got %d", len(batchCheck.ResponseChecks))
	}

	// Verify response checks
	if batchCheck.ResponseChecks[0].JSONField != "prediction" {
		t.Errorf("first response check field should be 'prediction', got %q", batchCheck.ResponseChecks[0].JSONField)
	}
	if batchCheck.ResponseChecks[0].FromData != "expected" {
		t.Errorf("first response check should have FromData='expected', got %q", batchCheck.ResponseChecks[0].FromData)
	}

	if repeatCheck == nil {
		t.Fatal("http_batch_repeat check not found")
	}

	if repeatCheck.ReuseFrom != "predictions" {
		t.Errorf("expected reuse 'predictions', got %q", repeatCheck.ReuseFrom)
	}
}

// TestHTTPBatchCodeGeneration verifies http_batch generates correct Go code
func TestHTTPBatchCodeGeneration(t *testing.T) {
	config, err := ParseLuaConfig("examples/lab04.lua")
	if err != nil {
		t.Fatalf("failed to parse lab04.lua: %v", err)
	}

	code, err := Generate(config)
	if err != nil {
		t.Fatalf("failed to generate: %v", err)
	}

	// Check for required elements
	requiredSnippets := []string{
		"//go:embed testdata/lab04_predictions.json",
		"var predictionsData []byte",
		"type BatchTestCase map[string]interface{}",
		"type BatchResult struct",
		"var batchResults = make(map[string][]BatchResult)",
		"func expandTemplate(",
		"func getJSONField(",
		`batchName := "predictions"`,
		`previousResults, ok := batchResults["predictions"]`,
	}

	for _, snippet := range requiredSnippets {
		if !strings.Contains(code, snippet) {
			t.Errorf("generated code should contain %q", snippet)
		}
	}
}

// TestGeneratedCodeCompiles verifies generated code actually compiles
func TestGeneratedCodeCompiles(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping compilation test in short mode")
	}

	// Create temp directory
	tmpDir, err := os.MkdirTemp("", "trekker-test-*")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Parse and generate
	config, err := ParseLuaConfig("examples/lab04.lua")
	if err != nil {
		t.Fatalf("failed to parse: %v", err)
	}

	code, err := Generate(config)
	if err != nil {
		t.Fatalf("failed to generate: %v", err)
	}

	// Write main.go
	mainPath := filepath.Join(tmpDir, "main.go")
	if err := os.WriteFile(mainPath, []byte(code), 0644); err != nil {
		t.Fatalf("failed to write main.go: %v", err)
	}

	// Copy testdata
	testdataDir := filepath.Join(tmpDir, "testdata")
	if err := os.MkdirAll(testdataDir, 0755); err != nil {
		t.Fatalf("failed to create testdata dir: %v", err)
	}

	testdataSrc := "examples/testdata/lab04_predictions.json"
	testdataDst := filepath.Join(testdataDir, "lab04_predictions.json")
	data, err := os.ReadFile(testdataSrc)
	if err != nil {
		t.Fatalf("failed to read testdata: %v", err)
	}
	if err := os.WriteFile(testdataDst, data, 0644); err != nil {
		t.Fatalf("failed to write testdata: %v", err)
	}

	// Initialize go.mod
	cmd := exec.Command("go", "mod", "init", "testchecker")
	cmd.Dir = tmpDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go mod init failed: %v\n%s", err, out)
	}

	// Add replace directive
	cwd, _ := os.Getwd()
	trekkerPath := filepath.Dir(cwd) // go up from codegen to trekker root
	if filepath.Base(cwd) == "codegen" {
		// Already in codegen dir
	} else {
		trekkerPath = cwd
	}
	cmd = exec.Command("go", "mod", "edit", "-replace=github.com/shrimpsizemoose/trekker="+trekkerPath)
	cmd.Dir = tmpDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go mod edit failed: %v\n%s", err, out)
	}

	// Run go mod tidy
	cmd = exec.Command("go", "mod", "tidy")
	cmd.Dir = tmpDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go mod tidy failed: %v\n%s", err, out)
	}

	// Try to build
	cmd = exec.Command("go", "build", "-o", "checker", ".")
	cmd.Dir = tmpDir
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("go build failed: %v\n%s", err, out)
	}

	// Verify binary exists
	binPath := filepath.Join(tmpDir, "checker")
	if _, err := os.Stat(binPath); os.IsNotExist(err) {
		t.Error("expected checker binary to exist")
	}
}

// TestResponseChecksFromData verifies from_data field parsing
func TestResponseChecksFromData(t *testing.T) {
	config, err := ParseLuaConfig("examples/lab04.lua")
	if err != nil {
		t.Fatalf("failed to parse: %v", err)
	}

	var batchCheck *Check
	for i := range config.Checks {
		if config.Checks[i].Type == "http_batch" {
			batchCheck = &config.Checks[i]
			break
		}
	}

	if batchCheck == nil {
		t.Fatal("batch check not found")
	}

	// First check should use from_data
	if batchCheck.ResponseChecks[0].FromData == "" {
		t.Error("first response check should have FromData set")
	}

	// Second check should use static expected
	if batchCheck.ResponseChecks[1].Expected == "" {
		t.Error("second response check should have Expected set")
	}
	if batchCheck.ResponseChecks[1].FromData != "" {
		t.Error("second response check should not have FromData set")
	}
}

// TestEmbeddedDataParsing verifies embedded_data parsing
func TestEmbeddedDataParsing(t *testing.T) {
	config, err := ParseLuaConfig("examples/lab04.lua")
	if err != nil {
		t.Fatalf("failed to parse: %v", err)
	}

	if len(config.EmbeddedData) != 1 {
		t.Fatalf("expected 1 embedded data entry, got %d", len(config.EmbeddedData))
	}

	ed := config.EmbeddedData[0]
	if ed.Name != "predictions" {
		t.Errorf("expected name 'predictions', got %q", ed.Name)
	}
	if ed.File != "testdata/lab04_predictions.json" {
		t.Errorf("expected file 'testdata/lab04_predictions.json', got %q", ed.File)
	}
}

// TestBackwardsCompatibility ensures old configs still work
func TestBackwardsCompatibility(t *testing.T) {
	oldExamples := []string{
		"examples/lab00.lua",
		"examples/lab01.lua",
		"examples/lab02.lua",
		"examples/lab03.lua",
	}

	for _, example := range oldExamples {
		t.Run(filepath.Base(example), func(t *testing.T) {
			config, err := ParseLuaConfig(example)
			if err != nil {
				t.Fatalf("failed to parse %s: %v", example, err)
			}

			// These old examples shouldn't have http_batch
			if config.HasHTTPBatchChecks {
				t.Errorf("%s should not have HasHTTPBatchChecks", example)
			}

			// Should still generate
			code, err := Generate(config)
			if err != nil {
				t.Fatalf("failed to generate from %s: %v", example, err)
			}

			if !strings.Contains(code, "package main") {
				t.Error("generated code should contain 'package main'")
			}
		})
	}
}
