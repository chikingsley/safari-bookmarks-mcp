# Changelog

## Unreleased

- Renamed project from `safari-bookmarks-cli` to `safari-bookmarks-mcp` to reflect MCP server support.
- Reorganized source into `cli/` and `mcp/` subpackages for clearer separation of concerns.
- Added MCP bootstrap support via `safari-bookmarks bootstrap` to generate local/global client configuration for Claude Code, OpenCode, Codex, and Gemini.
- Documented MCP bootstrap workflow for local vs global scope, including how to preview changes with plan-only mode and how to apply with `--write`.
- Documented that NPX/BUNX are Node-only install paths and not directly available for this Python package unless you publish a wrapper package.
