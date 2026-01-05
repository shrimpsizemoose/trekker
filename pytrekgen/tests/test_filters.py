"""Tests for Jinja2 custom filters in generator.py."""

import pytest

from pytrekgen.generator import Generator


class TestQuoteFilter:
    """Tests for the quote filter."""

    def test_quotes_string(self):
        assert Generator._quote("hello") == '"hello"'

    def test_quotes_empty_string(self):
        assert Generator._quote("") == '""'

    def test_quotes_string_with_spaces(self):
        assert Generator._quote("hello world") == '"hello world"'


class TestTitleCaseFilter:
    """Tests for the title_case filter (kebab/snake to PascalCase)."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("send-only", "SendOnly"),
            ("send_only", "SendOnly"),
            ("small", "Small"),
            ("skip-db", "SkipDb"),
            ("my-long-flag-name", "MyLongFlagName"),
            ("UPPER_CASE", "UpperCase"),
            ("already", "Already"),
            ("a-b-c", "ABC"),
            ("", ""),
        ],
    )
    def test_title_case(self, input_str, expected):
        assert Generator._title_case(input_str) == expected


class TestLowerCamelFilter:
    """Tests for the lower_camel filter (UPPER_SNAKE to lowerCamelCase)."""

    @pytest.mark.parametrize(
        "input_str,expected",
        [
            ("KAFKA_BATCH_SIZE", "kafkaBatchSize"),
            ("PORT", "port"),
            ("DB_URL", "dbUrl"),
            ("STUDENT", "student"),
            ("A_B_C", "aBC"),
            ("SINGLE", "single"),
        ],
    )
    def test_lower_camel(self, input_str, expected):
        assert Generator._lower_camel(input_str) == expected


class TestUrlToFormatFilter:
    """Tests for the url_to_format filter (${VAR} to %s)."""

    def test_single_variable(self):
        result = Generator._url_to_format("http://${HOST}:8080")
        assert result == "http://%s:8080"

    def test_multiple_variables(self):
        result = Generator._url_to_format("http://${HOST}:${PORT}/api")
        assert result == "http://%s:%s/api"

    def test_no_variables(self):
        result = Generator._url_to_format("http://localhost:8080")
        assert result == "http://localhost:8080"

    def test_variable_at_end(self):
        result = Generator._url_to_format("http://host/${PATH}")
        assert result == "http://host/%s"


class TestExtractVarsFilter:
    """Tests for the extract_vars filter (extract variable names from URL)."""

    def test_extract_single(self):
        result = Generator._extract_vars("http://${HOST}")
        assert result == ["HOST"]

    def test_extract_multiple(self):
        result = Generator._extract_vars("${A}/${B}/${C}")
        assert result == ["A", "B", "C"]

    def test_extract_none(self):
        result = Generator._extract_vars("http://localhost")
        assert result == []

    def test_extract_complex_names(self):
        result = Generator._extract_vars("http://${API_HOST}:${API_PORT}")
        assert result == ["API_HOST", "API_PORT"]


class TestUrlFormatFilter:
    """Tests for the url_format filter (URL to fmt.Sprintf call)."""

    def test_no_variables_returns_quoted(self):
        result = Generator._url_format("http://localhost:8080", "NPL")
        assert result == '"http://localhost:8080"'

    def test_single_variable(self):
        result = Generator._url_format("http://${HOST}:8080", "NPL")
        assert "fmt.Sprintf" in result
        assert 'os.Getenv("NPL_HOST")' in result
        assert "%s" in result
        assert "http://%s:8080" in result

    def test_multiple_variables(self):
        result = Generator._url_format("http://${HOST}:${PORT}/api", "NPL")
        assert "fmt.Sprintf" in result
        assert 'os.Getenv("NPL_HOST")' in result
        assert 'os.Getenv("NPL_PORT")' in result
        assert result.count("%s") == 2

    def test_different_env_prefix(self):
        result = Generator._url_format("http://${HOST}", "MYAPP")
        assert 'os.Getenv("MYAPP_HOST")' in result

    def test_complex_url(self):
        result = Generator._url_format(
            "http://${HOST}:${PORT}/v1/${VERSION}/health", "API"
        )
        assert 'os.Getenv("API_HOST")' in result
        assert 'os.Getenv("API_PORT")' in result
        assert 'os.Getenv("API_VERSION")' in result


class TestPrefixedEnvFilter:
    """Tests for the prefixed_env filter."""

    def test_with_prefix(self):
        result = Generator._prefixed_env("TOKEN", "NPL")
        assert result == "NPL_TOKEN"

    def test_with_empty_prefix(self):
        result = Generator._prefixed_env("TOKEN", "")
        assert result == "TOKEN"

    def test_with_complex_name(self):
        result = Generator._prefixed_env("LAB04_AIRFLOW_URL", "")
        assert result == "LAB04_AIRFLOW_URL"

    def test_with_prefix_and_complex_name(self):
        result = Generator._prefixed_env("LAB04_AIRFLOW_URL", "NPL")
        assert result == "NPL_LAB04_AIRFLOW_URL"


class TestUrlFormatEmptyPrefix:
    """Tests for url_format with empty prefix."""

    def test_empty_prefix_single_var(self):
        result = Generator._url_format("http://${HOST}/api", "")
        assert 'os.Getenv("HOST")' in result
        assert 'os.Getenv("_HOST")' not in result

    def test_empty_prefix_multiple_vars(self):
        result = Generator._url_format("http://${HOST}:${PORT}/api", "")
        assert 'os.Getenv("HOST")' in result
        assert 'os.Getenv("PORT")' in result
        assert "_HOST" not in result
        assert "_PORT" not in result


class TestFiltersRegistration:
    """Test that filters are properly registered in the Jinja2 environment."""

    def test_filters_registered(self, generator):
        filters = generator.env.filters
        assert "quote" in filters
        assert "title_case" in filters
        assert "lower_camel" in filters
        assert "url_to_format" in filters
        assert "extract_vars" in filters
        assert "url_format" in filters
        assert "prefixed_env" in filters
