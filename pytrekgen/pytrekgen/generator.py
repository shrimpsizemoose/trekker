"""Code generator using Jinja2 templates."""

import re
from io import StringIO
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import LabConfig


class Generator:
    """Generates Go code from lab configuration."""

    def __init__(self, template_dir: Path | None = None) -> None:
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(default=False),
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        self._register_custom_filters()

    def _register_custom_filters(self) -> None:
        self.env.filters["quote"] = self._quote
        self.env.filters["title_case"] = self._title_case
        self.env.filters["lower_camel"] = self._lower_camel
        self.env.filters["url_to_format"] = self._url_to_format
        self.env.filters["extract_vars"] = self._extract_vars
        self.env.filters["url_format"] = self._url_format
        self.env.filters["prefixed_env"] = self._prefixed_env
        self.env.filters["check_detail"] = self._check_detail
        self.env.filters["check_type_label"] = self._check_type_label

    @staticmethod
    def _quote(value: str) -> str:
        """Quote a string for Go."""
        return f'"{value}"'

    @staticmethod
    def _title_case(s: str) -> str:
        """Convert 'send-only' or 'send_only' to 'SendOnly'."""
        s = s.replace("-", " ").replace("_", " ")
        return "".join(word.capitalize() for word in s.split())

    @staticmethod
    def _lower_camel(s: str) -> str:
        """Convert 'UPPER_SNAKE' to 'upperSnake'."""
        parts = s.lower().split("_")
        return parts[0] + "".join(word.capitalize() for word in parts[1:])

    @staticmethod
    def _prefixed_env(name: str, prefix: str) -> str:
        """Create env var name with optional prefix.

        Example:
            _prefixed_env("TOKEN", "NPL") -> "NPL_TOKEN"
            _prefixed_env("TOKEN", "") -> "TOKEN"
            _prefixed_env("NPL_TOKEN", "NPL") -> "NPL_TOKEN"

        """
        if prefix:
            if name.startswith(f"{prefix}_"):
                return name
            return f"{prefix}_{name}"
        return name

    @staticmethod
    def _url_to_format(url: str) -> str:
        """Convert 'http://${VAR}/path' to 'http://%s/path'."""
        return re.sub(r"\$\{[^}]+\}", "%s", url)

    @staticmethod
    def _extract_vars(url: str) -> list[str]:
        """Extract variable names from 'http://${VAR1}/${VAR2}'."""
        return re.findall(r"\$\{([^}]+)\}", url)

    @staticmethod
    def _check_detail(check, config=None) -> str:
        """Extract a display-friendly one-line detail string from a check."""
        match check.type:
            case "param_equals":
                cmp = " (case-insensitive)" if check.case_insensitive else ""
                return f"{check.env_var} == {check.expected!r}{cmp}"
            case "forbidden_address":
                return f"{check.env_var} not in [{', '.join(check.forbidden)}]"
            case "wait":
                return f"wait {check.seconds}s"
            case "http_get":
                return f"GET {check.url} → {check.expected_status}"
            case "http_get_random_path":
                return f"GET {check.url}/??? → {check.expected_status}"
            case "http_request":
                return f"{check.method} {check.url} → {check.expected_status}"
            case "http_batch":
                return f"batch {check.method} {check.url} (data: {check.test_data})"
            case "http_batch_repeat":
                return f"repeat batch {check.reuse}"
            case "kafka_topic_exists":
                return f"topic: ${{{check.kafka_topic_env}}} @ ${{{check.kafka_addr_env}}}"
            case "kafka_roundtrip":
                return f"roundtrip {check.message_count} msgs @ ${{{check.kafka_addr_env}}}"
            case "kafka_send_file":
                return f"send {check.file} → ${{{check.kafka_topic_env}}}"
            case "postgres_connect":
                return f"connect ${{{check.postgres_url_env}}}"
            case "postgres_tables_empty":
                parts = list(check.tables)
                parts += [f"${{{e}}}" for e in check.tables_from_env]
                return f"tables empty: {', '.join(parts)}"
            case "clickhouse_query_simple":
                if check.expected:
                    return f"query: {check.query} → {check.expected!r}"
                return f"query: {check.query} → {check.expected_rows} rows"
            case "kafka_to_clickhouse":
                parts = list(check.match_by)
                return (
                    f"send {check.send_file_jsonl} → ${{{check.send_topic_env}}} "
                    f"| query CH → {check.expected_file_jsonl} "
                    f"[{', '.join(parts)}]"
                )
            case "custom":
                detail = f"func: {check.func}()"
                if config and config.custom_code and config.custom_code.code_file:
                    detail += f" [{config.custom_code.code_file}]"
                return detail
            case "branch_flag":
                parts = [f"flag: -{check.flag}"]
                if check.if_set:
                    parts.append(f"yes → {check.if_set}")
                if check.if_not_set:
                    parts.append(f"no → {check.if_not_set}")
                return ", ".join(parts)
            case _:
                return check.type

    @staticmethod
    def _check_type_label(check, config=None) -> str:
        """Return type label, enriched for custom checks with code_file."""
        if check.type == "custom" and config and config.custom_code and config.custom_code.code_file:
            return f"custom::{config.custom_code.code_file}"
        return check.type

    @staticmethod
    def _extract_custom_events(config, func_name: str) -> list[str]:
        """Extract tracker.Ping event names from a custom function's body."""
        code = ""
        if config and config.custom_code:
            code = config.custom_code.code or ""

        if not code or not func_name:
            return []

        # Find function body: func funcName(...) ... { ... }
        # Use a simple brace-counting approach
        pattern = rf'func\s+{re.escape(func_name)}\s*\('
        match = re.search(pattern, code)
        if not match:
            return []

        # Find opening brace
        brace_pos = code.find("{", match.end())
        if brace_pos == -1:
            return []

        # Count braces to find function end
        depth = 1
        pos = brace_pos + 1
        while pos < len(code) and depth > 0:
            if code[pos] == "{":
                depth += 1
            elif code[pos] == "}":
                depth -= 1
            pos += 1

        body = code[brace_pos:pos]
        return re.findall(r'tracker\.Ping\("([^"]+)"', body)

    @staticmethod
    def _strip_build_constraints(content: str) -> str:
        """Strip Go build constraints from file content.

        Removes lines starting with //go:build or // +build and any
        following blank line (as per Go convention).
        """
        lines = content.split("\n")
        result = []
        skip_next_blank = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//go:build") or stripped.startswith("// +build"):
                skip_next_blank = True
                continue
            if skip_next_blank and stripped == "":
                skip_next_blank = False
                continue
            skip_next_blank = False
            result.append(line)

        return "\n".join(result)

    @staticmethod
    def _url_format(url: str, env_prefix: str) -> str:
        """Convert URL with ${VAR} placeholders to Go fmt.Sprintf call.

        Example:
            http://${IP}:${PORT} -> fmt.Sprintf("http://%s:%s", os.Getenv("NPL_IP"), os.Getenv("NPL_PORT"), )

        """
        vars_found = re.findall(r"\$\{([^}]+)\}", url)
        if not vars_found:
            return f'"{url}"'

        format_str = re.sub(r"\$\{[^}]+\}", "%s", url)
        getenvs = ", ".join(
            f'os.Getenv("{env_prefix}_{var}")' if env_prefix else f'os.Getenv("{var}")'
            for var in vars_found
        )
        return f'fmt.Sprintf("{format_str}", {getenvs}, )'

    @classmethod
    def load_config(cls, config_path: Path, overrides: dict | None = None) -> LabConfig:
        """Load and validate configuration from YAML file.

        Returns:
            initialized LabConfig object

        """
        config_path = Path(config_path)
        config_dir = config_path.parent

        with config_path.open() as f:
            data = yaml.safe_load(f)

        # Handle confirm_display which can be strings or dicts
        if "confirm_display" in data:
            normalized = []
            for item in data["confirm_display"]:
                if isinstance(item, str):
                    normalized.append({"name": item, "masked": False})
                else:
                    normalized.append(item)
            data["confirm_display"] = normalized

        # Handle custom_code file references
        if "custom_code" in data:
            cc = data["custom_code"]

            # Read types from file if specified
            if cc.get("types_file"):
                types_path = config_dir / cc["types_file"]
                file_content = types_path.read_text()
                # Strip build constraints (//go:build, // +build)
                file_content = cls._strip_build_constraints(file_content)
                # Merge: file content first, then inline
                cc["types"] = file_content + "\n" + cc.get("types", "")
                cc["types"] = cc["types"].strip()

            # Read code from file if specified
            if cc.get("code_file"):
                code_path = config_dir / cc["code_file"]
                file_content = code_path.read_text()
                # Strip build constraints (//go:build, // +build)
                file_content = cls._strip_build_constraints(file_content)
                # Merge: file content first, then inline
                cc["code"] = file_content + "\n" + cc.get("code", "")
                cc["code"] = cc["code"].strip()

        # Apply dot-notation overrides (e.g. {"analytics.offline": True})
        for key, value in (overrides or {}).items():
            parts = key.split(".")
            target = data
            for part in parts[:-1]:
                target = target.setdefault(part, {})
            target[parts[-1]] = value

        return LabConfig.model_validate(data)

    def generate(self, config: LabConfig, source_file: str = "") -> str:
        """Generate Go code from configuration.

        Returns:
            rendered template as string

        """
        template = self.env.get_template("base.go.j2")

        return template.render(
            config=config,
            lab=config.lab,
            confirm_fields=config.get_confirm_fields(),
            source_file=source_file,
        )

    def generate_flow(self, config: LabConfig, fmt: str = "ascii") -> str:
        match fmt:
            case "ascii":
                return self._render_ascii(config)
            case "mermaid":
                return self.generate_mermaid(config)
            case _:
                mermaid_text = self._build_mermaid_lines(config, html_labels=True)
                template = self.env.get_template(f"flow.{fmt}.j2")
                return template.render(config=config, mermaid_text=mermaid_text)

    @classmethod
    def generate_mermaid(cls, config: LabConfig) -> str:
        """Generate markdown-fenced mermaid flowchart."""
        diagram = cls._build_mermaid_lines(config, html_labels=False)
        return f"```mermaid\n{diagram}\n```\n"

    @classmethod
    def _build_mermaid_lines(cls, config: LabConfig, html_labels: bool = False) -> str:
        """Build mermaid diagram lines from config.

        Args:
            config: Lab configuration.
            html_labels: Use HTML formatting in node labels (for embedded HTML pages).

        """
        br = "<br/>"
        success = "SUCCESS{{100_lab_finish}}"
        fail = "FAIL{Fail}"
        dead_end_node = 'DEAD_END([" Done (no grade)"])'

        checks_by_name = {c.name: c for c in config.checks if c.name}

        visible_checks = [
            c for c in config.checks
            if not getattr(c, "branch_only", False)
        ]

        def build_node_label(check, number=None):
            """Build mermaid node label for a check."""
            name = check.name or "unnamed"
            type_label = cls._check_type_label(check, config)

            if html_labels and number is not None:
                label = f'<b><span style="font-size:1.1em">{number}. {name}</span></b>{br}[{type_label}]'
            elif number is not None:
                label = f"{number}. {name}{br}[{type_label}]"
            else:
                label = f"{name}{br}[{type_label}]"

            events = []
            for attr in ("on_request", "on_connect", "on_start", "on_response", "on_partitions_read"):
                val = getattr(check, attr, None)
                if val:
                    events.append(val)

            # Extract tracker.Ping events from custom code
            if check.type == "custom" and hasattr(check, "func"):
                custom_events = cls._extract_custom_events(config, check.func)
                events.extend(custom_events)

            if events:
                styled = ", ".join(f"<i>{e}</i>" for e in events)
                label += br + styled

            return label

        def add_node_and_edges(lines, node_id, check, next_node, number=None):
            """Add a check node with success/failure edges."""
            label = build_node_label(check, number)
            lines.append(f'    {node_id}["{label}"]')

            target = dead_end_node if getattr(check, "dead_end", False) else next_node

            if check.on_success and check.on_success.event:
                evt = f"<i>{check.on_success.event}</i>"
                lines.append(f'    {node_id} -- "{evt}" --> {target}')
            else:
                lines.append(f"    {node_id} --> {target}")

            if check.on_failure and check.on_failure.event:
                evt = f"<i>{check.on_failure.event}</i>"
                lines.append(f'    {node_id} -. "{evt}" .-> {fail}')

        lines = ["graph TD"]
        lines.append("    START{{000_lab_start}} --> C1")

        for i, check in enumerate(visible_checks, 1):
            next_node = f"C{i + 1}" if i < len(visible_checks) else success

            if check.type == "branch_flag":
                flag_label = f"-{check.flag}?"
                lines.append(f'    C{i}{{"{flag_label}"}}')

                if check.if_set and check.if_set in checks_by_name:
                    target = checks_by_name[check.if_set]
                    add_node_and_edges(lines, f"C{i}_yes", target, next_node)
                    lines.append(f'    C{i} -->|yes| C{i}_yes')
                elif check.if_set:
                    lines.append(f'    C{i} -->|yes| C{i}_yes["{check.if_set}"]')
                    lines.append(f"    C{i}_yes --> {next_node}")

                if check.if_not_set and check.if_not_set in checks_by_name:
                    target = checks_by_name[check.if_not_set]
                    add_node_and_edges(lines, f"C{i}_no", target, next_node)
                    lines.append(f'    C{i} -->|no| C{i}_no')
                elif check.if_not_set:
                    lines.append(f'    C{i} -->|no| C{i}_no["{check.if_not_set}"]')
                    lines.append(f"    C{i}_no --> {next_node}")

                if not check.if_set:
                    lines.append(f"    C{i} -->|yes| {next_node}")
                if not check.if_not_set:
                    lines.append(f"    C{i} -->|no| {next_node}")

                continue

            add_node_and_edges(lines, f"C{i}", check, next_node, number=i)

        lines.append("    classDef startEnd fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef fail fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c")
        lines.append("    classDef deadEnd fill:#fff3cd,stroke:#664d03,stroke-width:2px,color:#664d03")
        lines.append("    class START,SUCCESS startEnd")
        lines.append("    class FAIL fail")
        lines.append("    class DEAD_END deadEnd")

        return "\n".join(lines)

    @classmethod
    def _render_ascii(cls, config: LabConfig) -> str:
        buf = StringIO()
        console = Console(file=buf, width=72, highlight=False)
        prefix = config.lab.env_prefix

        # --- Header ---
        header = Text()
        header.append(f"Lab {config.lab.id}: {config.lab.name}", style="bold")
        if prefix:
            header.append(f"\nPrefix: {prefix}")
        console.print(Panel(header, style="blue"))

        # --- Env vars ---
        if config.required_env or config.optional_env or config.optional_env_int:
            env_table = Table(show_header=True, expand=True, box=None, padding=(0, 1))
            env_table.add_column("Variable", style="bold")
            env_table.add_column("Kind")
            env_table.add_column("Default", style="dim")
            for env in config.required_env:
                env_table.add_row(cls._prefixed_env(env.name, prefix), "required", "")
            for env in config.optional_env:
                env_table.add_row(
                    cls._prefixed_env(env.name, prefix), "optional", env.default
                )
            for env in config.optional_env_int:
                env_table.add_row(
                    cls._prefixed_env(env.name, prefix), "optional", str(env.default)
                )
            console.print(Panel(env_table, title="Environment", style="cyan"))

        # --- Start event ---
        console.print("         │", style="dim")
        console.print("         │  **000_lab_start**", style="dim")
        console.print("         ▼", style="dim")

        # --- Checks ---
        checks_by_name = {c.name: c for c in config.checks if c.name}
        visible_checks = [
            c for c in config.checks
            if not getattr(c, "branch_only", False)
        ]

        def render_check_panel(check, number, style="white"):
            """Render a single check as a Panel."""
            detail = cls._check_detail(check, config)
            name = check.name or "unnamed"

            body = Text()
            body.append(detail)

            events = []
            if check.on_success and check.on_success.event:
                events.append(("✓ ", "green", check.on_success.event))
            if check.on_failure and check.on_failure.event:
                events.append(("✗ ", "red", check.on_failure.event))
            if check.skip_on_flag:
                events.append(("⊘ ", "yellow", f"skip if --{check.skip_on_flag}"))
            if getattr(check, "dead_end", False):
                events.append(("⛔ ", "yellow", "dead end (no grade)"))

            # Extract tracker.Ping events from custom code
            if check.type == "custom" and hasattr(check, "func"):
                for evt in cls._extract_custom_events(config, check.func):
                    events.append(("📡 ", "dim", evt))

            if events:
                for symbol, ev_style, text in events:
                    body.append("\n")
                    body.append(symbol, style=ev_style)
                    body.append(text, style="dim")

            type_label = cls._check_type_label(check, config)
            title = f"{number}. [bold]{name}[/bold]  [dim]\\[{type_label}][/dim]"
            return Panel(body, title=title, style=style)

        for i, check in enumerate(visible_checks, 1):
            if check.type == "branch_flag":
                # Render branch as a panel with both paths
                name = check.name or "unnamed"
                body = Text()
                body.append(f"⚑ flag: --{check.flag}\n")

                if check.if_set and check.if_set in checks_by_name:
                    target = checks_by_name[check.if_set]
                    de = " ⛔" if getattr(target, "dead_end", False) else ""
                    body.append(f"  yes → {check.if_set} [{target.type}]{de}\n", style="green")
                elif check.if_set:
                    body.append(f"  yes → {check.if_set}\n", style="green")

                if check.if_not_set and check.if_not_set in checks_by_name:
                    target = checks_by_name[check.if_not_set]
                    de = " ⛔" if getattr(target, "dead_end", False) else ""
                    body.append(f"  no  → {check.if_not_set} [{target.type}]{de}", style="blue")
                elif check.if_not_set:
                    body.append(f"  no  → {check.if_not_set}", style="blue")

                title = f"{i}. [bold]{name}[/bold]  [dim]\\[branch_flag][/dim]"
                console.print(Panel(body, title=title, style="yellow"))
            else:
                console.print(render_check_panel(check, i))

            if i < len(visible_checks):
                console.print("         │", style="dim")
                console.print("         ▼", style="dim")

        # --- Finish event + Success ---
        console.print("         │", style="dim")
        console.print("         │  **100_lab_finish**", style="dim")
        console.print("         ▼", style="dim")
        console.print(
            Panel(
                Text("✅ Success", justify="center"),
                style="green",
            )
        )

        # --- Analytics footer ---
        footer = Text()
        analytics_desc = config.analytics.url_env
        if config.analytics.skip_tls:
            analytics_desc += " (skip_tls)"
        if config.analytics.offline:
            analytics_desc += " (offline)"
        footer.append(f"Analytics: {analytics_desc}\n")

        if config.analytics.headers:
            parts = [f"{k}={v}" for k, v in config.analytics.headers.items()]
            footer.append(f"Headers: {', '.join(parts)}\n", style="dim")

        flag_names = ["--ping", "--version", "--checks"]
        for f in config.flags:
            flag_names.append(f"--{f.name}")
        footer.append(f"Flags: {', '.join(flag_names)}")

        console.print(Panel(footer, style="dim"))

        return buf.getvalue()

    def generate_to_file(
        self, config: LabConfig, output_path: Path, source_file: str = ""
    ) -> None:
        """Generate Go code and write to file."""
        code = self.generate(config, source_file=source_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code)

    def generate_gomod(
        self,
        config: LabConfig,
        replace: dict[str, str] | None = None,
    ) -> str:
        """Generate go.mod content.

        Args:
            config: Lab configuration
            replace: Optional dict of module -> path replace directives

        Returns:
            go.mod content as string

        """
        if not config.build.module:
            raise ValueError("build.module is required for go.mod generation")

        lines = [
            f"module {config.build.module}",
            "",
            f"go {config.build.go_version}",
        ]

        if replace:
            lines.append("")
            for module, path in replace.items():
                lines.append(f"replace {module} => {path}")

        return "\n".join(lines) + "\n"

    def generate_gomod_to_file(self, config: LabConfig, output_dir: Path) -> None:
        """Generate go.mod and write to file."""
        content = self.generate_gomod(config)
        output_path = output_dir / "go.mod"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
