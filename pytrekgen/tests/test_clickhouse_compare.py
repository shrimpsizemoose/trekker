"""Tests for clickhouse_compare, including compiled generated checkers."""

import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from conftest import minimal_config
from pytrekgen.config import ClickhouseCompareCheck, CHECK_TYPE_STDLIB_IMPORTS
from pytrekgen.generator import Generator


def comparison(**overrides):
    result = dict(type="clickhouse_compare", clickhouse_addr_env="CH_ADDR",
                  query="SELECT {dataset:String}", expected_file_env="EXPECTED",
                  match_by=["id"], columns={"id": "string", "value": "decimal"})
    result.update(overrides)
    return result


@pytest.mark.parametrize("overrides", [
    {"expected_file_env": ""},
    {"expected_file_jsonl": "rows.jsonl"},
    {"match_by": []}, {"match_by": ["missing"]}, {"match_by": ["id", "id"]},
    {"columns": {"id": "float"}}, {"columns": {"": "string"}},
    {"timeout_seconds": -1}, {"request_timeout_seconds": 0}, {"poll_interval_ms": 0},
    {"params": {"bad-name": "x"}},
])
def test_invalid_config(overrides):
    with pytest.raises(ValidationError):
        ClickhouseCompareCheck.model_validate(comparison(**overrides))


def test_requires_embedded_reference():
    with pytest.raises(ValidationError, match="listed in embedded_data"):
        minimal_config(checks=[comparison(expected_file_env="", expected_file_jsonl="rows.jsonl")])


def test_generation_and_mixed_helpers():
    config = minimal_config(checks=[comparison(params={"dataset": "${DATASET}"}),
        {"type": "clickhouse_query_simple", "clickhouse_addr_env": "CH", "query": "SELECT 1", "expected": "1"}])
    code = Generator().generate(config)
    assert config.has_context
    assert "func clickhouseCompare(" in code
    assert 'os.Getenv("TEST_EXPECTED")' in code
    assert '"param_"+name' in code
    assert 'os.LookupEnv(name)' in code
    assert "func clickhouseQuerySimple(" in code
    assert "infra.NewKafkaWriter" not in code


@pytest.mark.skipif(shutil.which("go") is None, reason="Go is required")
def test_helper_behavior(tmp_path):
    generator = Generator()
    helper = generator.env.get_template("checks/clickhouse_compare_helpers.go.j2").render()
    imports = (CHECK_TYPE_STDLIB_IMPORTS["clickhouse_compare"] - {"os/signal"}) | {"fmt"}
    (tmp_path / "go.mod").write_text("module comparetest\n\ngo 1.23\n")
    (tmp_path / "compare.go").write_text('package main\nimport (\n' + "\n".join(f'"{s}"' for s in sorted(imports)) + '\n)\n' + helper)
    shutil.copy(Path(__file__).parent / "go/clickhouse_compare_test.go.txt", tmp_path / "compare_test.go")
    result = subprocess.run(["go", "test", "-race", "-count=1", "-timeout=30s", "./..."], cwd=tmp_path,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(shutil.which("go") is None, reason="Go is required")
def test_generated_block_with_runtime_and_embedded_data(tmp_path):
    import json
    import os
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlsplit

    seen = []
    value = {"id": "a", "value": "833.670"}
    query = "SELECT {dataset:String} /* quotes: ` \" \\ and Unicode 🦌 */\n"

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen.append((self.rfile.read(int(self.headers["Content-Length"])).decode(),
                         parse_qs(urlsplit(self.path).query, keep_blank_values=True)))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(value).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        check = comparison(
            query=query,
            params={
                "dataset": "${DATASET}",
                "literal": "price $100 / $DATASET / $$ / $ / ${unfinished",
                "mixed": "price $100 for ${DATASET} / ${TEST_DATASET}",
                "empty": "${EMPTY}",
            },
            on_success={"event": "matched"},
            on_failure={"event": "mismatch", "message": "comparison failed"},
        )
        config = minimal_config(
            checks=[check, {**check, "expected_file_env": "", "expected_file_jsonl": "expected.jsonl"}],
            embedded_data=[{"name": "expectedMetrics", "file": "expected.jsonl"}],
            analytics={"offline": True}, success_message="comparison completed")
        generator = Generator()
        (tmp_path / "main.go").write_text(generator.generate(config))
        (tmp_path / "expected.jsonl").write_text('{"id":"a","value":833.67}\n')
        root = Path(__file__).resolve().parents[2]
        (tmp_path / "go.mod").write_text(generator.generate_gomod(
            config, replace={"github.com/shrimpsizemoose/trekker": str(root)}))
        for command in (["go", "mod", "tidy"], ["go", "build", "-buildvcs=false", "-o", "checker", "."]):
            result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, timeout=120)
            assert result.returncode == 0, result.stdout + result.stderr
        env = {**os.environ, "TEST_CH_ADDR": f"127.0.0.1:{server.server_port}",
               "TEST_EXPECTED": str(tmp_path / "expected.jsonl"),
               "TEST_DATASET": "a'b&c${UNCHANGED}", "TEST_EMPTY": ""}
        env.pop("TEST_1", None)
        result = subprocess.run([str(tmp_path / "checker")], cwd=tmp_path, env=env,
                                input="yes\n", capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "comparison completed" in result.stdout + result.stderr
        assert len(seen) == 2
        for sql, params in seen:
            assert sql == query
            assert params["param_dataset"] == ["a'b&c${UNCHANGED}"]
            assert params["param_literal"] == ["price $100 / $DATASET / $$ / $ / ${unfinished"]
            assert params["param_mixed"] == ["price $100 for a'b&c${UNCHANGED} / a'b&c${UNCHANGED}"]
            assert params["param_empty"] == [""]
        (tmp_path / "expected.jsonl").write_text('{"id":"a","value":0}\n')
        result = subprocess.run([str(tmp_path / "checker")], cwd=tmp_path, env=env,
                                input="yes\n", capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert "comparison failed" in result.stdout + result.stderr
        assert "comparison completed" not in result.stdout + result.stderr
        del env["TEST_DATASET"]
        result = subprocess.run([str(tmp_path / "checker")], cwd=tmp_path, env=env,
                                input="yes\n", capture_output=True, text=True, timeout=20)
        assert result.returncode != 0
        assert "TEST_DATASET is not set" in result.stdout + result.stderr
        assert len(seen) == 3
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
