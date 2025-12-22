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

    try:
        log.debug("Loading config from %s", args.input_path)
        config = generator.load_config(args.input_path)
        log.debug("Loaded config for lab %s", config.lab.id)
    except Exception as e:
        log.error("Failed to parse config: %s", e)
        sys.exit(1)

    try:
        source_file = args.input_path.name
        if args.output_path:
            generator.generate_to_file(
                config, args.output_path, source_file=source_file
            )
            log.info("Generated: %s", args.output_path)
        else:
            code = generator.generate(config, source_file=source_file)
            sys.stdout.write(code)
    except Exception as e:
        log.error("Failed to generate code: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
