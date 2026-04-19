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


class TestRedisConnectCheck:
    """Tests for redis_connect generation."""

    def test_generates_ping(self, generator):
        config = minimal_config(
            checks=[{"type": "redis_connect", "addr_env": "REDIS"}]
        )
        code = generator.generate(config)
        assert "redisCli.Ping" in code

    def test_uses_prefixed_env_vars(self, generator):
        config = minimal_config(
            checks=[{"type": "redis_connect", "addr_env": "REDIS", "url_env": "REDIS_URL"}]
        )
        code = generator.generate(config)
        assert '"TEST_REDIS"' in code
        assert '"TEST_REDIS_URL"' in code

    def test_includes_shared_helper(self, generator):
        config = minimal_config(
            checks=[{"type": "redis_connect", "addr_env": "REDIS"}]
        )
        code = generator.generate(config)
        assert "func redisConnect(" in code


class TestRedisSMembersCheck:
    """Tests for redis_smembers generation."""

    def test_generates_check_call(self, generator):
        config = minimal_config(
            embedded_data=[{"name": "answersFavDay1", "file": "answers_fav_day1.json"}],
            checks=[
                {
                    "type": "redis_smembers",
                    "addr_env": "REDIS",
                    "answers_file": "answers_fav_day1.json",
                }
            ],
        )
        code = generator.generate(config)
        assert "redisSMembersCheck(" in code
        assert "answersFavDay1Data" in code

    def test_includes_smembers_logic_and_sort(self, generator):
        config = minimal_config(
            embedded_data=[{"name": "answers", "file": "answers.json"}],
            checks=[
                {
                    "type": "redis_smembers",
                    "addr_env": "REDIS",
                    "answers_file": "answers.json",
                }
            ],
        )
        code = generator.generate(config)
        assert ".SMembers(" in code
        assert "sort.Strings(actual)" in code
        assert "sort.Strings(expected)" in code


class TestRedisZRangeCheck:
    """Tests for redis_zrange generation."""

    def test_generates_check_call(self, generator):
        config = minimal_config(
            embedded_data=[{"name": "answersFavDay1", "file": "answers_fav_day1.json"}],
            checks=[
                {
                    "type": "redis_zrange",
                    "addr_env": "REDIS",
                    "answers_file": "answers_fav_day1.json",
                }
            ],
        )
        code = generator.generate(config)
        assert "redisZRangeCheck(" in code
        assert "answersFavDay1Data" in code

    def test_includes_zrange_logic_without_sorting(self, generator):
        config = minimal_config(
            embedded_data=[{"name": "answers", "file": "answers.json"}],
            checks=[
                {
                    "type": "redis_zrange",
                    "addr_env": "REDIS",
                    "answers_file": "answers.json",
                }
            ],
        )
        code = generator.generate(config)
        assert ".ZRange(" in code
        assert "sort.Strings(actual)" not in code


def _kafka_compare_check(**overrides):
    """Build a minimal kafka_compare check dict with optional overrides."""
    base = {
        "type": "kafka_compare",
        "kafka_addr_env": "LAB03_KAFKA",
        "send_topic_env": "TOPIC_IN",
        "send_file_jsonl": "input.jsonl",
        "receive_topic_env": "TOPIC_OUT",
        "receive_expected_file_jsonl": "expected.jsonl",
        "match_by": ["start_ts", "end_ts"],
        "compare": ["revenue", "visitors"],
    }
    base.update(overrides)
    return base


def _kafka_compare_code(generator, **overrides):
    config = minimal_config(checks=[_kafka_compare_check(**overrides)])
    return generator.generate(config)


def test_kafka_compare_generates_helper_function(generator):
    code = _kafka_compare_code(generator)
    assert "func kafkaCompare(" in code


def test_kafka_compare_generates_check_call(generator):
    code = _kafka_compare_code(generator)
    assert "kafkaCompare(" in code
    assert "rootCtx" in code


