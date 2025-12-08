package codegen

import (
	"bytes"
	"embed"
	"fmt"
	"os"
	"strings"
	"text/template"

	lua "github.com/yuin/gopher-lua"
)

//go:embed templates/*.tmpl
var templateFS embed.FS

// LabConfig represents the parsed Lua configuration
type LabConfig struct {
	ID        string
	Name      string
	EnvPrefix string

	RequiredEnv    []EnvVar
	OptionalEnv    []OptionalEnvVar
	OptionalEnvInt []OptionalEnvInt

	Flags []Flag

	UsageText      string
	ConfirmDisplay []ConfirmField

	Analytics AnalyticsConfig

	Checks []Check

	SuccessMessage string

	// Custom Go code to embed
	CustomImports []string
	CustomTypes   string
	CustomCode    string

	// Computed fields for template conditionals
	HasHTTPChecks           bool
	HasParamChecks          bool
	HasKafkaChecks          bool
	HasPostgresChecks       bool
	HasCustomChecks         bool
	HasForbiddenAddrChecks  bool
	HasKafkaRoundtripChecks bool
	HasFlags                bool
}

type EnvVar struct {
	Name  string
	Error string
}

type OptionalEnvVar struct {
	Name    string
	Default string
	Message string
}

type OptionalEnvInt struct {
	Name    string
	Default int
	Message string
}

type Flag struct {
	Name        string
	Type        string // "bool", "string", "int"
	Default     string
	Description string
}

type ConfirmField struct {
	Name   string
	Masked bool
}

type AnalyticsConfig struct {
	SkipTLS    bool
	CommonData map[string]string // key -> env var name
	Headers    map[string]string // header name -> value (may contain "env:VAR")
}

type Check struct {
	Type string
	Name string
	// For param_equals
	EnvVar          string
	Expected        string
	CaseInsensitive bool
	OnFailure       FailureAction
	OnSuccess       SuccessAction
	// For http_get / http_get_random_path
	URL            string
	ExpectedStatus int
	MessageBefore  string
	MessageSuccess string
	// For kafka_topic_exists and kafka_roundtrip
	KafkaAddrEnv  string
	KafkaTopicEnv string
	// For kafka_roundtrip
	MessageCount     int
	WaitSeconds      int
	MessageGenerator string // "uuid", "sequential", "timestamp"
	// For postgres_tables_empty
	PostgresURLEnv string
	Tables         []string
	// For forbidden_address
	ForbiddenAddresses []string
	// For custom code blocks
	CustomFunc string
	Requires   []string // dependencies: "context", "kafka", "infra", "time"
	SkipOnFlag string   // skip this check if flag is set
}

type FailureAction struct {
	Event   string
	Message string
}

type SuccessAction struct {
	Event string
}

// ParseLuaConfig reads a Lua file and extracts the lab configuration
func ParseLuaConfig(filename string) (*LabConfig, error) {
	L := lua.NewState()
	defer L.Close()

	if err := L.DoFile(filename); err != nil {
		return nil, fmt.Errorf("failed to parse Lua file: %w", err)
	}

	config := &LabConfig{}

	// Parse 'lab' table
	if err := parseLab(L, config); err != nil {
		return nil, err
	}

	// Parse 'required_env' table
	if err := parseRequiredEnv(L, config); err != nil {
		return nil, err
	}

	// Parse 'optional_env' table
	if err := parseOptionalEnv(L, config); err != nil {
		return nil, err
	}

	// Parse 'optional_env_int' table
	if err := parseOptionalEnvInt(L, config); err != nil {
		return nil, err
	}

	// Parse 'flags' table
	if err := parseFlags(L, config); err != nil {
		return nil, err
	}

	// Parse usage_text and expand template variables
	if v := L.GetGlobal("usage_text"); v.Type() == lua.LTString {
		usageTemplate := v.String()
		// Replace template variables with Go format specifiers
		usageTemplate = strings.ReplaceAll(usageTemplate, "{{.EnvPrefix}}", config.EnvPrefix)
		usageTemplate = strings.ReplaceAll(usageTemplate, "{{.Image}}", "%s")
		usageTemplate = strings.ReplaceAll(usageTemplate, "{{.Debug}}", "%s")
		config.UsageText = usageTemplate
	}

	// Parse confirm_display
	if err := parseConfirmDisplay(L, config); err != nil {
		return nil, err
	}

	// Parse analytics
	if err := parseAnalytics(L, config); err != nil {
		return nil, err
	}

	// Parse checks
	if err := parseChecks(L, config); err != nil {
		return nil, err
	}

	// Parse custom code sections
	if err := parseCustomCode(L, config); err != nil {
		return nil, err
	}

	// Parse success_message
	if v := L.GetGlobal("success_message"); v.Type() == lua.LTString {
		config.SuccessMessage = v.String()
	}

	// Compute derived fields
	for _, check := range config.Checks {
		switch check.Type {
		case "http_get", "http_get_random_path":
			config.HasHTTPChecks = true
		case "param_equals":
			config.HasParamChecks = true
		case "kafka_topic_exists":
			config.HasKafkaChecks = true
		case "kafka_roundtrip":
			config.HasKafkaChecks = true
			config.HasKafkaRoundtripChecks = true
		case "postgres_connect", "postgres_tables_empty":
			config.HasPostgresChecks = true
		case "custom":
			config.HasCustomChecks = true
			// Process requires to set appropriate flags
			for _, req := range check.Requires {
				switch req {
				case "kafka", "infra":
					config.HasKafkaChecks = true
				}
			}
		case "forbidden_address":
			config.HasForbiddenAddrChecks = true
		}
	}
	config.HasFlags = len(config.Flags) > 0

	return config, nil
}

