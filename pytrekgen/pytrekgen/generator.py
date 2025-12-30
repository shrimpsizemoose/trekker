"""Code generator using Jinja2 templates."""

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

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

        # Register custom filters
        self.env.filters["quote"] = self._quote
        self.env.filters["title_case"] = self._title_case
        self.env.filters["lower_camel"] = self._lower_camel
        self.env.filters["url_to_format"] = self._url_to_format
        self.env.filters["extract_vars"] = self._extract_vars
        self.env.filters["url_format"] = self._url_format

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
    def _url_to_format(url: str) -> str:
        """Convert 'http://${VAR}/path' to 'http://%s/path'."""
        return re.sub(r"\$\{[^}]+\}", "%s", url)

    @staticmethod
    def _extract_vars(url: str) -> list[str]:
        """Extract variable names from 'http://${VAR1}/${VAR2}'."""
        return re.findall(r"\$\{([^}]+)\}", url)

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
        getenvs = ", ".join(f'os.Getenv("{env_prefix}_{var}")' for var in vars_found)
        return f'fmt.Sprintf("{format_str}", {getenvs}, )'

    @classmethod
    def load_config(cls, config_path: Path) -> LabConfig:
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

    def generate_to_file(
        self, config: LabConfig, output_path: Path, source_file: str = ""
    ) -> None:
        """Generate Go code and write to file."""
        code = self.generate(config, source_file=source_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(code)

    def generate_gomod(self, config: LabConfig) -> str:
        """Generate go.mod content.

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

        return "\n".join(lines) + "\n"

    def generate_gomod_to_file(self, config: LabConfig, output_dir: Path) -> None:
        """Generate go.mod and write to file."""
        content = self.generate_gomod(config)
        output_path = output_dir / "go.mod"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)
