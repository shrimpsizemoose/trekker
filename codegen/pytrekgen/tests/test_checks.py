"""Tests for each check type's code generation."""

import pytest

from pytrekgen.generator import Generator

from conftest import minimal_config


@pytest.fixture
def generator():
    return Generator()


class TestParamEqualsCheck:
    """Tests for param_equals check generation."""

    def test_generates_check_function(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "production",
                }
            ]
        )
        code = generator.generate(config)
        assert "func checkParamMODE()" in code

    def test_compares_against_expected(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "production",
                }
            ]
        )
        code = generator.generate(config)
        assert 'param == "production"' in code

    def test_uses_env_prefix(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "prod",
                }
            ]
        )
        code = generator.generate(config)
        assert 'os.Getenv("TEST_MODE")' in code

    def test_case_insensitive(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "production",
                    "case_insensitive": True,
                }
            ]
        )
        code = generator.generate(config)
        assert "strings.ToLower" in code

    def test_calls_check_function_in_main(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "prod",
                }
            ]
        )
        code = generator.generate(config)
        assert "checkParamMODE()" in code

    def test_failure_event(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "prod",
                    "on_failure": {"event": "wrong_mode", "message": "Invalid mode"},
                }
            ]
        )
        code = generator.generate(config)
        assert '"wrong_mode"' in code
        assert "Invalid mode" in code


class TestForbiddenAddressCheck:
    """Tests for forbidden_address check generation."""

    def test_generates_helper_function(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "forbidden_address",
                    "env_var": "KAFKA_ADDR",
                    "forbidden": ["10.0.0.1"],
                }
            ]
        )
        code = generator.generate(config)
        assert "func checkForbiddenAddress(" in code

    def test_generates_check_call(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "forbidden_address",
                    "env_var": "KAFKA_ADDR",
                    "forbidden": ["10.0.0.1", "bad.host.com"],
                }
            ]
        )
        code = generator.generate(config)
        assert "checkForbiddenAddress(" in code

    def test_includes_forbidden_list(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "forbidden_address",
                    "env_var": "KAFKA",
                    "forbidden": ["10.0.0.1", "bad.host.com"],
                }
            ]
        )
        code = generator.generate(config)
        assert '"10.0.0.1"' in code
        assert '"bad.host.com"' in code

    def test_uses_env_prefix(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "forbidden_address",
                    "env_var": "KAFKA",
                    "forbidden": ["x"],
                }
            ]
        )
        code = generator.generate(config)
        assert '"TEST_KAFKA"' in code

    def test_failure_event_and_message(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "forbidden_address",
                    "env_var": "KAFKA",
                    "forbidden": ["x"],
                    "on_failure": {
                        "event": "cheater_detected",
                        "message": "Use your own Kafka!",
                    },
                }
            ]
        )
        code = generator.generate(config)
        assert '"cheater_detected"' in code
        assert "Use your own Kafka!" in code


class TestWaitCheck:
    """Tests for wait check generation."""

    def test_generates_time_sleep(self, generator):
        config = minimal_config(checks=[{"type": "wait", "seconds": 5}])
        code = generator.generate(config)
        assert "time.Sleep" in code

    def test_uses_correct_duration(self, generator):
        config = minimal_config(checks=[{"type": "wait", "seconds": 10}])
        code = generator.generate(config)
        assert "10" in code
        assert "time.Second" in code