func parseLab(L *lua.LState, config *LabConfig) error {
	labTable := L.GetGlobal("lab")
	if labTable.Type() != lua.LTTable {
		return fmt.Errorf("'lab' must be a table")
	}
	t := labTable.(*lua.LTable)

	if v := t.RawGetString("id"); v.Type() == lua.LTString {
		config.ID = v.String()
	}
	if v := t.RawGetString("name"); v.Type() == lua.LTString {
		config.Name = v.String()
	}
	if v := t.RawGetString("env_prefix"); v.Type() == lua.LTString {
		config.EnvPrefix = v.String()
	}

	return nil
}

func parseRequiredEnv(L *lua.LState, config *LabConfig) error {
	envTable := L.GetGlobal("required_env")
	if envTable.Type() != lua.LTTable {
		return nil // Optional
	}
	t := envTable.(*lua.LTable)

	t.ForEach(func(_, v lua.LValue) {
		if v.Type() == lua.LTTable {
			entry := v.(*lua.LTable)
			ev := EnvVar{}
			if name := entry.RawGetString("name"); name.Type() == lua.LTString {
				ev.Name = name.String()
			}
			if errMsg := entry.RawGetString("error"); errMsg.Type() == lua.LTString {
				ev.Error = errMsg.String()
			}
			config.RequiredEnv = append(config.RequiredEnv, ev)
		}
	})

	return nil
}

func parseOptionalEnv(L *lua.LState, config *LabConfig) error {
	envTable := L.GetGlobal("optional_env")
	if envTable.Type() != lua.LTTable {
		return nil
	}
	t := envTable.(*lua.LTable)

	t.ForEach(func(_, v lua.LValue) {
		if v.Type() == lua.LTTable {
			entry := v.(*lua.LTable)
			ev := OptionalEnvVar{}
			if name := entry.RawGetString("name"); name.Type() == lua.LTString {
				ev.Name = name.String()
			}
			if def := entry.RawGetString("default"); def.Type() == lua.LTString {
				ev.Default = def.String()
			}
			if msg := entry.RawGetString("message"); msg.Type() == lua.LTString {
				ev.Message = msg.String()
			}
			config.OptionalEnv = append(config.OptionalEnv, ev)
		}
	})

	return nil
}

func parseOptionalEnvInt(L *lua.LState, config *LabConfig) error {
	envTable := L.GetGlobal("optional_env_int")
	if envTable.Type() != lua.LTTable {
		return nil
	}
	t := envTable.(*lua.LTable)

	t.ForEach(func(_, v lua.LValue) {
		if v.Type() == lua.LTTable {
			entry := v.(*lua.LTable)
			ev := OptionalEnvInt{}
			if name := entry.RawGetString("name"); name.Type() == lua.LTString {
				ev.Name = name.String()
			}
			if def := entry.RawGetString("default"); def.Type() == lua.LTNumber {
				ev.Default = int(lua.LVAsNumber(def))
			}
			if msg := entry.RawGetString("message"); msg.Type() == lua.LTString {
				ev.Message = msg.String()
			}
			config.OptionalEnvInt = append(config.OptionalEnvInt, ev)
		}
	})

	return nil
}

