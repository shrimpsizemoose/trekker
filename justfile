VERSION := `git describe --tags --always --dirty 2>/dev/null || echo "dev"`

tell-dependabot-issues:
    @printf "STATE\tSEVERITY\tPACKAGE\tFIXED IN\tSUMMARY\n" | expand -t 12,22,56,66
    @gh api repos/shrimpsizemoose/kanelbulle/dependabot/alerts \
        --jq 'sort_by(.security_advisory.severity | {critical:0,high:1,medium:2,low:3}[.]) | .[] | [.state, .security_advisory.severity, .dependency.package.name, (.security_vulnerability.first_patched_version.identifier // "n/a"), .security_advisory.summary] | @tsv' \
        | expand -t 12,22,56,66

echo-version:
    @echo current version = {{ VERSION }}

# Run pytrekgen tests
test:
    cd pytrekgen && uv run pytest

pytrekgen-example-lab00:
    cd pytrekgen && uv run pytrekgen -i examples/lab00.yaml

pytrekgen-example-lab01:
    cd pytrekgen && uv run pytrekgen -i examples/lab01.yaml

pytrekgen-example-lab02:
    cd pytrekgen && uv run pytrekgen -i examples/lab02.yaml

pytrekgen-example-lab03:
    cd pytrekgen && uv run pytrekgen -i examples/lab03.yaml

# Visualize checker flow as ASCII
visualize-ascii lab:
    cd pytrekgen && uv run pytrekgen -i examples/{{lab}}.yaml --ascii

# Visualize checker flow as HTML
visualize-html lab:
    cd pytrekgen && uv run pytrekgen -i examples/{{lab}}.yaml --html -o /tmp/{{lab}}-flow.html
    @echo "Open /tmp/{{lab}}-flow.html in a browser"

# Generate documentation locally for debugging
docs-generate:
    cd pytrekgen && uv run python docs_generator.py
    @echo "Documentation generated in: docs/"

# Serve docs locally with Python's built-in HTTP server (for raw MD files)
docs-serve-raw: docs-generate
    @echo "Serving raw docs at http://localhost:8000"
    @cd docs && python3 -m http.server 8000

# Serve docs with MkDocs (requires 'uv sync --extra dev' in pytrekgen first)
docs-serve: docs-generate
    cd pytrekgen && uv run mkdocs serve --config-file ../mkdocs.yml -a localhost:8000
