"""Pydantic models for lab checker configuration."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# -----------------------------------------------------------------------------
# Common / Shared Models
# -----------------------------------------------------------------------------


class LabMeta(BaseModel):
    """Lab metadata."""

    id: str
    name: str
    env_prefix: str


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


class AnalyticsConfig(BaseModel):
    """Analytics configuration."""

    skip_tls: bool = False
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
    code: str = ""


# -----------------------------------------------------------------------------
# Check Type Models
# -----------------------------------------------------------------------------


class BaseCheck(BaseModel):
    """Common fields for all check types."""

    name: str = ""
    skip_on_flag: str = ""
    on_failure: FailureAction = Field(default_factory=FailureAction)
    on_success: SuccessAction = Field(default_factory=SuccessAction)


class ParamEqualsCheck(BaseCheck):
    """Check that an environment variable equals an expected value."""

    type: Literal["param_equals"] = "param_equals"
    env_var: str
    expected: str
    case_insensitive: bool = False


class ForbiddenAddressCheck(BaseCheck):
    """Check that an address is not in a forbidden list."""

    type: Literal["forbidden_address"] = "forbidden_address"
    env_var: str
    forbidden: list[str] = Field(default_factory=list)


class WaitCheck(BaseCheck):
    """Wait for a specified duration."""

    type: Literal["wait"] = "wait"
    seconds: int
    message: str = ""


# --- HTTP Checks ---


class HTTPAuth(BaseModel):
    """HTTP authentication configuration."""

    type: Literal["none", "basic", "bearer"] = "none"
    user_env: str = ""
    pass_env: str = ""
    token_env: str = ""


class ResponseCheck(BaseModel):
    """Response field validation."""

    field: str
    expected: str = ""
    from_data: str = ""


class HTTPGetCheck(BaseCheck):
    """Simple HTTP GET check."""

    type: Literal["http_get"] = "http_get"
    url: str
    expected_status: int = 200
    message_before: str = ""
    message_success: str = ""
    on_request: str = ""
    on_response: str = ""


class HTTPGetRandomPathCheck(BaseCheck):
    """HTTP GET with random path segment."""

    type: Literal["http_get_random_path"] = "http_get_random_path"
    url: str
    expected_status: int = 200
    message_before: str = ""
    message_success: str = ""
    on_request: str = ""
    on_response: str = ""


class HTTPRequestCheck(BaseCheck):
    """Full HTTP request with method, body, auth."""

    type: Literal["http_request"] = "http_request"
    url: str
    method: str = "GET"
    expected_status: int = 200
    message_before: str = ""
    message_success: str = ""
    content_type: str = ""
    body: str = ""
    auth: HTTPAuth = Field(default_factory=HTTPAuth)
    response_checks: list[ResponseCheck] = Field(default_factory=list)


class HTTPBatchCheck(BaseCheck):
    """Iterate over test data, send HTTP requests."""

    type: Literal["http_batch"] = "http_batch"
    url: str
    method: str = "POST"
    content_type: str = "application/json"
    test_data: str  # Name of embedded data
    request_template: str
    response_checks: list[ResponseCheck] = Field(default_factory=list)
    delay_ms: int = 0
    message_before: str = ""
    message_success: str = ""


class HTTPBatchRepeatCheck(BaseCheck):
    """Repeat a previous http_batch check (e.g., for cache validation)."""

    type: Literal["http_batch_repeat"] = "http_batch_repeat"
    reuse: str  # Name of the http_batch check to repeat
    message_before: str = ""
    message_success: str = ""


# --- Kafka Checks ---


class KafkaTopicExistsCheck(BaseCheck):
    """Check that a Kafka topic exists."""

    type: Literal["kafka_topic_exists"] = "kafka_topic_exists"
    kafka_addr_env: str
    kafka_topic_env: str


class KafkaRoundtripCheck(BaseCheck):
    """Send and receive messages through Kafka."""

    type: Literal["kafka_roundtrip"] = "kafka_roundtrip"
    kafka_addr_env: str
    kafka_topic_env: str
    message_count: int = 1
    wait_seconds: int = 5
    message_generator: str = ""


class KafkaSendFileCheck(BaseCheck):
    """Send file contents to Kafka."""

    type: Literal["kafka_send_file"] = "kafka_send_file"
    kafka_addr_env: str
    kafka_topic_env: str
    file: str


# --- Postgres Checks ---


class PostgresConnectCheck(BaseCheck):
    """Check Postgres connection."""

    type: Literal["postgres_connect"] = "postgres_connect"
    postgres_url_env: str


class PostgresTablesEmptyCheck(BaseCheck):
    """Check that Postgres tables are empty."""

    type: Literal["postgres_tables_empty"] = "postgres_tables_empty"
    postgres_url_env: str
    tables: list[str] = Field(default_factory=list)


# --- Custom Check ---


class CustomCheck(BaseCheck):
    """Custom check implemented in Go."""

    type: Literal["custom"] = "custom"
    func: str
    requires: list[str] = Field(default_factory=list)


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
    | PostgresConnectCheck
    | PostgresTablesEmptyCheck
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
    usage_debug: str = ""   # optional, can contain ${DEBUG}
    confirm_display: list[ConfirmField | str] = Field(default_factory=list)

    analytics: AnalyticsConfig = Field(default_factory=AnalyticsConfig)

    embedded_data: list[EmbeddedData] = Field(default_factory=list)

    checks: list[Check] = Field(default_factory=list)

    success_message: str = ""

    custom_code: CustomCode = Field(default_factory=CustomCode)

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
            c.type in ("kafka_topic_exists", "kafka_roundtrip", "kafka_send_file")
            for c in self.checks
        )

    @property
    def has_kafka_send_file_checks(self) -> bool:
        return any(c.type == "kafka_send_file" for c in self.checks)

    @property
    def has_postgres_checks(self) -> bool:
        return any(
            c.type in ("postgres_connect", "postgres_tables_empty") for c in self.checks
        )

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
        result = []
        for field in self.confirm_display:
            if isinstance(field, str):
                result.append(ConfirmField(name=field, masked=False))
            else:
                result.append(field)
        return result