func parseFlags(L *lua.LState, config *LabConfig) error {
	flagsTable := L.GetGlobal("flags")
	if flagsTable.Type() != lua.LTTable {
		return nil
	}
	t := flagsTable.(*lua.LTable)

	t.ForEach(func(_, v lua.LValue) {
		if v.Type() == lua.LTTable {
			entry := v.(*lua.LTable)
			f := Flag{Type: "bool"} // default to bool
			if name := entry.RawGetString("name"); name.Type() == lua.LTString {
				f.Name = name.String()
			}
			if typ := entry.RawGetString("type"); typ.Type() == lua.LTString {
				f.Type = typ.String()
			}
			if def := entry.RawGetString("default"); def.Type() == lua.LTString {
				f.Default = def.String()
			}
			if desc := entry.RawGetString("description"); desc.Type() == lua.LTString {
				f.Description = desc.String()
			}
			config.Flags = append(config.Flags, f)
		}
	})

	return nil
}

func parseConfirmDisplay(L *lua.LState, config *LabConfig) error {
	cdTable := L.GetGlobal("confirm_display")
	if cdTable.Type() != lua.LTTable {
		return nil
	}
	t := cdTable.(*lua.LTable)

	t.ForEach(func(_, v lua.LValue) {
		switch v.Type() {
		case lua.LTString:
			config.ConfirmDisplay = append(config.ConfirmDisplay, ConfirmField{
				Name:   v.String(),
				Masked: false,
			})
		case lua.LTTable:
			entry := v.(*lua.LTable)
			cf := ConfirmField{}
			if name := entry.RawGetString("name"); name.Type() == lua.LTString {
				cf.Name = name.String()
			}
			if masked := entry.RawGetString("masked"); masked.Type() == lua.LTBool {
				cf.Masked = lua.LVAsBool(masked)
			}
			config.ConfirmDisplay = append(config.ConfirmDisplay, cf)
		}
	})

	return nil
}

func parseAnalytics(L *lua.LState, config *LabConfig) error {
	aTable := L.GetGlobal("analytics")
	if aTable.Type() != lua.LTTable {
		return nil
	}
	t := aTable.(*lua.LTable)

	config.Analytics.CommonData = make(map[string]string)
	config.Analytics.Headers = make(map[string]string)

	if v := t.RawGetString("skip_tls"); v.Type() == lua.LTBool {
		config.Analytics.SkipTLS = lua.LVAsBool(v)
	}

	// Parse common_data - table of key = env_var_name
	// Each entry becomes: "key": os.Getenv("PREFIX_env_var_name")
	if cd := t.RawGetString("common_data"); cd.Type() == lua.LTTable {
		cd.(*lua.LTable).ForEach(func(k, v lua.LValue) {
			if k.Type() == lua.LTString && v.Type() == lua.LTString {
				key := k.String()
				envVar := v.String()
				config.Analytics.CommonData[key] = envVar
			}
		})
	}

	// Parse headers
	if h := t.RawGetString("headers"); h.Type() == lua.LTTable {
		h.(*lua.LTable).ForEach(func(k, v lua.LValue) {
			if k.Type() == lua.LTString && v.Type() == lua.LTString {
				config.Analytics.Headers[k.String()] = v.String()
			}
		})
	}

	return nil
}

