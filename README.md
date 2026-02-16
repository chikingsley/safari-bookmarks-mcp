# safari-bookmarks-mcp

A CLI and MCP server to manage bookmarks in the Safari web browser.

This utility interacts with Safari's `Bookmarks.plist` file. When it detects changes it is reloaded without intervention.

**Note** macOS 10.14+ requires Full Disk Access for the application being used. ie. Terminal, iTerm, etc.

## Installation

You can install safari-bookmarks-mcp with uv:

```shell
uv tool install safari-bookmarks-mcp

# verify installation
safari-bookmarks --version
```

Install `just` (optional, for dev flows) from https://just.systems (for example `brew install just`) if you want one-command setup tasks.

## Development with `just`

`justfile` is the recommended workflow for local development:

```shell
just setup    # create .venv and install test/lint/type-check deps
just check    # ruff + ty + pytest
```

MCP-specific helpers:

```shell
just mcp-deps
just mcp-bootstrap-local
just mcp-bootstrap-global
just mcp-bootstrap-both
```

## Usage

The following assumes the default location for Safari's bookmarks, which is `~/Library/Safari/Bookmarks.plist`. If this is not the case you can specify an alternate location by passing the arguments `-f <elsewhere>`.

For a full list of commands and options just run:

```shell
safari-bookmarks --help
```

### To list all bookmarks run

```shell
safari-bookmarks list
```

### To list all bookmarks in the menubar

```shell
safari-bookmarks list "BookmarksMenu"
```

### Add a new bookmark to the menubar

```shell
safari-bookmarks add --title "New bookmark" --url "http://example.com" "BookmarksMenu"
```

### Add a new bookmark to the menu

```shell
safari-bookmarks add --title "New folder" --list "BookmarksBar"
```

### Move a bookmark to a different folder

```shell
safari-bookmarks move "BookmarksMenu" "New bookmark" --to "BookmarksBar" "New folder"
```

### Remove a bookmark or folder

**Note** removing a folder will also remove all bookmarks and folders within it.

```shell
safari-bookmarks remove "BookmarksBar" "New folder"
```

### Empty a folder

```shell
safari-bookmarks empty "BookmarksBar" "New folder"
```

## MCP server

You can run an MCP (Model Context Protocol) server for LLM tooling:

```shell
uv sync --extra mcp
safari-bookmarks-mcp --file ~/Library/Safari/Bookmarks.plist
```

The server currently exposes tools for:
- `list_bookmarks`
- `snapshot`
- `search_bookmarks`
- `add_bookmark`
- `add_folder`
- `move_item`
- `remove_item`
- `edit_item`
- `empty_folder`

Write tools accept `dry_run=True` to validate intent and return the proposed change without saving.
By default, the server requires `--confirm-write` before any tool with `dry_run=False` is executed.

You can also run the server as read-only:

```shell
safari-bookmarks-mcp --readonly --file ~/Library/Safari/Bookmarks.plist
```

```shell
safari-bookmarks-mcp --confirm-write --file ~/Library/Safari/Bookmarks.plist
```

Each MCP tool now returns a structured payload:

```json
{
  "status": "ok",
  "operation": "search_bookmarks",
  "result": [],
  "changed_count": 2,
  "changed_ids": ["..."],
  "dry_run": true
}
```

Use `path` arguments as a UUID or bookmark/title path stack, matching existing CLI resolution semantics (title segments are resolved depth-first, UUIDs are exact).

## MCP client bootstrap setup

You can generate and apply MCP configuration for common clients:

```shell
safari-bookmarks bootstrap --client claude --client opencode --scope local --write
safari-bookmarks bootstrap --client gemini --scope global --write
```

Select one or more clients with repeated `--client` flags:

- `claude`
- `opencode`
- `codex`
- `gemini`

### Client prerequisites

`bootstrap` writes config files and/or command snippets; it does not install external MCP clients.

Required for this package:

- `safari-bookmarks-mcp` on your `PATH` (install this package with MCP extras):

```shell
uv sync --extra mcp
```

Or test directly in-tree:

```shell
uv run safari-bookmarks-mcp --help
```

For client-side setup, ensure each client executable you target is installed and on PATH:

- `claude` for Claude Code
- `opencode` for OpenCode
- `gemini` for Gemini
- Codex reads from `~/.codex/config.toml` (no separate client binary required beyond your existing Codex CLI).

Scope controls where the config is written:

- `--scope local`: writes project-scoped config files (`.mcp.json`, `opencode.json`, `.vscode/mcp.json`).
- `--scope global`: writes user-scoped files where supported, and prints manual commands/snippets for others.
- `--scope both`: performs both local and global options.

For safety, use plan-only mode first:

```shell
safari-bookmarks bootstrap --client claude --scope local
```

Then pass `--write` to apply.

Notes:

- Claude Code user-scope setup is printed as a command (`claude mcp add ... --scope user`) because that path is managed by the CLI and may vary by version.
- Codex currently supports shared MCP config in `~/.codex/config.toml`; scope is therefore treated as global only.

Also, `npx`/`bunx` are for JavaScript packages. `safari-bookmarks` is a Python package, so they only work if you publish a dedicated Node wrapper.
For local Python execution, use `safari-bookmarks-mcp` directly or `uv run python -m safaribookmarks.mcp.server`/`uv run safari-bookmarks-mcp`.

## Testing

Clone the repository:

```shell
git clone https://github.com/evilmarty/safari-bookmarks-mcp.git
```

Install test/lint/type-check deps:

```shell
uv sync --extra tests
```

Run tests, lint, and type checks:

```shell
just check
```

Using uv:

```shell
uv sync
uv run ruff check src tests && uv run ty check src tests && uv run pytest
```
