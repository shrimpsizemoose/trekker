"""Command-line interface for pytrekgen."""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .generator import Generator

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    """Generate Go checker code from YAML configuration."""
    parser = argparse.ArgumentParser(
        description="Generate Go checker code from YAML configuration"
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        required=True,
        type=Path,
        help="Input YAML configuration file",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=Path,
        help="Output Go file (defaults to stdout)",
    )
    parser.add_argument(
        "-t",
        "--templates",
        dest="template_dir",
        type=Path,
        help="Custom template directory",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"pytrekgen {__version__}",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--with-gomod",
        action="store_true",
        help="Generate go.mod alongside the checker (requires -o and build.module in config)",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Override config value (dot notation, e.g. analytics.offline=true)",
    )

    viz_group = parser.add_mutually_exclusive_group()
    viz_group.add_argument(
        "--ascii",
        action="store_true",
        help="Print ASCII flow visualization instead of generating code",
    )
    viz_group.add_argument(
        "--html",
        action="store_true",
        help="Print HTML flow visualization instead of generating code",
    )
    viz_group.add_argument(
        "--mermaid",
        action="store_true",
        help="Print mermaid flowchart diagram instead of generating code",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.input_path.exists():
        log.error("Input file not found: %s", args.input_path)
        sys.exit(1)

    if args.template_dir and not args.template_dir.exists():
        log.error("Template directory not found: %s", args.template_dir)
        sys.exit(1)

    generator = Generator(template_dir=args.template_dir)

    overrides = {}
    for item in args.set:
        if "=" not in item:
            log.error("Invalid --set format: %s (expected KEY=VALUE)", item)
            sys.exit(1)
        key, value = item.split("=", 1)
        # Auto-convert booleans and numbers
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif value.isdigit():
            value = int(value)
        overrides[key] = value

    try:
        log.debug("Loading config from %s", args.input_path)
        config = generator.load_config(args.input_path, overrides=overrides)
        log.debug("Loaded config for lab %s", config.lab.id)
    except Exception as e:
        log.error("Failed to parse config: %s", e)
        sys.exit(1)

    viz_fmt = "ascii" if args.ascii else "html" if args.html else "mermaid" if args.mermaid else None

    if viz_fmt and args.with_gomod:
        log.error("--with-gomod cannot be used with visualization flags")
        sys.exit(1)

    if args.with_gomod and not args.output_path:
        log.error("--with-gomod requires -o/--output")
        sys.exit(1)

    if args.with_gomod and not config.build.module:
        log.error("--with-gomod requires build.module in config")
        sys.exit(1)

    try:
        if viz_fmt:
            output = generator.generate_flow(config, fmt=viz_fmt)
            if args.output_path:
                args.output_path.parent.mkdir(parents=True, exist_ok=True)
                args.output_path.write_text(output)
                log.info("Generated: %s", args.output_path)
            else:
                sys.stdout.write(output)
        else:
            source_file = args.input_path.name
            if args.output_path:
                generator.generate_to_file(
                    config, args.output_path, source_file=source_file
                )
                log.info("Generated: %s", args.output_path)

                if args.with_gomod:
                    generator.generate_gomod_to_file(config, args.output_path.parent)
                    log.info("Generated: %s", args.output_path.parent / "go.mod")
            else:
                code = generator.generate(config, source_file=source_file)
                sys.stdout.write(code)
    except Exception as e:
        log.error("Failed to generate code: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