def test_kafka_compare_uses_env_prefix(generator):
    code = _kafka_compare_code(generator)
    assert 'os.Getenv("TEST_LAB03_KAFKA")' in code
    assert 'os.Getenv("TEST_TOPIC_IN")' in code
    assert 'os.Getenv("TEST_TOPIC_OUT")' in code


def test_kafka_compare_match_by_fields(generator):
    code = _kafka_compare_code(generator)
    assert '"start_ts"' in code
    assert '"end_ts"' in code


def test_kafka_compare_compare_fields(generator):
    code = _kafka_compare_code(generator)
    assert '"revenue"' in code
    assert '"visitors"' in code


def test_kafka_compare_float_tolerance(generator):
    code = _kafka_compare_code(generator, float_tolerance=0.01)
    assert "0.01" in code


def test_kafka_compare_message_before(generator):
    code = _kafka_compare_code(generator, message_before="Отправляю данные...")
    assert "Отправляю данные..." in code


def test_kafka_compare_message_success(generator):
    code = _kafka_compare_code(generator, message_success="Все совпало!")
    assert "Все совпало!" in code
    assert "logger.Victory" in code


def test_kafka_compare_failure_event(generator):
    code = _kafka_compare_code(
        generator,
        on_failure={"event": "compare_failed", "message": "Не совпало"},
    )
    assert '"compare_failed"' in code
    assert "Не совпало" in code


def test_kafka_compare_success_event(generator):
    code = _kafka_compare_code(generator, on_success={"event": "compare_ok"})
    assert 'tracker.Ping("compare_ok"' in code


def test_kafka_compare_embedded_data_references(generator):
    code = _kafka_compare_code(generator)
    assert "inputData" in code
    assert "expectedData" in code


def test_kafka_compare_wait_and_timeout(generator):
    code = _kafka_compare_code(
        generator,
        receive_wait_before_seconds=15,
        receive_timeout_seconds=60,
    )
    assert "15 * time.Second" in code
    assert "60 * time.Second" in code


def test_kafka_compare_build_key_helper(generator):
    code = _kafka_compare_code(generator)
    assert "func kafkaCompareBuildKey(" in code


def test_kafka_compare_to_float_helper(generator):
    code = _kafka_compare_code(generator)
    assert "func kafkaCompareToFloat(" in code


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


def test_check_description_appears_in_generated_code(generator):
    config = minimal_config(
        checks=[
            {
                "type": "http_get",
                "url": "http://localhost",
                "name": "health",
                "description": "Проверяет health endpoint",
            }
        ]
    )
    code = generator.generate(config)
    assert "Проверяет health endpoint" in code


def test_check_no_description_line_when_empty(generator):
    config = minimal_config(
        checks=[
            {
                "type": "http_get",
                "url": "http://localhost",
                "name": "health",
            }
        ]
    )
    code = generator.generate(config)
    assert "[http_get] health" in code
    # Should not have an indented description line
    lines = code.splitlines()
    for i, line in enumerate(lines):
        if "[http_get] health" in line:
            # Next non-empty template line should not be an indented description
            if i + 1 < len(lines):
                assert '     "' not in lines[i + 1] or "Println" not in lines[i + 1]
            break


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


# ── kafka_to_clickhouse ────────────────────────────────────────────────


def _ch_compare_check(**overrides):
    base = {
        "type": "kafka_to_clickhouse",
        "kafka_addr_env": "LAB03S_KAFKA",
        "send_topic_env": "TOPIC_IN",
        "send_file_jsonl": "inputEvents.jsonl",
        "receive_wait_before_seconds": 30,
        "clickhouse_addr_env": "CH_ADDR",
        "query": "SELECT start_ts, revenue FROM t FINAL WHERE run_id = '%s' FORMAT JSONEachRow",
        "expected_file_jsonl": "expectedOutput.jsonl",
        "match_by": ["start_ts"],
        "compare": ["revenue"],
    }
    base.update(overrides)
    return base


def _ch_compare_code(generator, **overrides):
    config = minimal_config(checks=[_ch_compare_check(**overrides)])
    return generator.generate(config)