func parseChecks(L *lua.LState, config *LabConfig) error {
	checksTable := L.GetGlobal("checks")
	if checksTable.Type() != lua.LTTable {
		return nil
	}
	t := checksTable.(*lua.LTable)

	t.ForEach(func(_, v lua.LValue) {
		if v.Type() != lua.LTTable {
			return
		}
		entry := v.(*lua.LTable)

		check := Check{}
		if typ := entry.RawGetString("type"); typ.Type() == lua.LTString {
			check.Type = typ.String()
		}

		if name := entry.RawGetString("name"); name.Type() == lua.LTString {
			check.Name = name.String()
		}

		switch check.Type {
		case "param_equals":
			if ev := entry.RawGetString("env_var"); ev.Type() == lua.LTString {
				check.EnvVar = ev.String()
			}
			if exp := entry.RawGetString("expected"); exp.Type() == lua.LTString {
				check.Expected = exp.String()
			}
			if ci := entry.RawGetString("case_insensitive"); ci.Type() == lua.LTBool {
				check.CaseInsensitive = lua.LVAsBool(ci)
			}
		case "http_get", "http_get_random_path":
			if url := entry.RawGetString("url"); url.Type() == lua.LTString {
				check.URL = url.String()
			}
			if status := entry.RawGetString("expected_status"); status.Type() == lua.LTNumber {
				check.ExpectedStatus = int(lua.LVAsNumber(status))
			}
			if mb := entry.RawGetString("message_before"); mb.Type() == lua.LTString {
				check.MessageBefore = mb.String()
			}
			if ms := entry.RawGetString("message_success"); ms.Type() == lua.LTString {
				check.MessageSuccess = ms.String()
			}
		case "kafka_topic_exists":
			if addr := entry.RawGetString("kafka_addr_env"); addr.Type() == lua.LTString {
				check.KafkaAddrEnv = addr.String()
			}
			if topic := entry.RawGetString("kafka_topic_env"); topic.Type() == lua.LTString {
				check.KafkaTopicEnv = topic.String()
			}
			if mb := entry.RawGetString("message_before"); mb.Type() == lua.LTString {
				check.MessageBefore = mb.String()
			}
			if ms := entry.RawGetString("message_success"); ms.Type() == lua.LTString {
				check.MessageSuccess = ms.String()
			}
		case "postgres_connect", "postgres_tables_empty":
			if url := entry.RawGetString("postgres_url_env"); url.Type() == lua.LTString {
				check.PostgresURLEnv = url.String()
			}
			if tables := entry.RawGetString("tables"); tables.Type() == lua.LTTable {
				tables.(*lua.LTable).ForEach(func(_, v lua.LValue) {
					if v.Type() == lua.LTString {
						check.Tables = append(check.Tables, v.String())
					}
				})
			}
			if mb := entry.RawGetString("message_before"); mb.Type() == lua.LTString {
				check.MessageBefore = mb.String()
			}
		case "custom":
			if fn := entry.RawGetString("func"); fn.Type() == lua.LTString {
				check.CustomFunc = fn.String()
			}
			// Parse requires for custom checks
			if req := entry.RawGetString("requires"); req.Type() == lua.LTTable {
				req.(*lua.LTable).ForEach(func(_, v lua.LValue) {
					if v.Type() == lua.LTString {
						check.Requires = append(check.Requires, v.String())
					}
				})
			}
		case "forbidden_address":
			if ev := entry.RawGetString("env_var"); ev.Type() == lua.LTString {
				check.EnvVar = ev.String()
			}
			if forbidden := entry.RawGetString("forbidden"); forbidden.Type() == lua.LTTable {
				forbidden.(*lua.LTable).ForEach(func(_, v lua.LValue) {
					if v.Type() == lua.LTString {
						check.ForbiddenAddresses = append(check.ForbiddenAddresses, v.String())
					}
				})
			}
		case "kafka_roundtrip":
			if addr := entry.RawGetString("kafka_addr_env"); addr.Type() == lua.LTString {
				check.KafkaAddrEnv = addr.String()
			}
			if topic := entry.RawGetString("kafka_topic_env"); topic.Type() == lua.LTString {
				check.KafkaTopicEnv = topic.String()
			}
			if count := entry.RawGetString("message_count"); count.Type() == lua.LTNumber {
				check.MessageCount = int(lua.LVAsNumber(count))
			}
			if wait := entry.RawGetString("wait_seconds"); wait.Type() == lua.LTNumber {
				check.WaitSeconds = int(lua.LVAsNumber(wait))
			}
			if gen := entry.RawGetString("message_generator"); gen.Type() == lua.LTString {
				check.MessageGenerator = gen.String()
			}
			if mb := entry.RawGetString("message_before"); mb.Type() == lua.LTString {
				check.MessageBefore = mb.String()
			}
			if ms := entry.RawGetString("message_success"); ms.Type() == lua.LTString {
				check.MessageSuccess = ms.String()
			}
		}

		// Common: skip_on_flag
		if skip := entry.RawGetString("skip_on_flag"); skip.Type() == lua.LTString {
			check.SkipOnFlag = skip.String()
		}

		// Parse on_failure
		if of := entry.RawGetString("on_failure"); of.Type() == lua.LTTable {
			ofTable := of.(*lua.LTable)
			if ev := ofTable.RawGetString("event"); ev.Type() == lua.LTString {
				check.OnFailure.Event = ev.String()
			}
			if msg := ofTable.RawGetString("message"); msg.Type() == lua.LTString {
				check.OnFailure.Message = msg.String()
			}
		}

		// Parse on_success
		if os := entry.RawGetString("on_success"); os.Type() == lua.LTTable {
			osTable := os.(*lua.LTable)
			if ev := osTable.RawGetString("event"); ev.Type() == lua.LTString {
				check.OnSuccess.Event = ev.String()
			}
		}

		config.Checks = append(config.Checks, check)
	})

	return nil
}

