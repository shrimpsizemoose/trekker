"""Tests for config.py - Pydantic model validation."""

import pytest
from pydantic import ValidationError

from pytrekgen.config import (
    LabConfig,
    LabMeta,
    EnvVar,
    EnvOneOf,
    OptionalEnvVar,
    OptionalEnvInt,
    Flag,
    ConfirmField,
    AnalyticsConfig,
    BuildConfig,
    CustomCode,
    FailureAction,
    SuccessAction,
    # Check types
    ParamEqualsCheck,
    ForbiddenAddressCheck,
    WaitCheck,
    HTTPGetCheck,
    HTTPGetRandomPathCheck,
    HTTPRequestCheck,
    HTTPBatchCheck,
    KafkaTopicExistsCheck,
    KafkaRoundtripCheck,
    KafkaSendFileCheck,
    KafkaCompareCheck,
    PostgresConnectCheck,
    PostgresTablesEmptyCheck,
    CustomCheck,
)

from conftest import minimal_config


class TestLabMeta:
    """Tests for LabMeta model."""

    def test_valid_lab_meta(self):
        meta = LabMeta(id="01", name="Test Lab", env_prefix="NPL")
        assert meta.id == "01"
        assert meta.name == "Test Lab"
        assert meta.env_prefix == "NPL"

    def test_missing_id(self):
        with pytest.raises(ValidationError) as exc_info:
            LabMeta(name="Test", env_prefix="NPL")
        assert "id" in str(exc_info.value)

    def test_missing_name(self):
        with pytest.raises(ValidationError) as exc_info:
            LabMeta(id="01", env_prefix="NPL")
        assert "name" in str(exc_info.value)

    def test_missing_env_prefix_defaults_to_empty(self):
        meta = LabMeta(id="01", name="Test")
        assert meta.env_prefix == ""


class TestEnvVar:
    """Tests for EnvVar model."""

    def test_valid_env_var(self):
        ev = EnvVar(name="TOKEN", error="Need token")
        assert ev.name == "TOKEN"
        assert ev.error == "Need token"

    def test_missing_error(self):
        with pytest.raises(ValidationError):
            EnvVar(name="TOKEN")


class TestEnvOneOf:
    """Tests for EnvOneOf model."""

    def test_valid_env_one_of(self):
        one_of = EnvOneOf(vars=["REDIS", "REDIS_URL"], error="need one")
        assert one_of.vars == ["REDIS", "REDIS_URL"]
        assert one_of.error == "need one"


class TestOptionalEnvVar:
    """Tests for OptionalEnvVar model."""

    def test_with_defaults(self):
        ev = OptionalEnvVar(name="PORT")
        assert ev.name == "PORT"
        assert ev.default == ""
        assert ev.message == ""

    def test_with_values(self):
        ev = OptionalEnvVar(name="PORT", default="8080", message="using default port")
        assert ev.default == "8080"
        assert ev.message == "using default port"


class TestOptionalEnvInt:
    """Tests for OptionalEnvInt model."""

    def test_with_defaults(self):
        ev = OptionalEnvInt(name="BATCH_SIZE")
        assert ev.default == 0

    def test_with_int_value(self):
        ev = OptionalEnvInt(name="BATCH_SIZE", default=100)
        assert ev.default == 100


class TestFlag:
    """Tests for Flag model."""

    def test_bool_flag(self):
        flag = Flag(name="debug", type="bool", default="false", description="Enable debug")
        assert flag.name == "debug"
        assert flag.type == "bool"

    def test_string_flag(self):
        flag = Flag(name="output", type="string", default="stdout")
        assert flag.type == "string"

    def test_int_flag(self):
        flag = Flag(name="count", type="int", default="10")
        assert flag.type == "int"

    def test_invalid_flag_type(self):
        with pytest.raises(ValidationError):
            Flag(name="x", type="float")


class TestConfirmField:
    """Tests for ConfirmField model."""

    def test_default_not_masked(self):
        field = ConfirmField(name="STUDENT")
        assert field.masked is False

    def test_masked_field(self):
        field = ConfirmField(name="TOKEN", masked=True)
        assert field.masked is True


