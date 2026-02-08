#!/usr/bin/env python3
"""Generate documentation from source code (Pydantic models)."""

import inspect
import re
from pathlib import Path
from typing import get_args, get_origin

from pytrekgen.config import (
    Check,
    CustomCheck,
    ForbiddenAddressCheck,
    HTTPBatchCheck,
    HTTPBatchRepeatCheck,
    HTTPGetCheck,
    HTTPGetRandomPathCheck,
    HTTPRequestCheck,
    KafkaRoundtripCheck,
    KafkaSendFileCheck,
    KafkaTopicExistsCheck,
    LabConfig,
    ParamEqualsCheck,
    PostgresConnectCheck,
    PostgresTablesEmptyCheck,
    WaitCheck,
)

# All check types (explicit list to avoid Annotated/Union complexity)
CHECK_TYPES = [
    ParamEqualsCheck,
    ForbiddenAddressCheck,
    WaitCheck,
    HTTPGetCheck,
    HTTPGetRandomPathCheck,
    HTTPRequestCheck,
    HTTPBatchCheck,
    HTTPBatchRepeatCheck,
    KafkaTopicExistsCheck,
    KafkaRoundtripCheck,
    KafkaSendFileCheck,
    PostgresConnectCheck,
    PostgresTablesEmptyCheck,
    CustomCheck,
]

# Output directory (docs/ at project root for MkDocs)
DOCS_DIR = Path(__file__).parent.parent / "docs"


def get_model_fields(model_class) -> list[dict]:
    """Extract field info from a Pydantic model."""
    fields = []
    for name, field in model_class.model_fields.items():
        # Skip 'type' discriminator field
        if name == "type":
            continue

        field_info = {
            "name": name,
            "type": str(field.annotation)
            .replace("typing.", "")
            .replace("<class '", "")
            .replace("'>", ""),
            "required": field.is_required(),
            "default": field.default if not field.is_required() else None,
            "description": field.description or "",
        }
        fields.append(field_info)
    return fields


def generate_check_types_md() -> str:
    lines = [
        "# Check Types Reference",
        "",
        "This page lists all available check types for your YAML configuration.",
        "",
        "---",
        "",
    ]

    for check_type in CHECK_TYPES:
        doc = inspect.getdoc(check_type) or "No description available."
        type_name = check_type.model_fields["type"].default

        lines.extend(
            [
                f"## `{type_name}`",
                "",
                doc,
                "",
                "### Fields",
                "",
                "| Field | Type | Required | Default | Description |",
                "|-------|------|----------|---------|-------------|",
            ]
        )

        for field in get_model_fields(check_type):
            req = "Yes" if field["required"] else "No"
            default = f"`{field['default']}`" if field["default"] is not None else "—"
            desc = field["description"] or "—"
            lines.append(
                f"| `{field['name']}` | `{field['type']}` | {req} | {default} | {desc} |"
            )

        lines.extend(["", "---", ""])

    return "\n".join(lines)


def generate_config_schema_md() -> str:
    lines = [
        "# Configuration Schema",
        "",
        "Complete reference for the YAML configuration file structure.",
        "",
        "## Top-Level Structure",
        "",
        "```yaml",
        "lab:",
        '  id: "01"',
        '  name: "My Lab"',
        '  env_prefix: "NPL"',
        "",
        "# ... other sections",
        "```",
        "",
        "## Sections",
        "",
    ]

    for name, field in LabConfig.model_fields.items():
        lines.extend(
            [
                f"### `{name}`",
                "",
                f"**Type:** `{field.annotation}`",
                "",
                field.description or "",
                "",
            ]
        )

    return "\n".join(lines)


def generate_index_md() -> str:
    """Generate main index.md."""
    return """# Pytrekgen Documentation

**Pytrekgen** is a Python-based code generator that creates
Go checkers for lab assignments
from declarative YAML configurations.

## Quick Start

```bash
# Install
cd pytrekgen
uv sync

# Generate a checker
uv run pytrekgen -i examples/lab02.yaml -o build/main.go --with-gomod
```

## What's Inside

- [Check Types Reference](check-types.md) - All available check types
- [Configuration Schema](config-schema.md) - Complete YAML reference
- [Examples](examples.md) - Real-world configuration examples

## Checker Example

**config.yaml:**
```yaml
lab:
  id: "02"
  name: "Kafka Pipeline"
  env_prefix: "NPL"

build:
  module: github.com/example/my-checker
  go_version: "1.23"

required_env:
  - name: HOST
    error: "Target host is required"
  - name: STUDENT_TOKEN
    error: "Token is required"

optional_env:
  - name: PORT
    default: "8080"
    message: "using default port"

analytics:
  offline: true  # Print events to console instead of sending

checks:
  - type: http_get
    url: "http://${HOST}:${PORT}/health"
    expected_status: 200
    on_success:
      event: "health_check_passed"
```

**Generate and run:**
```bash
# 1. Generate Go checker from YAML
cd pytrekgen
uv run pytrekgen -i config.yaml -o ../build/main.go --with-gomod

# 2. Build the checker
cd ../build
go mod tidy
go build -o checker .

# 3. Run with environment variables
NPL_HOST=localhost NPL_STUDENT_TOKEN=secret ./checker
```
"""


def main() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    files = {
        "index.md": generate_index_md(),
        "check-types.md": generate_check_types_md(),
        "config-schema.md": generate_config_schema_md(),
    }

    for filename, content in files.items():
        filepath = DOCS_DIR / filename
        filepath.write_text(content)
        print(f"Generated: {filepath}")

    print(f"\nDocumentation generated in: {DOCS_DIR}")


if __name__ == "__main__":
    main()