func parseCustomCode(L *lua.LState, config *LabConfig) error {
	customTable := L.GetGlobal("custom_code")
	if customTable.Type() != lua.LTTable {
		return nil
	}
	t := customTable.(*lua.LTable)

	// Parse imports
	if imports := t.RawGetString("imports"); imports.Type() == lua.LTTable {
		imports.(*lua.LTable).ForEach(func(_, v lua.LValue) {
			if v.Type() == lua.LTString {
				imp := v.String()
				// Expand trekker: shorthand to full path
				if strings.HasPrefix(imp, "trekker:") {
					imp = "github.com/shrimpsizemoose/trekker/" + strings.TrimPrefix(imp, "trekker:")
				}
				config.CustomImports = append(config.CustomImports, imp)
			}
		})
	}

	// Parse types (raw Go code)
	if types := t.RawGetString("types"); types.Type() == lua.LTString {
		config.CustomTypes = types.String()
	}

	// Parse code (raw Go code for functions)
	if code := t.RawGetString("code"); code.Type() == lua.LTString {
		config.CustomCode = code.String()
	}

	return nil
}

// extractVars extracts variable names from URL patterns like "http://{{.VAR1}}:{{.VAR2}}"
func extractVars(url string) []string {
	var vars []string
	remaining := url
	for {
		start := strings.Index(remaining, "{{.")
		if start == -1 {
			break
		}
		remaining = remaining[start+3:]
		end := strings.Index(remaining, "}}")
		if end == -1 {
			break
		}
		vars = append(vars, remaining[:end])
		remaining = remaining[end+2:]
	}
	return vars
}

// urlToFormat converts "http://{{.VAR1}}:{{.VAR2}}" to "http://%s:%s"
func urlToFormat(url string) string {
	result := url
	for {
		start := strings.Index(result, "{{.")
		if start == -1 {
			break
		}
		end := strings.Index(result[start:], "}}")
		if end == -1 {
			break
		}
		result = result[:start] + "%s" + result[start+end+2:]
	}
	return result
}

// toLowerCamel converts UPPER_SNAKE to lowerCamel
func toLowerCamel(s string) string {
	parts := strings.Split(strings.ToLower(s), "_")
	for i := 1; i < len(parts); i++ {
		if len(parts[i]) > 0 {
			parts[i] = strings.ToUpper(parts[i][:1]) + parts[i][1:]
		}
	}
	return strings.Join(parts, "")
}

// toTitleCase converts "send-only" to "SendOnly" (valid Go identifier)
func toTitleCase(s string) string {
	// Replace hyphens with spaces for title casing, then remove spaces
	s = strings.ReplaceAll(s, "-", " ")
	s = strings.ReplaceAll(s, "_", " ")
	words := strings.Fields(s)
	for i, word := range words {
		if len(word) > 0 {
			words[i] = strings.ToUpper(word[:1]) + strings.ToLower(word[1:])
		}
	}
	return strings.Join(words, "")
}

// Generate produces Go source code from the parsed configuration
func Generate(config *LabConfig) (string, error) {
	funcMap := template.FuncMap{
		"hasPrefix":    strings.HasPrefix,
		"trimPrefix":   strings.TrimPrefix,
		"extractVars":  extractVars,
		"urlToFormat":  urlToFormat,
		"toLowerCamel": toLowerCamel,
		"title":        toTitleCase,
	}

	tmpl, err := template.New("checker.go.tmpl").Funcs(funcMap).ParseFS(templateFS, "templates/checker.go.tmpl")
	if err != nil {
		return "", fmt.Errorf("failed to parse template: %w", err)
	}

	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, config); err != nil {
		return "", fmt.Errorf("failed to execute template: %w", err)
	}

	return buf.String(), nil
}

// GenerateToFile writes the generated Go code to a file
func GenerateToFile(config *LabConfig, outputPath string) error {
	code, err := Generate(config)
	if err != nil {
		return err
	}

	return os.WriteFile(outputPath, []byte(code), 0644)
}
