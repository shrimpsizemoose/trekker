"""Pydantic models for lab checker configuration."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

# -----------------------------------------------------------------------------
# Import Registry
# -----------------------------------------------------------------------------

# Always included in generated Go code
BASE_IMPORTS: set[str] = {"fmt", "os", "flag"}

# Each check type declares which Go stdlib imports it needs.
# Each check type declares which helper template partials it needs.
CHECK_TYPE_HELPERS: dict[str, list[str]] = {
    "param_equals": ["checks/param_equals_helpers.go.j2"],
    "forbidden_address": ["checks/forbidden_address_helpers.go.j2"],
    "http_get": ["checks/http_get_helpers.go.j2"],
    "http_get_random_path": ["checks/http_get_helpers.go.j2"],
    "http_request": [],
    "http_batch": ["checks/http_batch_helpers.go.j2"],
    "http_batch_repeat": ["checks/http_batch_helpers.go.j2"],
    "kafka_topic_exists": ["checks/kafka_topic_exists_helpers.go.j2"],
    "kafka_roundtrip": ["checks/kafka_roundtrip_helpers.go.j2"],
    "kafka_send_file": [],
    "kafka_compare": ["checks/kafka_compare_helpers.go.j2"],
    "postgres_tables_empty": ["checks/postgres_tables_empty_helpers.go.j2"],
    "clickhouse_query_simple": ["checks/clickhouse_query_simple_helpers.go.j2"],
}

# Each check type declares which Go stdlib imports it needs.
CHECK_TYPE_STDLIB_IMPORTS: dict[str, set[str]] = {
    "param_equals": {"strings"},
    "forbidden_address": {"strings"},
    "wait": {"time"},
    "http_get": {"context", "os/signal", "net/http", "crypto/rand", "math/big"},
    "http_get_random_path": {"context", "os/signal", "net/http", "crypto/rand", "math/big"},
    "http_request": {"context", "os/signal", "net/http", "strings", "encoding/json", "io"},
    "http_batch": {"context", "os/signal", "net/http", "strings", "encoding/json", "io", "time"},
    "http_batch_repeat": {"context", "os/signal", "net/http", "strings", "encoding/json", "io", "time"},
    "kafka_topic_exists": {"context", "os/signal", "time"},
    "kafka_roundtrip": {"context", "os/signal", "time"},
    "kafka_send_file": {"context", "os/signal", "bufio", "time"},
    "kafka_compare": {
        "context", "os/signal", "encoding/json", "fmt", "math",
        "os", "bufio", "strings", "time", "bytes",
    },
    "postgres_connect": {"context", "os/signal", "database/sql"},
    "postgres_tables_empty": {"context", "os/signal", "database/sql"},
    "custom": {"context", "os/signal"},
    "clickhouse_query_simple": {"net/http", "net/url", "io", "strings"},
}

# -----------------------------------------------------------------------------
# Common / Shared Models
# -----------------------------------------------------------------------------


class LabMeta(BaseModel):
    """Lab metadata."""

    id: str
    name: str
    env_prefix: str = ""


class EnvVar(BaseModel):
    """Required environment variable."""

    name: str
    error: str


class OptionalEnvVar(BaseModel):
    """Optional environment variable with default."""

    name: str
    default: str = ""
    message: str = ""


class OptionalEnvInt(BaseModel):
    """Optional integer environment variable with default."""

    name: str
    default: int = 0
    message: str = ""


class Flag(BaseModel):
    """Command-line flag."""

    name: str
    type: Literal["bool", "string", "int"] = "bool"
    default: str = ""
    description: str = ""


class ConfirmField(BaseModel):
    """Field to display in confirmation prompt."""

    name: str
    masked: bool = False
    default: str = ""


class AnalyticsConfig(BaseModel):
    """Analytics configuration."""

    url_env: str = "KANELBULLE"
    health_url_env: str = ""
    skip_tls: bool = False
    offline: bool = False  # print to console instead of sending over wire
    common_data: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)


class EmbeddedData(BaseModel):
    """Embedded data file."""

    name: str
    file: str


class FailureAction(BaseModel):
    """Action on check failure."""

    event: str = ""
    message: str = ""


class SuccessAction(BaseModel):
    """Action on check success."""

    event: str = ""


class CustomCode(BaseModel):
    """Custom Go code to embed."""

    imports: list[str] = Field(default_factory=list)
    types: str = ""
    types_file: str = ""  # path to .go file with type definitions
    code: str = ""
    code_file: str = ""  # path to .go file with custom functions


class BuildConfig(BaseModel):
    """Build configuration for go.mod generation."""

    module: str = ""
    go_version: str = "1.23"


# -----------------------------------------------------------------------------
# Check Type Models
# -----------------------------------------------------------------------------


class BaseCheck(BaseModel):
    """Common fields for all check types."""

    name: str = Field(
        default="",
        description="Optional identifier for this check, used in logs and analytics",
    )
    description: str = Field(
        default="",
        description="Brief text explaining what the check does, shown in --checks output",
    )
    skip_on_flag: str = Field(
        default="",
        description="Skip this check if the specified command-line flag is set",
    )
    on_failure: FailureAction = Field(
        default_factory=FailureAction, description="Action to take when check fails"
    )
    on_success: SuccessAction = Field(
        default_factory=SuccessAction, description="Action to take when check passes"
    )


class ParamEqualsCheck(BaseCheck):
    """Check that an environment variable equals an expected value."""

    type: Literal["param_equals"] = "param_equals"
    env_var: str = Field(description="Name of the environment variable to check")
    expected: str = Field(description="Expected value for the environment variable")
    case_insensitive: bool = Field(
        default=False, description="If true, comparison is case-insensitive"
    )


class ForbiddenAddressCheck(BaseCheck):
    """Check that an address is not in a forbidden list."""

    type: Literal["forbidden_address"] = "forbidden_address"
    env_var: str = Field(
        description="Name of environment variable containing the address to validate"
    )
    forbidden: list[str] = Field(
        default_factory=list, description="List of forbidden addresses/patterns"
    )


class WaitCheck(BaseCheck):
    """Wait for a specified duration."""

    type: Literal["wait"] = "wait"
    seconds: int = Field(description="Number of seconds to wait")
    message: str = Field(
        default="", description="Optional message to display while waiting"
    )


# --- HTTP Checks ---


class HTTPAuth(BaseModel):
    """HTTP authentication configuration."""

    type: Literal["none", "basic", "bearer"] = Field(
        default="none", description="Authentication type: none, basic, or bearer"
    )
    user_env: str = Field(
        default="", description="Environment variable name for username (basic auth)"
    )
    pass_env: str = Field(
        default="", description="Environment variable name for password (basic auth)"
    )
    token_env: str = Field(
        default="",
        description="Environment variable name for bearer token (bearer auth)",
    )


class ResponseCheck(BaseModel):
    """Response field validation."""

    field: str = Field(
        description="JSON field path to validate (e.g., 'user.id' or 'status')"
    )
    expected: str = Field(default="", description="Expected value for the field")
    from_data: str = Field(
        default="", description="Reference to test data field to compare against"
    )


class HTTPGetCheck(BaseCheck):
    """Simple HTTP GET check."""

    type: Literal["http_get"] = "http_get"
    url: str = Field(
        description="URL to request, supports ${VAR} substitution from environment variables"
    )
    expected_status: int = Field(
        default=200, description="Expected HTTP status code (default: 200)"
    )
    message_before: str = Field(
        default="", description="Message to display before making the request"
    )
    message_success: str = Field(
        default="", description="Message to display on successful response"
    )
    on_request: str = Field(
        default="", description="Analytics event to emit when request is sent"
    )
    on_response: str = Field(
        default="", description="Analytics event to emit when response is received"
    )


class HTTPGetRandomPathCheck(BaseCheck):
    """HTTP GET with random path segment (useful for testing 404 handling)."""

    type: Literal["http_get_random_path"] = "http_get_random_path"
    url: str = Field(description="Base URL, a random path segment will be appended")
    expected_status: int = Field(
        default=200, description="Expected HTTP status code (default: 200)"
    )
    message_before: str = Field(
        default="", description="Message to display before making the request"
    )
    message_success: str = Field(
        default="", description="Message to display on successful response"
    )
    on_request: str = Field(
        default="", description="Analytics event to emit when request is sent"
    )
    on_response: str = Field(
        default="", description="Analytics event to emit when response is received"
    )


class HTTPRequestCheck(BaseCheck):
    """Full HTTP request with custom method, body, and authentication."""

    type: Literal["http_request"] = "http_request"
    url: str = Field(description="Request URL, supports ${VAR} substitution")
    method: str = Field(
        default="GET", description="HTTP method (GET, POST, PUT, DELETE, etc.)"
    )
    expected_status: int = Field(default=200, description="Expected HTTP status code")
    message_before: str = Field(
        default="", description="Message to display before making the request"
    )
    message_success: str = Field(
        default="", description="Message to display on successful response"
    )
    content_type: str = Field(default="", description="Content-Type header value")
    body: str = Field(default="", description="Request body (for POST/PUT)")
    auth: HTTPAuth = Field(
        default_factory=HTTPAuth, description="Authentication configuration"
    )
    response_checks: list[ResponseCheck] = Field(
        default_factory=list, description="List of response field validations"
    )


class HTTPBatchCheck(BaseCheck):
    """Iterate over test data, send multiple HTTP requests."""

    type: Literal["http_batch"] = "http_batch"
    url: str = Field(description="Request URL, supports ${VAR} substitution")
    method: str = Field(default="POST", description="HTTP method for all requests")
    content_type: str = Field(
        default="application/json", description="Content-Type header"
    )
    test_data: str = Field(
        description="Name of embedded_data entry to use as test data"
    )
    request_template: str = Field(
        description="Request body template with placeholders like {{.Field}}"
    )
    response_checks: list[ResponseCheck] = Field(
        default_factory=list, description="Validations for each response"
    )
    delay_ms: int = Field(
        default=0, description="Delay in milliseconds between requests"
    )
    message_before: str = Field(default="", description="Message before starting batch")
    message_success: str = Field(
        default="", description="Message after batch completes"
    )


class HTTPBatchRepeatCheck(BaseCheck):
    """Repeat a previous http_batch check (useful for cache validation)."""

    type: Literal["http_batch_repeat"] = "http_batch_repeat"
    reuse: str = Field(description="Name of the http_batch check to repeat")
    response_checks: list[ResponseCheck] = Field(
        default_factory=list, description="Override original response checks"
    )
    message_before: str = Field(
        default="", description="Message before repeating batch"
    )
    message_success: str = Field(
        default="", description="Message after repeat completes"
    )


# --- Kafka Checks ---


class KafkaTopicExistsCheck(BaseCheck):
    """Check that a Kafka topic exists and is accessible."""

    type: Literal["kafka_topic_exists"] = "kafka_topic_exists"
    kafka_addr_env: str = Field(
        description="Environment variable name containing Kafka address (host:port)"
    )
    kafka_topic_env: str = Field(
        description="Environment variable name containing topic name"
    )
    on_connect: str = Field(
        default="", description="Analytics event when connected to Kafka"
    )
    on_partitions_read: str = Field(
        default="", description="Analytics event when partitions are read"
    )


class KafkaRoundtripCheck(BaseCheck):
    """Send messages to Kafka and verify they can be received."""

    type: Literal["kafka_roundtrip"] = "kafka_roundtrip"
    kafka_addr_env: str = Field(
        description="Environment variable name containing Kafka address"
    )
    kafka_topic_env: str = Field(
        description="Environment variable name containing topic name"
    )
    message_count: int = Field(default=1, description="Number of test messages to send")
    wait_seconds: int = Field(
        default=5, description="Seconds to wait for messages to be received"
    )
    message_generator: str = Field(
        default="", description="Optional custom Go function to generate messages"
    )


class KafkaSendFileCheck(BaseCheck):
    """Send contents of a file to a Kafka topic."""

    type: Literal["kafka_send_file"] = "kafka_send_file"
    kafka_addr_env: str = Field(
        description="Environment variable name containing Kafka address"
    )
    kafka_topic_env: str = Field(
        description="Environment variable name containing topic name"
    )
    file: str = Field(description="Path to file containing messages to send")


class KafkaCompareCheck(BaseCheck):
    """Send JSONL to a Kafka input topic, read from output topic, compare messages."""

    type: Literal["kafka_compare"] = "kafka_compare"
    kafka_addr_env: str = Field(
        description="Environment variable name containing Kafka address (host:port)"
    )

    # Send phase
    send_topic_env: str = Field(
        description="Environment variable name containing input topic name"
    )
    send_file_jsonl: str = Field(
        description="JSONL file to send (must match an embedded_data entry)"
    )

    # Receive phase
    receive_topic_env: str = Field(
        description="Environment variable name containing output topic name"
    )
    receive_expected_file_jsonl: str = Field(
        description="JSONL file with expected messages (must match an embedded_data entry)"
    )
    receive_wait_before_seconds: int = Field(
        default=0, description="Seconds to wait before reading output topic"
    )
    receive_timeout_seconds: int = Field(
        default=120, description="Timeout in seconds for reading all expected messages"
    )

    # Comparison
    match_by: list[str] = Field(
        description="Fields forming the composite key for matching messages"
    )
    compare: list[str] = Field(
        description="Fields to compare between expected and received messages"
    )
    float_tolerance: float = Field(
        default=0.0001, description="Maximum allowed difference for float comparisons"
    )

    message_before: str = Field(
        default="", description="Message to display before starting"
    )
    message_success: str = Field(
        default="", description="Message to display on success"
    )


# --- Postgres Checks ---


class PostgresConnectCheck(BaseCheck):
    """Verify PostgreSQL database connectivity."""

    type: Literal["postgres_connect"] = "postgres_connect"
    postgres_url_env: str = Field(
        description="Environment variable with PostgreSQL connection URL"
    )
    on_connect: str = Field(
        default="", description="Analytics event when connection succeeds"
    )


class PostgresTablesEmptyCheck(BaseCheck):
    """Verify that specified PostgreSQL tables have no rows."""

    type: Literal["postgres_tables_empty"] = "postgres_tables_empty"
    postgres_url_env: str = Field(
        description="Environment variable with PostgreSQL connection URL"
    )
    tables: list[str] = Field(
        default_factory=list, description="List of table names that should be empty"
    )
    message_before: str = Field(
        default="", description="Message before checking tables"
    )
    on_start: str = Field(default="", description="Analytics event when check starts")


# --- Custom Check ---


class ClickhouseQuerySimpleCheck(BaseCheck):
    """Run a single ClickHouse query via HTTP and validate the response."""

    type: Literal["clickhouse_query_simple"] = "clickhouse_query_simple"
    clickhouse_addr_env: str = Field(
        description="Environment variable name containing ClickHouse host:port"
    )
    clickhouse_user_env: str = Field(
        default="", description="Environment variable name for ClickHouse user (optional)"
    )
    clickhouse_pass_env: str = Field(
        default="",
        description="Environment variable name for ClickHouse password (optional)",
    )
    query: str = Field(description="ClickHouse SQL query, supports ${VAR} substitution")
    expected: str = Field(
        default="",
        description="Expected exact value of trimmed response (mutually exclusive with expected_rows)",
    )
    expected_rows: int = Field(
        default=-1,
        description="Expected number of non-empty lines in response (-1 means not set, mutually exclusive with expected)",
    )
    message_before: str = Field(
        default="", description="Message to display before running the query"
    )
    message_success: str = Field(
        default="", description="Message to display on success"
    )
    on_request: str = Field(
        default="", description="Analytics event to emit when query is sent"
    )
    on_response: str = Field(
        default="", description="Analytics event to emit when response is received"
    )

    @model_validator(mode="after")
    def check_expected_xor_rows(self) -> "ClickhouseQuerySimpleCheck":
        has_expected = bool(self.expected)
        has_rows = self.expected_rows >= 0
        if has_expected == has_rows:
            raise ValueError("exactly one of 'expected' or 'expected_rows' must be set")
        return self


class CustomCheck(BaseCheck):
    """Custom check implemented as a Go function in custom_code."""

    type: Literal["custom"] = "custom"
    func: str = Field(
        description="Name of the Go function to call (defined in custom_code)"
    )
    requires: list[str] = Field(
        default_factory=list, description="Environment variables required by this check"
    )


# -----------------------------------------------------------------------------
# Discriminated Union
# -----------------------------------------------------------------------------

Check = Annotated[
    ParamEqualsCheck
    | ForbiddenAddressCheck
    | WaitCheck
    | HTTPGetCheck
    | HTTPGetRandomPathCheck
    | HTTPRequestCheck
    | HTTPBatchCheck
    | HTTPBatchRepeatCheck
    | KafkaTopicExistsCheck
    | KafkaRoundtripCheck
    | KafkaSendFileCheck
    | KafkaCompareCheck
    | PostgresConnectCheck
    | PostgresTablesEmptyCheck
    | ClickhouseQuerySimpleCheck
    | CustomCheck,
    Field(discriminator="type"),
]


# -----------------------------------------------------------------------------
# Lab Configuration
# -----------------------------------------------------------------------------


class LabConfig(BaseModel):
    """Complete lab configuration."""

    lab: LabMeta

    required_env: list[EnvVar] = Field(default_factory=list)
    optional_env: list[OptionalEnvVar] = Field(default_factory=list)
    optional_env_int: list[OptionalEnvInt] = Field(default_factory=list)

    flags: list[Flag] = Field(default_factory=list)

    usage_header: str = ""
    usage_vars: str = ""
    usage_docker: str = ""  # optional, can contain ${IMAGE}
    usage_debug: str = ""  # optional, can contain ${DEBUG}
    confirm_display: list[ConfirmField | str] = Field(default_factory=list)

    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)

    embedded_data: list[EmbeddedData] = Field(default_factory=list)

    checks: list[Check] = Field(default_factory=list)

    success_message: str = ""

    custom_code: CustomCode = Field(default_factory=CustomCode)

    build: BuildConfig = Field(default_factory=BuildConfig)

    @property
    def env_prefix(self) -> str:
        return self.lab.env_prefix

    @property
    def has_http_checks(self) -> bool:
        return any(c.type in ("http_get", "http_get_random_path") for c in self.checks)

    @property
    def has_http_request_checks(self) -> bool:
        return any(c.type == "http_request" for c in self.checks)

    @property
    def has_http_batch_checks(self) -> bool:
        return any(c.type in ("http_batch", "http_batch_repeat") for c in self.checks)

    @property
    def has_param_checks(self) -> bool:
        return any(c.type == "param_equals" for c in self.checks)

    @property
    def has_kafka_checks(self) -> bool:
        return any(
            c.type
            in (
                "kafka_topic_exists",
                "kafka_roundtrip",
                "kafka_send_file",
                "kafka_compare",
            )
            for c in self.checks
        )

    @property
    def has_kafka_send_file_checks(self) -> bool:
        return any(c.type == "kafka_send_file" for c in self.checks)

    @property
    def has_kafka_compare_checks(self) -> bool:
        return any(c.type == "kafka_compare" for c in self.checks)

    @property
    def has_postgres_checks(self) -> bool:
        return any(
            c.type in ("postgres_connect", "postgres_tables_empty") for c in self.checks
        )

    @property
    def has_clickhouse_simple_checks(self) -> bool:
        return any(c.type == "clickhouse_query_simple" for c in self.checks)

    @property
    def has_custom_checks(self) -> bool:
        return any(c.type == "custom" for c in self.checks)

    @property
    def has_forbidden_addr_checks(self) -> bool:
        return any(c.type == "forbidden_address" for c in self.checks)

    @property
    def has_wait_checks(self) -> bool:
        return any(c.type == "wait" for c in self.checks)

    @property
    def has_flags(self) -> bool:
        return len(self.flags) > 0

    @property
    def has_masked_fields(self) -> bool:
        for field in self.confirm_display:
            if isinstance(field, ConfirmField) and field.masked:
                return True
        return False

    @property
    def has_context(self) -> bool:
        """Whether rootCtx is needed."""
        return (
            self.has_http_checks
            or self.has_http_request_checks
            or self.has_http_batch_checks
            or self.has_kafka_checks
            or self.has_postgres_checks
            or self.has_custom_checks
        )

    def get_confirm_fields(self) -> list[ConfirmField]:
        """Normalize confirm_display to list of ConfirmField."""
        # Build lookup of optional env defaults
        opt_defaults: dict[str, str] = {}
        for env in self.optional_env:
            if env.default:
                opt_defaults[env.name] = env.default
        for env in self.optional_env_int:
            opt_defaults[env.name] = str(env.default)

        if not self.confirm_display:
            sources = self.required_env + self.optional_env + self.optional_env_int
            return [
                ConfirmField(
                    name=env.name,
                    masked=False,
                    default=opt_defaults.get(env.name, ""),
                )
                for env in sources
            ]

        result = []
        for field in self.confirm_display:
            if isinstance(field, str):
                result.append(ConfirmField(
                    name=field,
                    masked=False,
                    default=opt_defaults.get(field, ""),
                ))
            else:
                if not field.default and field.name in opt_defaults:
                    field = field.model_copy(
                        update={"default": opt_defaults[field.name]}
                    )
                result.append(field)
        return result

    @property
    def required_helper_templates(self) -> list[str]:
        """Compute unique ordered list of helper template partials needed."""
        seen: set[str] = set()
        result: list[str] = []
        for check in self.checks:
            for tpl in CHECK_TYPE_HELPERS.get(check.type, []):
                if (tpl not in seen) and (seen := seen | {tpl}):
                    result.append(tpl)
        return result

    @property
    def required_stdlib_imports(self) -> set[str]:
        """Compute all required Go stdlib imports from check types."""
        result = set(BASE_IMPORTS)
        for check in self.checks:
            result |= CHECK_TYPE_STDLIB_IMPORTS.get(check.type, set())
        return result

    @property
    def auto_third_party_imports(self) -> set[str]:
        """Trekker/third-party packages auto-imported by the template."""
        auto = {"trekker:analytics", "trekker:cli", "trekker:env", "trekker:logger"}
        if self.has_kafka_checks:
            auto.add("trekker:infra")
        if self.has_masked_fields:
            auto.add("trekker:utils")
        return auto

    def get_filtered_imports(self) -> list[str]:
        """Custom imports minus auto-generated ones."""
        excluded = self.required_stdlib_imports | self.auto_third_party_imports
        return [imp for imp in self.custom_code.imports if imp not in excluded]