class TestAnalyticsConfig:
    """Tests for AnalyticsConfig model."""

    def test_defaults(self):
        analytics = AnalyticsConfig()
        assert analytics.skip_tls is False
        assert analytics.common_data == {}
        assert analytics.headers == {}

    def test_with_values(self):
        analytics = AnalyticsConfig(
            skip_tls=True,
            common_data={"lab": "01"},
            headers={"x-token": "secret"},
        )
        assert analytics.skip_tls is True
        assert analytics.common_data["lab"] == "01"


class TestBuildConfig:
    """Tests for BuildConfig model."""

    def test_defaults(self):
        build = BuildConfig()
        assert build.module == ""
        assert build.go_version == "1.23"

    def test_with_values(self):
        build = BuildConfig(module="github.com/test/checker", go_version="1.22")
        assert build.go_version == "1.22"


def test_description_defaults_to_empty():
    check = ParamEqualsCheck(env_var="X", expected="y")
    assert check.description == ""


def test_description_is_set():
    check = ParamEqualsCheck(
        env_var="X", expected="y", description="Проверяет режим"
    )
    assert check.description == "Проверяет режим"


def test_description_parsed_from_dict():
    config = minimal_config(
        checks=[
            {
                "type": "http_get",
                "url": "http://localhost",
                "description": "Проверяет health endpoint",
            }
        ]
    )
    assert config.checks[0].description == "Проверяет health endpoint"


class TestCheckTypes:
    """Tests for individual check type models."""

    def test_param_equals_check(self):
        check = ParamEqualsCheck(env_var="MODE", expected="prod")
        assert check.type == "param_equals"
        assert check.env_var == "MODE"
        assert check.case_insensitive is False

    def test_param_equals_case_insensitive(self):
        check = ParamEqualsCheck(env_var="MODE", expected="prod", case_insensitive=True)
        assert check.case_insensitive is True

    def test_forbidden_address_check(self):
        check = ForbiddenAddressCheck(
            env_var="KAFKA",
            forbidden=["10.0.0.1", "bad.host"],
        )
        assert check.type == "forbidden_address"
        assert len(check.forbidden) == 2

    def test_wait_check(self):
        check = WaitCheck(seconds=5, message="Waiting...")
        assert check.type == "wait"
        assert check.seconds == 5

    def test_http_get_check(self):
        check = HTTPGetCheck(url="http://localhost/health")
        assert check.type == "http_get"
        assert check.expected_status == 200  # default

    def test_http_get_random_path_check(self):
        check = HTTPGetRandomPathCheck(url="http://localhost")
        assert check.type == "http_get_random_path"

    def test_http_request_check(self):
        check = HTTPRequestCheck(url="http://localhost/api", method="POST")
        assert check.type == "http_request"
        assert check.method == "POST"

    def test_kafka_topic_exists_check(self):
        check = KafkaTopicExistsCheck(kafka_addr_env="KAFKA", kafka_topic_env="TOPIC")
        assert check.type == "kafka_topic_exists"

    def test_kafka_roundtrip_check(self):
        check = KafkaRoundtripCheck(
            kafka_addr_env="KAFKA",
            kafka_topic_env="TOPIC",
            message_count=10,
            wait_seconds=5,
        )
        assert check.type == "kafka_roundtrip"
        assert check.message_count == 10

    def test_kafka_send_file_check(self):
        check = KafkaSendFileCheck(
            kafka_addr_env="KAFKA",
            kafka_topic_env="TOPIC",
            file="data.json",
        )
        assert check.type == "kafka_send_file"

    def test_kafka_compare_check(self):
        check = KafkaCompareCheck(
            kafka_addr_env="KAFKA",
            send_topic_env="TOPIC_IN",
            send_file_jsonl="input.jsonl",
            receive_topic_env="TOPIC_OUT",
            receive_expected_file_jsonl="expected.jsonl",
            match_by=["start_ts", "end_ts"],
            compare=["revenue", "visitors"],
        )
        assert check.type == "kafka_compare"
        assert check.float_tolerance == 0.0001
        assert check.receive_wait_before_seconds == 0
        assert check.receive_timeout_seconds == 120

    def test_postgres_connect_check(self):
        check = PostgresConnectCheck(postgres_url_env="DB_URL")
        assert check.type == "postgres_connect"

    def test_postgres_tables_empty_check(self):
        check = PostgresTablesEmptyCheck(
            postgres_url_env="DB_URL",
            tables=["users", "orders"],
        )
        assert check.type == "postgres_tables_empty"
        assert len(check.tables) == 2

    def test_custom_check(self):
        check = CustomCheck(func="myValidator", requires=["context"])
        assert check.type == "custom"
        assert check.func == "myValidator"
        assert "context" in check.requires


