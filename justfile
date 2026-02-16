set shell := ["bash", "-euo", "pipefail"]

default:
  @just --list

[private]
_ensure-venv:
  test -d .venv || uv venv

[private]
_install-test-deps:
  uv sync --extra tests

# Create a local venv and install test/lint/type-check dependencies.
setup: _ensure-venv _install-test-deps

# Ensure `.venv` exists in the project.
venv: _ensure-venv

# Install dependencies needed to run tests/lint/type checks in place.
install-test-deps: _install-test-deps

# Install dependencies needed for the MCP CLI entrypoint.
mcp-deps:
  uv sync --extra mcp

# Open MCP server help output.
mcp-server:
  uv run safari-bookmarks-mcp --help

# Bootstrap MCP config for local development.
mcp-bootstrap-local:
  uv run safari-bookmarks bootstrap --client claude --client opencode --client gemini --client codex --scope local --write

# Bootstrap MCP config for user/global scope.
mcp-bootstrap-global:
  uv run safari-bookmarks bootstrap --client claude --client opencode --client gemini --client codex --scope global --write

# Bootstrap MCP config for both local and global scopes.
mcp-bootstrap-both:
  uv run safari-bookmarks bootstrap --client claude --client opencode --client gemini --client codex --scope both --write

# Run Ruff checks.
lint:
  uv run ruff check src tests

# Run Ty checks.
typecheck:
  uv run ty check src tests

# Run test suite.
test:
  uv run pytest

# Run all local quality gates.
check:
  just lint
  just typecheck
  just test
