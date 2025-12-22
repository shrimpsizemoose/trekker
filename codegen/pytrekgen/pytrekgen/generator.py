"""Code generator using Jinja2 templates."""

import re
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ConfirmField, LabConfig


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

    @classmethod
    def load_config(cls, config_path: Path) -> LabConfig:
        """Load and validate configuration from YAML file.

        Returns:
            initialized LabConfig object

        """
        with Path(config_path).open() as f:
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
