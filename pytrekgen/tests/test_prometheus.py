"""Validation, generated lifecycle, and local Prometheus behavior."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from conftest import minimal_config
from pytrekgen.config import CHECK_TYPE_STDLIB_IMPORTS
from pytrekgen.generator import Generator

QUERY = dict(type="prometheus_query", url="${PROMETHEUS_URL}", query='sum(up{job=~"a+b\\\\c"}) or vector(0)', operator="==", expected=1)
ALERT = dict(type="prometheus_alert", url="${PROMETHEUS_URL}", alert="ApiUnavailable", state="inactive")
CONFIRM = dict(type="confirm", name="ready", description="Readiness check", on_success={"event": "confirmed"}, on_failure={"event": "confirm_failed"}, message='Ready? "yes" \\ `\nда')


@pytest.mark.parametrize("check,changes", [
    (CONFIRM, {"message": "  "}), (QUERY, {"url": ""}),
    (QUERY, {"query": "\t"}), (ALERT, {"alert": " "}),
    (QUERY, {"operator": "="}), (ALERT, {"state": "missing"}),
    *[(QUERY, {"timeout_seconds": x}) for x in [True, 0, -1, 1.5, "1"]],
    *[(QUERY, {"expected": x}) for x in [True, "1", float("nan"), float("inf"), -float("inf")]],
])
def test_invalid(check, changes):
    with pytest.raises(ValidationError):
        minimal_config(checks=[{**check, **changes}])


def test_defaults_and_visualization():
    config = minimal_config(checks=[CONFIRM, QUERY, ALERT])
    assert config.checks[1].timeout_seconds == 120
    assert config.checks[1].message_before == ""
    assert len(config.required_helper_templates) == 1
    gen = Generator()
    for check in config.checks:
        assert gen._check_detail(check)
    assert "ApiUnavailable" in gen.generate_flow(config, "html")


def run(command, directory):
    result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("field,value", [
    ("usage_docker", "docker run ${IMAGE}"),
    ("usage_debug", "Debug: ${DEBUG}"),
])
def test_offline_confirm_usage_compiles(tmp_path, field, value):
    config = minimal_config(checks=[CONFIRM], analytics={"offline": True}, **{field: value})
    gen = Generator()
    (tmp_path / "main.go").write_text(gen.generate(config))
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "go.mod").write_text(gen.generate_gomod(config, replace={"github.com/shrimpsizemoose/trekker": str(root)}))
    run(["go", "mod", "tidy"], tmp_path)
    run(["go", "build", "-buildvcs=false", "-o", "checker", "."], tmp_path)


def test_go_helpers(tmp_path):
    gen = Generator()
    imports = (CHECK_TYPE_STDLIB_IMPORTS["prometheus_query"] - {"os/signal"}) | {"fmt"}
    (tmp_path / "go.mod").write_text("module prometheustest\n\ngo 1.23\n")
    (tmp_path / "prometheus.go").write_text('package main\nimport (\n' + '\n'.join(f'"{x}"' for x in imports) + '\n)\n' + gen.env.get_template("checks/prometheus_helpers.go.j2").render())
    shutil.copy(Path(__file__).parent / "go/prometheus_test.go.txt", tmp_path / "prometheus_test.go")
    run(["gofmt", "-w", "prometheus.go", "prometheus_test.go"], tmp_path)
    run(["go", "test", "-race", "-count=1", "-timeout=40s", "./..."], tmp_path)
    run(["go", "vet", "./..."], tmp_path)


@pytest.mark.parametrize("checks", [[CONFIRM], [QUERY], [ALERT], [QUERY, ALERT], [QUERY, QUERY], "example", "branch", "branch_query", "branch_alert"])
def test_generated_build(tmp_path, checks):
    gen = Generator()
    flags = []
    if checks == "example":
        config = gen.load_config(Path(__file__).parents[1] / "examples/prometheus.yaml")
        config.build.module = "example"
    else:
        if isinstance(checks, str) and checks.startswith("branch"):
            flags = [dict(name="drill", default="false")]
            target = {"branch": CONFIRM, "branch_query": QUERY, "branch_alert": ALERT}[checks]
            checks = [dict(type="branch_flag", flag="drill", if_set="ready"),
                      {**target, "name": "ready", "_branch_only": True, "dead_end": True},
                      {**QUERY, "skip_on_flag": "drill"}]
        config = minimal_config(checks=checks, flags=flags, analytics={"offline": True}, success_message="ALL_DONE")
    if checks == [CONFIRM]:
        config.checks.extend(minimal_config(checks=[dict(type="wait", seconds=0, on_success={"event": "next_check"})]).checks)
    (tmp_path / "main.go").write_text(gen.generate(config))
    root = Path(__file__).resolve().parents[2]
    (tmp_path / "go.mod").write_text(gen.generate_gomod(config, replace={"github.com/shrimpsizemoose/trekker": str(root)}))
    run(["go", "mod", "tidy"], tmp_path)
    run(["gofmt", "-w", "main.go"], tmp_path)
    run(["go", "test", "./..."], tmp_path)
    run(["go", "vet", "./..."], tmp_path)
    if flags and target == CONFIRM:
        run(["go", "build", "-o", "checker", "."], tmp_path)
        result = subprocess.run([str(tmp_path / "checker"), "--drill"], input="yes\nyes\n", capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        assert result.returncode == 0 and "100_lab_finish" not in output and "ALL_DONE" not in output
        assert output.count(" confirmed ") == 1
    if checks == [CONFIRM]:
        run(["go", "build", "-o", "checker", "."], tmp_path)
        for stdin, success in [("yes\nyes\n", True), ("yes\nno\n", False), ("yes\n", False), ("yes\nwhat\nyes\n", True)]:
            result = subprocess.run([str(tmp_path / "checker")], input=stdin, capture_output=True, text=True, timeout=10, env=os.environ)
            output = result.stdout + result.stderr
            assert ("ALL_DONE" in output) == success
            assert output.count(" confirmed ") == int(success)
            assert output.count("100_lab_finish") == int(success)
            assert "confirm_failed" not in output
            assert output.count(" next_check ") == int(success)
        result = subprocess.run([str(tmp_path / "checker"), "--checks"], capture_output=True, text=True, timeout=10)
        assert "[confirm] ready" in result.stdout and "Readiness check" in result.stdout


def test_runtime_events(tmp_path):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import parse_qs, urlsplit

    seen = []
    unhealthy = False

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            seen.append(parsed.path)
            if parsed.path.endswith("query"):
                assert parse_qs(parsed.query)["query"] == [QUERY["query"]]
                data = {"resultType": "scalar", "result": [1, "1" if seen.count(parsed.path) > 1 else "0"]}
            else:
                assert parse_qs(parsed.query)["type"] == ["alert"]
                data = {"groups": [{"rules": [{"type": "alerting", "name": "ApiUnavailable", "state": "inactive", "health": "err" if unhealthy else "ok", "lastError": "evaluation failed"}]}]}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success", "data": data}).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        config = minimal_config(checks=[CONFIRM,
            {**QUERY, "timeout_seconds": 3, "message_before": "WAIT_QUERY", "message_success": "QUERY_DONE", "on_success": {"event": "query_pass"}, "on_failure": {"event": "query_fail"}},
            {**ALERT, "timeout_seconds": 1, "on_success": {"event": "alert_pass"}, "on_failure": {"event": "alert_fail", "message": "ALERT_FAILURE"}}], analytics={"offline": True})
        gen = Generator()
        (tmp_path / "main.go").write_text(gen.generate(config))
        root = Path(__file__).resolve().parents[2]
        (tmp_path / "go.mod").write_text(gen.generate_gomod(config, replace={"github.com/shrimpsizemoose/trekker": str(root)}))
        run(["go", "mod", "tidy"], tmp_path)
        run(["go", "build", "-buildvcs=false", "-o", "checker", "."], tmp_path)
        env = {**os.environ, "TEST_PROMETHEUS_URL": f"http://user:secret@127.0.0.1:{server.server_port}/base/"}
        for unhealthy in [False, True]:
            seen.clear()
            result = subprocess.run([str(tmp_path / "checker")], cwd=tmp_path, env=env, input="yes\nyes\n", capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            assert (result.returncode == 0) == (not unhealthy), output
            for marker in [" confirmed ", " query_pass ", "WAIT_QUERY", "QUERY_DONE"]:
                assert output.count(marker) == 1, output
            assert " query_fail " not in output
            assert output.count(" alert_pass ") == int(not unhealthy)
            assert output.count(" alert_fail ") == int(unhealthy)
            assert output.count("100_lab_finish") == int(not unhealthy)
            if unhealthy:
                assert "ALERT_FAILURE" in output and "health=err" in output and "evaluation failed" in output
            assert "secret" not in output
            assert seen.count("/base/api/v1/query") == 2
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_url_format_escaping_and_prefix():
    formatted = Generator._url_format('http://${TEST_HOST}/a%20b?x="q"', "TEST")
    assert 'os.Getenv("TEST_HOST")' in formatted
    assert "TEST_TEST_HOST" not in formatted
    assert r'a%%20b?x=\"q\"' in formatted


def test_documented_operators():
    from docs_generator import get_model_fields
    from pytrekgen.config import PrometheusQueryCheck

    operator = next(field for field in get_model_fields(PrometheusQueryCheck) if field["name"] == "operator")
    assert "'>'" in operator["type"] and "'>='" in operator["type"]
