"""Shared pytest fixtures for pytrekgen tests."""

import pytest
from pathlib import Path

from pytrekgen.config import (
    LabConfig,
    LabMeta,
    BuildConfig,
    EnvVar,
    ConfirmField,
    AnalyticsConfig,
    CustomCode,
)
from pytrekgen.generator import Generator


def minimal_config(
    checks: list | None = None,
    flags: list | None = None,
    required_env: list | None = None,
    **kwargs,
) -> LabConfig:
    """Create a minimal valid LabConfig for testing."""
    return LabConfig(
        lab=LabMeta(id="01", name="Test Lab", env_prefix="TEST"),
        build=BuildConfig(module="github.com/test/checker", go_version="1.23"),
        checks=checks or [],
        flags=flags or [],
        required_env=required_env or [],
        **kwargs,
    )


@pytest.fixture
def generator():
    """Create a Generator instance."""
    return Generator()


@pytest.fixture
def minimal_yaml_content():
    """Minimal valid YAML config content."""
    return """
lab:
  id: "01"
  name: "Test Lab"
  env_prefix: "TEST"
build:
  module: github.com/test/checker
"""


@pytest.fixture
def full_yaml_content():
    """Full YAML config with most features."""
    return """
lab:
  id: "02"
  name: "Full Test Lab"
  env_prefix: "FULL"

build:
  module: github.com/test/full-checker
  go_version: "1.23"

required_env:
  - name: STUDENT
    error: "Need student name"
  - name: TOKEN
    error: "Need token"

optional_env:
  - name: DEBUG
    default: "false"
    message: "debug mode off"

flags:
  - name: skip-db
    type: bool
    default: "false"
    description: "Skip database checks"

usage_header: |
  Test checker

usage_vars: |
  ${ENV_PREFIX}_STUDENT - your name

confirm_display:
  - STUDENT
  - name: TOKEN
    masked: true

analytics:
  skip_tls: true
  headers:
    x-lab: "02"

checks:
  - type: http_get
    url: "http://localhost:8080/health"
    expected_status: 200
    message_before: "Checking health"

success_message: "All checks passed!"
"""


@pytest.fixture
def examples_dir():
    """Path to examples directory."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def tmp_yaml(tmp_path):
    """Factory for creating temporary YAML files."""

    def _create(content: str, name: str = "config.yaml") -> Path:
        path = tmp_path / name
        path.write_text(content)
        return path

    return _create