class TestCheckTypeDiscriminator:
    """Test that check types are correctly discriminated in LabConfig."""

    def test_param_equals_parsed(self):
        config = minimal_config(
            checks=[{"type": "param_equals", "env_var": "FOO", "expected": "bar"}]
        )
        assert isinstance(config.checks[0], ParamEqualsCheck)

    def test_forbidden_address_parsed(self):
        config = minimal_config(
            checks=[{"type": "forbidden_address", "env_var": "X", "forbidden": ["y"]}]
        )
        assert isinstance(config.checks[0], ForbiddenAddressCheck)

    def test_kafka_roundtrip_parsed(self):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_roundtrip",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                }
            ]
        )
        assert isinstance(config.checks[0], KafkaRoundtripCheck)

    def test_kafka_compare_parsed(self):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_compare",
                    "kafka_addr_env": "K",
                    "send_topic_env": "TI",
                    "send_file_jsonl": "input.jsonl",
                    "receive_topic_env": "TO",
                    "receive_expected_file_jsonl": "expected.jsonl",
                    "match_by": ["ts"],
                    "compare": ["val"],
                }
            ]
        )
        assert isinstance(config.checks[0], KafkaCompareCheck)

    def test_unknown_check_type_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            minimal_config(checks=[{"type": "nonexistent_check", "foo": "bar"}])
        # Should mention the invalid discriminator
        assert "type" in str(exc_info.value).lower()


class TestCheckRequiredFields:
    """Each check type has required fields."""

    def test_param_equals_requires_env_var(self):
        with pytest.raises(ValidationError):
            ParamEqualsCheck(expected="bar")  # missing env_var

    def test_param_equals_requires_expected(self):
        with pytest.raises(ValidationError):
            ParamEqualsCheck(env_var="FOO")  # missing expected

    def test_forbidden_address_requires_env_var(self):
        with pytest.raises(ValidationError):
            ForbiddenAddressCheck(forbidden=["x"])

    def test_http_get_requires_url(self):
        with pytest.raises(ValidationError):
            HTTPGetCheck(expected_status=200)

    def test_kafka_topic_exists_requires_addr(self):
        with pytest.raises(ValidationError):
            KafkaTopicExistsCheck(kafka_topic_env="T")

    def test_kafka_roundtrip_requires_addr(self):
        with pytest.raises(ValidationError):
            KafkaRoundtripCheck(kafka_topic_env="T")

    def test_kafka_compare_requires_fields(self):
        with pytest.raises(ValidationError):
            KafkaCompareCheck(
                kafka_addr_env="K",
                send_topic_env="TI",
                # missing send_file_jsonl, receive fields, match_by, compare
            )

    def test_postgres_connect_requires_url(self):
        with pytest.raises(ValidationError):
            PostgresConnectCheck()

    def test_custom_requires_func(self):
        with pytest.raises(ValidationError):
            CustomCheck()


