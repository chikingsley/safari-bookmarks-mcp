# Changelog

## Unreleased

- Migrated to `mcp` 2.x (`MCPServer`) and bounded the dependency to `>=2.3.0,<3`. Released 0.6.2 allows `mcp` 2.x but imports the removed `mcp.server.fastmcp`, so a fresh install fails at startup.
- Kept refusal and validation messages visible to MCP clients, which the 2.x SDK would otherwise replace with a generic error.
- Replaced the `pip-audit` wrapper with `uv audit`, which also covers the `build` extra and `audit` group.
- Made `just check` run the same lint, format and type checks as CI.

## 0.6.2

- Fixed broken wheel: source package was missing from 0.6.1 due to incorrect hatchling include config.
- Made `mcp` a core dependency (not optional) since this is primarily an MCP server — `uvx safari-bookmarks-mcp` now works without extras.
- Fixed `__iter__` return type (`Iterable` → `Iterator`) and removed dict unpacking into Pydantic constructors, resolving all ty type errors.
- Simplified README: MCP server first, uvx pattern, CLI secondary, dev at the bottom.

- Fixed CI workflows: replaced `flake8`/`pip` with `ruff`/`ty`/`uv`, corrected action versions, trimmed Python matrix to 3.12+ (per `requires-python`), split lint and test into separate jobs.
- Fixed test fixture plists that had stale URLs from the upstream fork (`evilmarty/safari-bookmarks-cli` → `chikingsley/safari-bookmarks-mcp`).
- Updated Dependabot to track `uv` ecosystem instead of `pip`.

## 0.6.1

- **Publication**: Updated package publication metadata and authorship for PyPI release via `uv`.
- **Attribution**: Added formal homage and attribution to `evilmarty` (Marty) for the core CLI logic in accordance with the Apache 2.0 license.
- Renamed project from `safari-bookmarks-cli` to `safari-bookmarks-mcp` to reflect MCP server support.
- Reorganized source into `cli/` and `mcp/` subpackages for clearer separation of concerns.
- Added MCP bootstrap support via `safari-bookmarks bootstrap` to generate local/global client configuration for Claude Code, OpenCode, Codex, and Gemini.
- Documented MCP bootstrap workflow for local vs global scope, including how to preview changes with plan-only mode and how to apply with `--write`.
- Documented that NPX/BUNX are Node-only install paths and not directly available for this Python package unless you publish a wrapper package.