class TestHTTPGetCheck:
    """Tests for http_get check generation."""

    def test_generates_http_check_call(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "http_get",
                    "url": "http://localhost:8080/health",
                    "expected_status": 200,
                }
            ]
        )
        code = generator.generate(config)
        assert "httpCheck(rootCtx" in code

    def test_uses_literal_url(self, generator):
        config = minimal_config(
            checks=[{"type": "http_get", "url": "http://localhost:8080/health"}]
        )
        code = generator.generate(config)
        assert '"http://localhost:8080/health"' in code

    def test_url_with_env_vars(self, generator):
        config = minimal_config(
            checks=[{"type": "http_get", "url": "http://${HOST}:${PORT}/health"}]
        )
        code = generator.generate(config)
        assert "fmt.Sprintf" in code
        assert 'os.Getenv("TEST_HOST")' in code
        assert 'os.Getenv("TEST_PORT")' in code

    def test_expected_status(self, generator):
        config = minimal_config(
            checks=[
                {"type": "http_get", "url": "http://localhost", "expected_status": 201}
            ]
        )
        code = generator.generate(config)
        assert "201" in code

    def test_message_before(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "http_get",
                    "url": "http://localhost",
                    "message_before": "Checking health endpoint",
                }
            ]
        )
        code = generator.generate(config)
        assert "Checking health endpoint" in code

    def test_generates_helper_function(self, generator):
        config = minimal_config(
            checks=[{"type": "http_get", "url": "http://localhost"}]
        )
        code = generator.generate(config)
        assert "func httpCheck(" in code


class TestHTTPGetRandomPathCheck:
    """Tests for http_get_random_path check generation."""

    def test_uses_get_random_path(self, generator):
        config = minimal_config(
            checks=[{"type": "http_get_random_path", "url": "http://localhost"}]
        )
        code = generator.generate(config)
        assert "getRandomPath(" in code

    def test_generates_random_path_function(self, generator):
        config = minimal_config(
            checks=[{"type": "http_get_random_path", "url": "http://localhost"}]
        )
        code = generator.generate(config)
        assert "func getRandomPath(" in code


class TestKafkaTopicExistsCheck:
    """Tests for kafka_topic_exists check generation."""

    def test_generates_check_call(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_topic_exists",
                    "kafka_addr_env": "KAFKA_ADDR",
                    "kafka_topic_env": "KAFKA_TOPIC",
                }
            ]
        )
        code = generator.generate(config)
        assert "checkKafkaTopicExists(" in code

    def test_uses_env_prefix(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_topic_exists",
                    "kafka_addr_env": "KAFKA_ADDR",
                    "kafka_topic_env": "KAFKA_TOPIC",
                }
            ]
        )
        code = generator.generate(config)
        assert 'os.Getenv("TEST_KAFKA_ADDR")' in code
        assert 'os.Getenv("TEST_KAFKA_TOPIC")' in code

    def test_on_connect_event(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_topic_exists",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                    "on_connect": "kafka_connected",
                }
            ]
        )
        code = generator.generate(config)
        assert '"kafka_connected"' in code

    def test_on_partitions_read_event(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_topic_exists",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                    "on_partitions_read": "partitions_read",
                }
            ]
        )
        code = generator.generate(config)
        assert '"partitions_read"' in code

    def test_generates_helper_function(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_topic_exists",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                }
            ]
        )
        code = generator.generate(config)
        assert "func checkKafkaTopicExists(" in code


class TestKafkaRoundtripCheck:
    """Tests for kafka_roundtrip check generation."""

    def test_generates_roundtrip_call(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_roundtrip",
                    "kafka_addr_env": "KAFKA",
                    "kafka_topic_env": "TOPIC",
                }
            ]
        )
        code = generator.generate(config)
        assert "kafkaRoundtrip(" in code

    def test_message_count(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_roundtrip",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                    "message_count": 10,
                }
            ]
        )
        code = generator.generate(config)
        # Should appear as an argument
        assert "10," in code

    def test_wait_seconds(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_roundtrip",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                    "wait_seconds": 5,
                }
            ]
        )
        code = generator.generate(config)
        assert "5," in code

    def test_message_generator(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_roundtrip",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                    "message_generator": "sequential",
                }
            ]
        )
        code = generator.generate(config)
        assert '"sequential"' in code

    def test_generates_helper_function(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_roundtrip",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                }
            ]
        )
        code = generator.generate(config)
        assert "func kafkaRoundtrip(" in code


