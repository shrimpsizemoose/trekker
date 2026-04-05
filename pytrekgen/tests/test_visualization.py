"""Tests for ASCII and HTML flow visualization."""

import subprocess
import sys

import pytest

from pytrekgen.generator import Generator

from conftest import minimal_config
from pytrekgen.config import (
    EnvVar,
    OptionalEnvVar,
    Flag,
    AnalyticsConfig,
    HTTPGetCheck,
    HTTPGetRandomPathCheck,
    ParamEqualsCheck,
    CustomCheck,
    FailureAction,
    SuccessAction,
    KafkaTopicExistsCheck,
    ClickhouseQuerySimpleCheck,
    PostgresConnectCheck,
)


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytrekgen.cli", *args],
        capture_output=True,
        text=True,
    )


@pytest.fixture
def gen():
    return Generator()


@pytest.fixture
def lab01_config(gen, examples_dir):
    return gen.load_config(examples_dir / "lab01.yaml")


@pytest.fixture
def rich_config():
    return minimal_config(
        required_env=[
            EnvVar(name="STUDENT", error="need student"),
            EnvVar(name="TOKEN", error="need token"),
        ],
        optional_env=[OptionalEnvVar(name="PORT", default="8000")],
        flags=[Flag(name="skip-db", description="skip database checks")],
        analytics=AnalyticsConfig(skip_tls=True, headers={"x-lab": "01"}),
        checks=[
            HTTPGetCheck(
                name="health",
                url="http://${IP}:${PORT}/health",
                expected_status=200,
                on_success=SuccessAction(event="010_health_ok"),
                on_failure=FailureAction(event="011_health_fail"),
            ),
            HTTPGetRandomPathCheck(
                name="random_404",
                url="http://${IP}:${PORT}",
                expected_status=404,
                on_success=SuccessAction(event="020_404_ok"),
            ),
            ParamEqualsCheck(
                name="param_check",
                env_var="MAGIC",
                expected="42",
                case_insensitive=True,
                skip_on_flag="skip-db",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# ASCII output
# ---------------------------------------------------------------------------


def test_ascii_contains_lab_name(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="ascii")
    assert "Lab 01" in out
    assert "Web Service Lab" in out


def test_ascii_lists_checks(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="ascii")
    assert "base_url_check" in out
    assert "random_404_check" in out
    assert "student_path_check" in out


def test_ascii_shows_env_vars(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="ascii")
    assert "STUDENT" in out
    assert "LAB01_EXTERNAL_IP" in out
    assert "LAB01_WEB_PORT" in out


def test_ascii_shows_check_types(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="ascii")
    assert "[http_get]" in out
    assert "[http_get_random_path]" in out
    assert "[param_equals]" in out


def test_ascii_shows_analytics_events(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="ascii")
    assert "010_health_ok" in out
    assert "011_health_fail" in out


def test_ascii_shows_skip_on_flag(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="ascii")
    assert "skip-db" in out


def test_ascii_shows_analytics_config(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="ascii")
    assert "skip_tls" in out


def test_ascii_empty_checks(gen):
    config = minimal_config(checks=[])
    out = gen.generate_flow(config, fmt="ascii")
    assert "Lab 01" in out
    assert "Success" in out


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------


def test_html_is_valid_structure(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "<!DOCTYPE html>" in out
    assert "<html" in out
    assert "</html>" in out
    assert "<head>" in out
    assert "<body>" in out


def test_html_has_mermaid(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "mermaid" in out
    assert "cdn.jsdelivr.net" in out


def test_html_mermaid_has_bookend_events(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "000_lab_start" in out
    assert "100_lab_finish" in out


def test_html_mermaid_fail_node_is_shared(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "FAIL{Fail}" in out
    assert "016_base_check_failed" in out


def test_html_lists_checks(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "base_url_check" in out
    assert "random_404_check" in out
    assert "student_path_check" in out


def test_html_contains_lab_info(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "Lab 01" in out
    assert "Web Service Lab" in out


def test_html_shows_env_vars(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="html")
    assert "NPL_STUDENT" in out
    assert "NPL_LAB01_EXTERNAL_IP" in out


def test_html_shows_check_details(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="html")
    assert "http_get" in out
    assert "param_equals" in out
    assert "010_health_ok" in out


def test_html_shows_analytics(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="html")
    assert "KANELBULLE" in out
    assert "x-lab" in out


def test_html_empty_checks(gen):
    config = minimal_config(checks=[])
    out = gen.generate_flow(config, fmt="html")
    assert "<html" in out
    assert "0 checks" in out


# ---------------------------------------------------------------------------
# Check detail filter
# ---------------------------------------------------------------------------


def test_check_detail_http_get():
    check = HTTPGetCheck(url="http://example.com", expected_status=200)
    detail = Generator._check_detail(check)
    assert "GET http://example.com" in detail
    assert "200" in detail


def test_check_detail_param_equals():
    check = ParamEqualsCheck(env_var="X", expected="y", case_insensitive=True)
    detail = Generator._check_detail(check)
    assert "X" in detail
    assert "case-insensitive" in detail


def test_check_detail_custom():
    check = CustomCheck(func="myFunc")
    detail = Generator._check_detail(check)
    assert "myFunc" in detail


def test_check_detail_kafka():
    check = KafkaTopicExistsCheck(kafka_addr_env="ADDR", kafka_topic_env="TOPIC")
    detail = Generator._check_detail(check)
    assert "TOPIC" in detail
    assert "ADDR" in detail


def test_check_detail_clickhouse_expected():
    check = ClickhouseQuerySimpleCheck(
        clickhouse_addr_env="CH", query="SELECT 1", expected="1"
    )
    detail = Generator._check_detail(check)
    assert "SELECT 1" in detail
    assert "'1'" in detail


def test_check_detail_clickhouse_rows():
    check = ClickhouseQuerySimpleCheck(
        clickhouse_addr_env="CH", query="DESCRIBE t", expected_rows=4
    )
    detail = Generator._check_detail(check)
    assert "4 rows" in detail


def test_check_detail_postgres():
    check = PostgresConnectCheck(postgres_url_env="DB_URL")
    detail = Generator._check_detail(check)
    assert "DB_URL" in detail


# ---------------------------------------------------------------------------
# Mermaid output
# ---------------------------------------------------------------------------


def test_mermaid_starts_and_ends_with_fence(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert out.startswith("```mermaid\n")
    assert out.rstrip().endswith("```")


def test_mermaid_has_graph_td(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert "graph TD" in out


def test_mermaid_has_bookend_events(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert "000_lab_start" in out
    assert "100_lab_finish" in out


def test_mermaid_contains_check_names(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert "base_url_check" in out
    assert "random_404_check" in out
    assert "student_path_check" in out


def test_mermaid_contains_check_types(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert "[http_get]" in out
    assert "[http_get_random_path]" in out


def test_mermaid_fail_node(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert "FAIL{Fail}" in out
    assert "016_base_check_failed" in out


def test_mermaid_success_events(gen, rich_config):
    out = gen.generate_flow(rich_config, fmt="mermaid")
    assert "010_health_ok" in out
    assert "011_health_fail" in out


def test_mermaid_empty_checks(gen):
    config = minimal_config(checks=[])
    out = gen.generate_flow(config, fmt="mermaid")
    assert out.startswith("```mermaid\n")
    assert "graph TD" in out


def test_mermaid_no_bold_html_in_labels(gen, lab01_config):
    out = gen.generate_flow(lab01_config, fmt="mermaid")
    assert "<b>" not in out
    assert "font-size:1.1em" not in out


# ---------------------------------------------------------------------------
# Integration: all example YAMLs render without errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["ascii", "html", "mermaid"])
@pytest.mark.parametrize(
    "yaml_file",
    ["lab00.yaml", "lab01.yaml", "lab02.yaml", "lab03.yaml", "clickhouse_simple_test.yaml"],
)
def test_example_renders(gen, examples_dir, yaml_file, fmt):
    config = gen.load_config(examples_dir / yaml_file)
    output = gen.generate_flow(config, fmt=fmt)
    assert len(output) > 100


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_cli_ascii(examples_dir):
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--ascii")
    assert result.returncode == 0
    assert "base_url_check" in result.stdout


def test_cli_html(examples_dir):
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--html")
    assert result.returncode == 0
    assert "<html" in result.stdout
    assert "mermaid" in result.stdout


def test_cli_html_to_file(examples_dir, tmp_path):
    out = tmp_path / "flow.html"
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--html", "-o", str(out))
    assert result.returncode == 0
    assert out.exists()
    content = out.read_text()
    assert "<html" in content


def test_cli_mermaid(examples_dir):
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--mermaid")
    assert result.returncode == 0
    assert result.stdout.startswith("```mermaid\n")
    assert "base_url_check" in result.stdout


def test_cli_mermaid_and_html_mutually_exclusive(examples_dir):
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--mermaid", "--html")
    assert result.returncode != 0


def test_cli_ascii_and_html_mutually_exclusive(examples_dir):
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--ascii", "--html")
    assert result.returncode != 0


def test_cli_viz_with_gomod_rejected(examples_dir):
    result = run_cli("-i", str(examples_dir / "lab01.yaml"), "--ascii", "--with-gomod")
    assert result.returncode != 0


def test_cli_codegen_still_works(examples_dir, tmp_path):
    out = tmp_path / "main.go"
    result = run_cli("-i", str(examples_dir / "lab00.yaml"), "-o", str(out))
    assert result.returncode == 0
    assert out.exists()
    assert "package main" in out.read_text()


def test_check_detail_clickhouse_compare():
    from pytrekgen.config import ClickhouseCompareCheck
    check = ClickhouseCompareCheck(
        kafka_addr_env="K", send_topic_env="T_IN", send_file_jsonl="input.jsonl",
        clickhouse_addr_env="CH",
        query="SELECT x FROM t FINAL WHERE run_id='%s' FORMAT JSONEachRow",
        expected_file_jsonl="expected.jsonl",
        match_by=["ts_start", "campaign_id"],
        compare=["revenue"],
    )
    detail = Generator._check_detail(check)
    assert "input.jsonl" in detail
    assert "T_IN" in detail
    assert "ts_start" in detail
    assert "expected.jsonl" in detail


def test_ascii_shows_clickhouse_compare(gen):
    from pytrekgen.config import ClickhouseCompareCheck
    config = minimal_config(checks=[
        ClickhouseCompareCheck(
            name="verify_ch",
            kafka_addr_env="K", send_topic_env="T_IN", send_file_jsonl="input.jsonl",
            clickhouse_addr_env="CH",
            query="SELECT x FROM t FINAL WHERE run_id='%s' FORMAT JSONEachRow",
            expected_file_jsonl="expected.jsonl",
            match_by=["ts"], compare=["revenue"],
        )
    ])
    out = gen.generate_flow(config, fmt="ascii")
    assert "[clickhouse_compare]" in out
    assert "verify_ch" in out