class TestLabConfigProperties:
    """Test computed properties on LabConfig."""

    def test_env_prefix_property(self):
        config = minimal_config()
        assert config.env_prefix == "TEST"

    def test_has_kafka_checks_true(self):
        config = minimal_config(
            checks=[
                {"type": "kafka_topic_exists", "kafka_addr_env": "X", "kafka_topic_env": "Y"}
            ]
        )
        assert config.has_kafka_checks is True

    def test_has_kafka_checks_false(self):
        config = minimal_config(checks=[])
        assert config.has_kafka_checks is False

    def test_has_kafka_checks_with_roundtrip(self):
        config = minimal_config(
            checks=[
                {"type": "kafka_roundtrip", "kafka_addr_env": "X", "kafka_topic_env": "Y"}
            ]
        )
        assert config.has_kafka_checks is True

    def test_has_kafka_checks_with_compare(self):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_compare",
                    "kafka_addr_env": "K",
                    "send_topic_env": "TI",
                    "send_file_jsonl": "in.jsonl",
                    "receive_topic_env": "TO",
                    "receive_expected_file_jsonl": "exp.jsonl",
                    "match_by": ["ts"],
                    "compare": ["val"],
                }
            ]
        )
        assert config.has_kafka_checks is True
        assert config.has_kafka_compare_checks is True

    def test_has_kafka_compare_checks_false(self):
        config = minimal_config(checks=[])
        assert config.has_kafka_compare_checks is False

    def test_has_postgres_checks_true(self):
        config = minimal_config(
            checks=[{"type": "postgres_connect", "postgres_url_env": "DB"}]
        )
        assert config.has_postgres_checks is True

    def test_has_postgres_checks_false(self):
        config = minimal_config(checks=[])
        assert config.has_postgres_checks is False

    def test_has_http_checks_true(self):
        config = minimal_config(
            checks=[{"type": "http_get", "url": "http://localhost"}]
        )
        assert config.has_http_checks is True

    def test_has_http_request_checks_true(self):
        config = minimal_config(
            checks=[{"type": "http_request", "url": "http://localhost"}]
        )
        assert config.has_http_request_checks is True

    def test_has_custom_checks_true(self):
        config = minimal_config(checks=[{"type": "custom", "func": "myFunc"}])
        assert config.has_custom_checks is True

    def test_has_forbidden_addr_checks_true(self):
        config = minimal_config(
            checks=[{"type": "forbidden_address", "env_var": "X", "forbidden": []}]
        )
        assert config.has_forbidden_addr_checks is True

    def test_has_wait_checks_true(self):
        config = minimal_config(checks=[{"type": "wait", "seconds": 5}])
        assert config.has_wait_checks is True

    def test_has_context_with_http(self):
        config = minimal_config(checks=[{"type": "http_get", "url": "http://localhost"}])
        assert config.has_context is True

    def test_has_context_with_kafka(self):
        config = minimal_config(
            checks=[
                {"type": "kafka_topic_exists", "kafka_addr_env": "K", "kafka_topic_env": "T"}
            ]
        )
        assert config.has_context is True

    def test_has_context_with_postgres(self):
        config = minimal_config(
            checks=[{"type": "postgres_connect", "postgres_url_env": "DB"}]
        )
        assert config.has_context is True

    def test_has_context_with_custom(self):
        config = minimal_config(checks=[{"type": "custom", "func": "f"}])
        assert config.has_context is True

    def test_has_context_without_checks(self):
        config = minimal_config(checks=[])
        assert config.has_context is False

    def test_has_flags_true(self):
        config = minimal_config(flags=[{"name": "debug", "type": "bool"}])
        assert config.has_flags is True

    def test_has_flags_false(self):
        config = minimal_config(flags=[])
        assert config.has_flags is False

    def test_has_masked_fields_true(self):
        config = minimal_config()
        config.confirm_display = [ConfirmField(name="TOKEN", masked=True)]
        assert config.has_masked_fields is True

    def test_has_masked_fields_false(self):
        config = minimal_config()
        config.confirm_display = [ConfirmField(name="STUDENT", masked=False)]
        assert config.has_masked_fields is False

    def test_has_param_checks_true(self):
        config = minimal_config(
            checks=[{"type": "param_equals", "env_var": "X", "expected": "y"}]
        )
        assert config.has_param_checks is True


class TestGetConfirmFields:
    """Test get_confirm_fields() normalization."""

    def test_normalizes_strings(self):
        config = minimal_config()
        config.confirm_display = ["STUDENT", "TOKEN"]  # type: ignore
        fields = config.get_confirm_fields()
        assert len(fields) == 2
        assert all(isinstance(f, ConfirmField) for f in fields)
        assert fields[0].name == "STUDENT"
        assert fields[0].masked is False

    def test_preserves_confirm_field_objects(self):
        config = minimal_config()
        config.confirm_display = [ConfirmField(name="TOKEN", masked=True)]
        fields = config.get_confirm_fields()
        assert fields[0].masked is True

    def test_mixed_strings_and_objects(self):
        config = minimal_config()
        config.confirm_display = [
            "STUDENT",  # type: ignore
            ConfirmField(name="TOKEN", masked=True),
        ]
        fields = config.get_confirm_fields()
        assert fields[0].name == "STUDENT"
        assert fields[0].masked is False
        assert fields[1].name == "TOKEN"
        assert fields[1].masked is True


