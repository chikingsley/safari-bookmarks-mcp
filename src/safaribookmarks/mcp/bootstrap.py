"""Helpers for generating MCP client bootstrap snippets and configuration files."""

from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Any

MCP_SERVER_NAME = "safari-bookmarks"
SUPPORTED_CLIENTS = ("claude", "opencode", "codex", "gemini")


@dataclass(frozen=True)
class BootstrapOptions:
    file: str
    mcp_command: tuple[str, ...] = ("safari-bookmarks-mcp",)
    clients: tuple[str, ...] | list[str] | None = None
    scope: str = "local"
    project_root: Path | None = None
    home: Path | None = None
    xdg_config_home: Path | None = None
    write: bool = False
    server_name: str = MCP_SERVER_NAME


@dataclass(frozen=True)
class MCPServerConfig:
    path: Path
    section: str
    server_name: str
    entry: dict[str, Any]


def _coerce_command(command: tuple[str, ...] | list[str] | str) -> tuple[str, ...]:
    if isinstance(command, str):
        return (command,)
    return tuple(command)


def _resolve_command(command: str) -> str:
    if which(command) is None and not Path(command).exists():
        raise ValueError(f"Could not locate MCP command: {command}")
    return command


def _expand_path(path: str) -> str:
    return str(Path(path).expanduser())


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON at {path}") from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_client_entry(
    path: Path,
    section: str,
    server_name: str,
    entry: dict[str, Any],
) -> None:
    data = _load_json(path)
    section_payload = data.get(section)
    if not isinstance(section_payload, dict):
        section_payload = {}
    section_payload[server_name] = entry
    data[section] = section_payload
    _write_json(path, data)


def _normalize_clients(clients: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not clients:
        return SUPPORTED_CLIENTS
    selected = [client.strip().lower() for client in clients if isinstance(client, str)]
    unknown = [client for client in selected if client not in SUPPORTED_CLIENTS]
    if unknown:
        raise ValueError(
            f"Unsupported client(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(SUPPORTED_CLIENTS)}"
        )
    return tuple(dict.fromkeys(selected))


def _append_plan_instruction(
    instructions: list[str],
    config: MCPServerConfig,
    command_line: str,
    scope: str,
    *,
    write: bool,
) -> None:
    instructions.append(f"[{scope}] Configure {config.path}")
    if write:
        _write_client_entry(
            config.path,
            config.section,
            config.server_name,
            config.entry,
        )
        instructions.append(f"  - wrote {config.path} with command: {command_line}")
    else:
        instructions.append(
            f"  - add '{config.server_name}' under '{config.section}' in {config.path}"
        )


def _build_local_specs(
    server_entry: dict[str, Any],
    server_name: str,
    project_root: Path,
    selected: tuple[str, ...],
) -> list[MCPServerConfig]:
    configs: list[MCPServerConfig] = []
    if "claude" in selected:
        configs.append(
            MCPServerConfig(
                path=project_root / ".mcp.json",
                section="mcpServers",
                server_name=server_name,
                entry=server_entry | {"env": {}},
            )
        )
    if "opencode" in selected:
        configs.append(
            MCPServerConfig(
                path=project_root / "opencode.json",
                section="mcp",
                server_name=server_name,
                entry={
                    "type": "local",
                    "command": server_entry["command"],
                    "args": server_entry["args"],
                    "environment": {},
                    "enabled": True,
                },
            )
        )
    if "gemini" in selected:
        configs.append(
            MCPServerConfig(
                path=project_root / ".vscode" / "mcp.json",
                section="mcpServers",
                server_name=server_name,
                entry={"command": server_entry["command"], "args": server_entry["args"]},
            )
        )
    return configs


def _build_global_specs(
    server_entry: dict[str, Any],
    server_name: str,
    home: Path,
    xdg_config_home: Path,
    selected: tuple[str, ...],
) -> list[MCPServerConfig]:
    configs: list[MCPServerConfig] = []
    if "opencode" in selected:
        configs.append(
            MCPServerConfig(
                path=xdg_config_home / "opencode" / "opencode.json",
                section="mcp",
                server_name=server_name,
                entry={
                    "type": "local",
                    "command": server_entry["command"],
                    "args": server_entry["args"],
                    "environment": {},
                    "enabled": True,
                },
            )
        )
    if "gemini" in selected:
        configs.append(
            MCPServerConfig(
                path=home / ".gemini" / "settings.json",
                section="mcpServers",
                server_name=server_name,
                entry={"command": server_entry["command"], "args": server_entry["args"]},
            )
        )
    return configs


def bootstrap_mcp(options: BootstrapOptions) -> list[str]:
    scope = options.scope
    if scope not in {"local", "global", "both"}:
        raise ValueError("scope must be local, global, or both")

    home = options.home or Path.home()
    project_root = options.project_root or Path.cwd()
    xdg_config_home = options.xdg_config_home or Path(
        os.environ.get("XDG_CONFIG_HOME", str(home / ".config"))
    )
    mcp_command = _coerce_command(options.mcp_command)
    server_name = options.server_name

    selected = _normalize_clients(options.clients)
    has_claude = "claude" in selected
    has_codex = "codex" in selected

    resolved_command = tuple(_resolve_command(cmd) for cmd in mcp_command)
    server_command = (*resolved_command, "--file", _expand_path(options.file))
    command_line = shlex.join(server_command)
    instructions: list[str] = []

    server_entry = {
        "type": "stdio",
        "command": server_command[0],
        "args": list(server_command[1:]),
    }

    local_specs = _build_local_specs(
        server_entry=server_entry,
        server_name=server_name,
        project_root=project_root,
        selected=selected,
    )
    global_specs = _build_global_specs(
        server_entry=server_entry,
        server_name=server_name,
        home=home,
        xdg_config_home=xdg_config_home,
        selected=selected,
    )

    if has_claude and scope in {"global", "both"}:
        instructions.append("[global] Configure Claude Code (user scope) via CLI:")
        instructions.append(
            f"  - claude mcp add --transport stdio --scope user {server_name} -- {command_line}"
        )

    if has_codex:
        if scope == "local":
            instructions.append(
                "[local] Configure Codex only supports shared/global MCP "
                "configuration in ~/.codex/config.toml"
            )
        else:
            instructions.append("[global] Configure Codex in ~/.codex/config.toml")
            instructions.append(
                "  - add the section below to your config file:\n"
                f"    [mcp_servers.{server_name}]\n"
                f'    command = "{server_entry["command"]}"\n'
                f"    args = {json.dumps(server_entry['args'])}"
            )

    if scope in {"local", "both"}:
        for config in local_specs:
            _append_plan_instruction(
                instructions,
                config,
                command_line=command_line,
                scope="local",
                write=options.write,
            )

    if scope in {"global", "both"}:
        for config in global_specs:
            _append_plan_instruction(
                instructions,
                config,
                command_line=command_line,
                scope="global",
                write=options.write,
            )

    if not instructions:
        instructions.append("No MCP clients selected.")

    return instructions
