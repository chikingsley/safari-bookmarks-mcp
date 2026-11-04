set shell := ["bash", "-euo", "pipefail", "-c"]
export UV_SYSTEM_CERTS := "1"

default:
  @just --list

[private]
_ensure-venv:
  test -d .venv || uv venv

[private]
_install-test-deps:
  uv sync --locked --dev

# Create a local venv and install test/lint/type-check dependencies.
setup: _ensure-venv _install-test-deps

# Ensure `.venv` exists in the project.
venv: _ensure-venv

# Install dependencies needed to run tests/lint/type checks in place.
install-test-deps: _install-test-deps

# Install local git hooks that run the quality/security gate before push.
install-hooks:
  mkdir -p .git/hooks
  cp scripts/git-hooks/pre-push .git/hooks/pre-push
  chmod +x .git/hooks/pre-push

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

# Run Ruff lint and format checks over the whole repo, matching CI.
lint:
  uv run --locked ruff check .
  uv run --locked ruff format --check .

# Run Ty checks.
typecheck:
  uv run --locked ty check

# Run test suite.
test:
  uv run --locked pytest

# Audit locked Python dependencies for known vulnerabilities.
audit-deps:
  uv audit --locked --preview-features audit-command

# Audit GitHub Actions workflows for common supply-chain hazards.
audit-actions:
  uv run --locked --group audit zizmor .github/workflows

# Run supply-chain checks.
audit:
  just audit-deps
  just audit-actions

# Run all local quality gates.
check:
  just lint
  just typecheck
  just test