class TestCustomCode:
    """Tests for CustomCode model."""

    def test_defaults(self):
        cc = CustomCode()
        assert cc.imports == []
        assert cc.types == ""
        assert cc.code == ""

    def test_with_imports(self):
        cc = CustomCode(imports=["encoding/json", "time"])
        assert len(cc.imports) == 2

    def test_with_code(self):
        cc = CustomCode(code="func myFunc() {}")
        assert "myFunc" in cc.code


def test_helper_templates_empty_when_no_helpers_needed():
    config = minimal_config(checks=[{"type": "wait", "seconds": 5}])
    assert config.required_helper_templates == []


def test_helper_templates_empty_when_no_checks():
    config = minimal_config(checks=[])
    assert config.required_helper_templates == []


def test_helper_templates_single_check_type():
    config = minimal_config(
        checks=[{"type": "http_get", "url": "http://localhost"}]
    )
    assert config.required_helper_templates == ["checks/http_get_helpers.go.j2"]


def test_helper_templates_deduplicates_same_check_type():
    config = minimal_config(
        checks=[
            {"type": "http_get", "url": "http://localhost/a"},
            {"type": "http_get", "url": "http://localhost/b"},
        ]
    )
    assert config.required_helper_templates == ["checks/http_get_helpers.go.j2"]


def test_helper_templates_shared_helpers_deduplicated():
    """http_get and http_get_random_path share the same helpers."""
    config = minimal_config(
        checks=[
            {"type": "http_get", "url": "http://localhost"},
            {"type": "http_get_random_path", "url": "http://localhost"},
        ]
    )
    assert config.required_helper_templates == ["checks/http_get_helpers.go.j2"]


def test_helper_templates_order_follows_check_order():
    config = minimal_config(
        checks=[
            {"type": "forbidden_address", "env_var": "X", "forbidden": ["y"]},
            {"type": "kafka_topic_exists", "kafka_addr_env": "K", "kafka_topic_env": "T"},
            {"type": "param_equals", "env_var": "M", "expected": "v"},
        ]
    )
    assert config.required_helper_templates == [
        "checks/forbidden_address_helpers.go.j2",
        "checks/kafka_topic_exists_helpers.go.j2",
        "checks/param_equals_helpers.go.j2",
    ]


def test_helper_templates_custom_and_wait_have_none():
    config = minimal_config(
        checks=[
            {"type": "custom", "func": "myFunc"},
            {"type": "wait", "seconds": 5},
        ]
    )
    assert config.required_helper_templates == []


def test_helper_templates_kafka_compare():
    config = minimal_config(
        checks=[
            {
                "type": "kafka_compare",
                "kafka_addr_env": "K",
                "send_topic_env": "TI",
                "send_file_jsonl": "in.jsonl",
                "receive_topic_env": "TO",
                "receive_expected_file_jsonl": "exp.jsonl",
                "match_by": ["ts"],
                "compare": ["val"],
            }
        ]
    )
    assert config.required_helper_templates == [
        "checks/kafka_compare_helpers.go.j2"
    ]


def test_helper_templates_multiple_kafka_types():
    config = minimal_config(
        checks=[
            {"type": "kafka_topic_exists", "kafka_addr_env": "K", "kafka_topic_env": "T"},
            {"type": "kafka_roundtrip", "kafka_addr_env": "K", "kafka_topic_env": "T"},
        ]
    )
    assert config.required_helper_templates == [
        "checks/kafka_topic_exists_helpers.go.j2",
        "checks/kafka_roundtrip_helpers.go.j2",
    ]