def test_ch_compare_generates_helper(generator):
    assert "func kafkaToClickhouse(" in _ch_compare_code(generator)


def test_ch_compare_call_site(generator):
    code = _ch_compare_code(generator)
    assert "kafkaToClickhouse(" in code
    assert "rootCtx" in code


def test_ch_compare_env_prefix_kafka(generator):
    code = _ch_compare_code(generator)
    assert 'os.Getenv("TEST_LAB03S_KAFKA")' in code


def test_ch_compare_env_prefix_ch(generator):
    code = _ch_compare_code(generator)
    assert 'os.Getenv("TEST_CH_ADDR")' in code


def test_ch_compare_empty_creds_when_not_set(generator):
    code = _ch_compare_code(generator)
    assert '"",' in code


def test_ch_compare_with_creds(generator):
    code = _ch_compare_code(generator, clickhouse_user_env="CH_USER", clickhouse_pass_env="CH_PASS")
    assert 'os.Getenv("TEST_CH_USER")' in code
    assert 'os.Getenv("TEST_CH_PASS")' in code


def test_ch_compare_data_references(generator):
    code = _ch_compare_code(generator)
    assert "inputEventsData" in code
    assert "expectedOutputData" in code


def test_ch_compare_match_and_compare_fields(generator):
    code = _ch_compare_code(generator, match_by=["ts", "cid"], compare=["rev", "aov"])
    assert '"ts"' in code
    assert '"cid"' in code
    assert '"rev"' in code
    assert '"aov"' in code


def test_ch_compare_float_tolerance(generator):
    assert "0.01" in _ch_compare_code(generator, float_tolerance=0.01)


def test_ch_compare_wait_seconds(generator):
    assert "60 * time.Second" in _ch_compare_code(generator, receive_wait_before_seconds=60)


def test_ch_compare_message_before(generator):
    assert "Проверяю..." in _ch_compare_code(generator, message_before="Проверяю...")


def test_ch_compare_message_success(generator):
    code = _ch_compare_code(generator, message_success="Ок!")
    assert "Ок!" in code
    assert "logger.Victory" in code


def test_ch_compare_failure_event(generator):
    code = _ch_compare_code(generator, on_failure={"event": "fail_ev", "message": "Не совпало"})
    assert '"fail_ev"' in code
    assert "Не совпало" in code


def test_ch_compare_success_event(generator):
    assert 'tracker.Ping("ok_ev"' in _ch_compare_code(generator, on_success={"event": "ok_ev"})


def test_ch_compare_query_in_code(generator):
    code = _ch_compare_code(generator)
    assert "FINAL" in code
    assert "FORMAT JSONEachRow" in code


def test_ch_compare_infra_import(generator):
    assert '"github.com/shrimpsizemoose/trekker/infra"' in _ch_compare_code(generator)


def test_ch_compare_no_direct_kafka_import(generator):
    code = _ch_compare_code(generator)
    assert 'kafka "github.com/segmentio/kafka-go"' not in code


def test_ch_compare_requires_context(generator):
    assert "rootCtx, rootCancel" in _ch_compare_code(generator)


def test_ch_compare_self_contained_helpers(generator):
    code = _ch_compare_code(generator)
    assert "func chCompareBuildKey(" in code
    assert "func chFmtNum(" in code
    assert "func chCompareToFloat(" in code


def test_ch_compare_no_kafka_compare_helpers_conflict(generator):
    """Both check types together should not produce duplicate function names."""
    config = minimal_config(checks=[
        _ch_compare_check(),
        {
            "type": "kafka_compare",
            "kafka_addr_env": "KAFKA",
            "send_topic_env": "T_IN",
            "send_file_jsonl": "input.jsonl",
            "receive_topic_env": "T_OUT",
            "receive_expected_file_jsonl": "expected.jsonl",
            "match_by": ["id"],
            "compare": ["val"],
        }
    ])
    code = generator.generate(config)
    # chCompare* and kafkaCompare* helpers should both exist without collision
    assert "func chCompareBuildKey(" in code
    assert "func kafkaCompareBuildKey(" in code
