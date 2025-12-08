package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"github.com/shrimpsizemoose/trekker/codegen"
)

func main() {
	inputFile := flag.String("input", "", "Input Lua configuration file")
	outputFile := flag.String("output", "", "Output Go file (defaults to stdout)")
	flag.Parse()

	if *inputFile == "" {
		fmt.Fprintln(os.Stderr, "Error: -input flag is required")
		flag.Usage()
		os.Exit(1)
	}

	config, err := codegen.ParseLuaConfig(*inputFile)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error parsing Lua config: %v\n", err)
		os.Exit(1)
	}

	if *outputFile == "" {
		code, err := codegen.Generate(config)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error generating code: %v\n", err)
			os.Exit(1)
		}
		fmt.Println(code)
	} else {
		// Ensure output directory exists
		dir := filepath.Dir(*outputFile)
		if err := os.MkdirAll(dir, 0755); err != nil {
			fmt.Fprintf(os.Stderr, "Error creating output directory: %v\n", err)
			os.Exit(1)
		}

		if err := codegen.GenerateToFile(config, *outputFile); err != nil {
			fmt.Fprintf(os.Stderr, "Error writing output: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("Generated: %s\n", *outputFile)
	}
}