class TestGetFilteredImports:
    """Tests for get_filtered_imports() method."""

    def test_returns_all_when_no_overlap(self):
        config = minimal_config()
        config.custom_code.imports = ["regexp", "sort"]
        filtered = config.get_filtered_imports()
        assert filtered == ["regexp", "sort"]

    def test_filters_fmt_always(self):
        config = minimal_config()
        config.custom_code.imports = ["fmt", "regexp"]
        filtered = config.get_filtered_imports()
        assert "fmt" not in filtered
        assert "regexp" in filtered

    def test_filters_os_always(self):
        config = minimal_config()
        config.custom_code.imports = ["os", "regexp"]
        filtered = config.get_filtered_imports()
        assert "os" not in filtered
        assert "regexp" in filtered

    def test_filters_time_with_kafka_checks(self):
        config = minimal_config(
            checks=[
                {"type": "kafka_topic_exists", "kafka_addr_env": "K", "kafka_topic_env": "T"}
            ]
        )
        config.custom_code.imports = ["time", "regexp"]
        filtered = config.get_filtered_imports()
        assert "time" not in filtered
        assert "regexp" in filtered

    def test_filters_time_with_wait_checks(self):
        config = minimal_config(checks=[{"type": "wait", "seconds": 5}])
        config.custom_code.imports = ["time", "regexp"]
        filtered = config.get_filtered_imports()
        assert "time" not in filtered

    def test_keeps_time_without_time_checks(self):
        config = minimal_config(checks=[])
        config.custom_code.imports = ["time"]
        filtered = config.get_filtered_imports()
        assert "time" in filtered

    def test_filters_strings_with_forbidden_address(self):
        config = minimal_config(
            checks=[
                {"type": "forbidden_address", "env_var": "X", "forbidden": ["y"]}
            ]
        )
        config.custom_code.imports = ["strings", "regexp"]
        filtered = config.get_filtered_imports()
        assert "strings" not in filtered

    def test_filters_context_with_context_checks(self):
        config = minimal_config(
            checks=[{"type": "http_get", "url": "http://localhost"}]
        )
        config.custom_code.imports = ["context", "regexp"]
        filtered = config.get_filtered_imports()
        assert "context" not in filtered

    def test_filters_database_sql_with_postgres(self):
        config = minimal_config(
            checks=[{"type": "postgres_connect", "postgres_url_env": "DB"}]
        )
        config.custom_code.imports = ["database/sql", "regexp"]
        filtered = config.get_filtered_imports()
        assert "database/sql" not in filtered

    def test_filters_flag_with_flags(self):
        config = minimal_config(flags=[{"name": "debug", "type": "bool"}])
        config.custom_code.imports = ["flag", "regexp"]
        filtered = config.get_filtered_imports()
        assert "flag" not in filtered

    def test_filters_out_flag_always(self):
        config = minimal_config(flags=[])
        config.custom_code.imports = ["flag"]
        filtered = config.get_filtered_imports()
        assert "flag" not in filtered

    def test_empty_imports_returns_empty(self):
        config = minimal_config()
        config.custom_code.imports = []
        filtered = config.get_filtered_imports()
        assert filtered == []

    def test_preserves_third_party_imports(self):
        config = minimal_config(
            checks=[{"type": "kafka_topic_exists", "kafka_addr_env": "K", "kafka_topic_env": "T"}]
        )
        config.custom_code.imports = ["time", "github.com/some/package"]
        filtered = config.get_filtered_imports()
        assert "github.com/some/package" in filtered
        assert "time" not in filtered


def test_filters_trekker_infra_when_kafka_checks_present():
    config = minimal_config(
        checks=[{"type": "kafka_topic_exists", "kafka_addr_env": "K", "kafka_topic_env": "T"}]
    )
    config.custom_code.imports = ["trekker:infra", "regexp"]
    filtered = config.get_filtered_imports()
    assert "trekker:infra" not in filtered
    assert "regexp" in filtered


def test_filters_trekker_utils_when_masked_fields_present():
    config = minimal_config(
        confirm_display=[{"name": "SECRET", "masked": True}],
    )
    config.custom_code.imports = ["trekker:utils", "regexp"]
    filtered = config.get_filtered_imports()
    assert "trekker:utils" not in filtered
    assert "regexp" in filtered


def test_filters_always_imported_trekker_packages():
    config = minimal_config()
    config.custom_code.imports = ["trekker:analytics", "trekker:cli", "trekker:env", "trekker:logger", "regexp"]
    filtered = config.get_filtered_imports()
    assert filtered == ["regexp"]


def test_keeps_trekker_infra_without_kafka_checks():
    config = minimal_config()
    config.custom_code.imports = ["trekker:infra"]
    filtered = config.get_filtered_imports()
    assert "trekker:infra" in filtered


def test_keeps_trekker_utils_without_masked_fields():
    config = minimal_config()
    config.custom_code.imports = ["trekker:utils"]
    filtered = config.get_filtered_imports()
    assert "trekker:utils" in filtered