class TestPostgresConnectCheck:
    """Tests for postgres_connect check generation."""

    def test_generates_sql_open(self, generator):
        config = minimal_config(
            checks=[{"type": "postgres_connect", "postgres_url_env": "DB_URL"}]
        )
        code = generator.generate(config)
        assert "sql.Open" in code
        assert '"postgres"' in code

    def test_uses_env_prefix(self, generator):
        config = minimal_config(
            checks=[{"type": "postgres_connect", "postgres_url_env": "DB_URL"}]
        )
        code = generator.generate(config)
        assert 'os.Getenv("TEST_DB_URL")' in code

    def test_on_connect_event(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "postgres_connect",
                    "postgres_url_env": "DB",
                    "on_connect": "db_connected",
                }
            ]
        )
        code = generator.generate(config)
        assert '"db_connected"' in code


class TestPostgresTablesEmptyCheck:
    """Tests for postgres_tables_empty check generation."""

    def test_generates_check_call(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "postgres_connect",
                    "postgres_url_env": "DB",
                },
                {
                    "type": "postgres_tables_empty",
                    "postgres_url_env": "DB",
                    "tables": ["users", "orders"],
                },
            ]
        )
        code = generator.generate(config)
        assert "checkPostgresTablesEmpty(" in code

    def test_includes_table_names(self, generator):
        config = minimal_config(
            checks=[
                {"type": "postgres_connect", "postgres_url_env": "DB"},
                {
                    "type": "postgres_tables_empty",
                    "postgres_url_env": "DB",
                    "tables": ["users", "orders"],
                },
            ]
        )
        code = generator.generate(config)
        assert '"users"' in code
        assert '"orders"' in code

    def test_generates_helper_function(self, generator):
        config = minimal_config(
            checks=[
                {"type": "postgres_connect", "postgres_url_env": "DB"},
                {
                    "type": "postgres_tables_empty",
                    "postgres_url_env": "DB",
                    "tables": ["t"],
                },
            ]
        )
        code = generator.generate(config)
        assert "func checkPostgresTablesEmpty(" in code


class TestCustomCheck:
    """Tests for custom check generation."""

    def test_generates_function_call(self, generator):
        config = minimal_config(checks=[{"type": "custom", "func": "myValidator"}])
        code = generator.generate(config)
        assert "myValidator(rootCtx)" in code

    def test_handles_error(self, generator):
        config = minimal_config(checks=[{"type": "custom", "func": "myValidator"}])
        code = generator.generate(config)
        assert "if err := myValidator(rootCtx); err != nil" in code


class TestSkipOnFlag:
    """Tests for skip_on_flag conditional execution."""

    def test_wraps_in_flag_condition(self, generator):
        config = minimal_config(
            flags=[{"name": "skip-db", "type": "bool", "default": "false"}],
            checks=[
                {
                    "type": "postgres_connect",
                    "postgres_url_env": "DB",
                    "skip_on_flag": "skip-db",
                }
            ],
        )
        code = generator.generate(config)
        assert "if !*flagSkipDb {" in code

    def test_multiple_checks_with_skip(self, generator):
        config = minimal_config(
            flags=[{"name": "fast", "type": "bool", "default": "false"}],
            checks=[
                {"type": "http_get", "url": "http://localhost/slow", "skip_on_flag": "fast"},
                {"type": "http_get", "url": "http://localhost/always"},
            ],
        )
        code = generator.generate(config)
        assert "if !*flagFast {" in code
        # The second check should not be wrapped
        assert code.count("if !*flagFast {") == 1


class TestOnSuccessEvent:
    """Tests for on_success event generation."""

    def test_kafka_topic_exists_success_event(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "kafka_topic_exists",
                    "kafka_addr_env": "K",
                    "kafka_topic_env": "T",
                    "on_success": {"event": "topic_found"},
                }
            ]
        )
        code = generator.generate(config)
        assert 'tracker.Ping("topic_found"' in code

    def test_param_equals_success_event(self, generator):
        config = minimal_config(
            checks=[
                {
                    "type": "param_equals",
                    "env_var": "MODE",
                    "expected": "prod",
                    "on_success": {"event": "mode_ok"},
                }
            ]
        )
        code = generator.generate(config)
        assert 'tracker.Ping("mode_ok"' in code
