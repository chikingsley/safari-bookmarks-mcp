import json
import sys
from pathlib import Path

import pytest

from safaribookmarks.mcp.bootstrap import BootstrapOptions, bootstrap_mcp


def _project_root(tmp_path: Path) -> Path:
    project = tmp_path.joinpath("project")
    project.mkdir()
    return project


def test_bootstrap_mcp_local_scope_writes_supported_clients(tmp_path: Path):
    project = _project_root(tmp_path)
    home = tmp_path.joinpath("home")
    home.mkdir()
    bookmarks = tmp_path.joinpath("Bookmarks.plist")
    bookmarks.write_text("test", encoding="utf-8")
    lines = bootstrap_mcp(
        BootstrapOptions(
            file=str(bookmarks),
            mcp_command=(sys.executable,),
            clients=("claude", "opencode", "gemini"),
            scope="local",
            project_root=project,
            home=home,
            write=True,
        )
    )

    assert lines
    claude_path = project.joinpath(".mcp.json")
    opencode_path = project.joinpath("opencode.json")
    gemini_path = project.joinpath(".vscode", "mcp.json")

    claude_data = json.loads(claude_path.read_text(encoding="utf-8"))
    opencode_data = json.loads(opencode_path.read_text(encoding="utf-8"))
    gemini_data = json.loads(gemini_path.read_text(encoding="utf-8"))

    claude_entry = claude_data["mcpServers"]["safari-bookmarks"]
    opencode_entry = opencode_data["mcp"]["safari-bookmarks"]
    gemini_entry = gemini_data["mcpServers"]["safari-bookmarks"]

    assert claude_entry["command"] == sys.executable
    assert claude_entry["args"][-2:] == ["--file", str(bookmarks)]

    assert opencode_entry["command"] == sys.executable
    assert opencode_entry["args"][-2:] == ["--file", str(bookmarks)]

    assert gemini_entry["command"] == sys.executable
    assert gemini_entry["args"][-2:] == ["--file", str(bookmarks)]


def test_bootstrap_mcp_global_scope_and_manual_clients(tmp_path: Path):
    project = _project_root(tmp_path)
    home = tmp_path.joinpath("home")
    home.mkdir()
    xdg_config = home.joinpath(".config")
    bookmarks = tmp_path.joinpath("Bookmarks.plist")
    bookmarks.write_text("test", encoding="utf-8")
    lines = bootstrap_mcp(
        BootstrapOptions(
            file=str(bookmarks),
            mcp_command=(sys.executable,),
            clients=("opencode", "gemini", "claude", "codex"),
            scope="global",
            project_root=project,
            home=home,
            xdg_config_home=xdg_config,
            write=True,
        )
    )

    opencode_path = xdg_config.joinpath("opencode", "opencode.json")
    gemini_path = home.joinpath(".gemini", "settings.json")
    assert opencode_path.exists()
    assert gemini_path.exists()
    assert any("claude mcp add --transport stdio --scope user" in line for line in lines)
    assert any(
        "~/.codex/config.toml" in line or "[mcp_servers.safari-bookmarks]" in line for line in lines
    )


def test_bootstrap_mcp_invalid_inputs_raise(tmp_path: Path):
    project = _project_root(tmp_path)
    with pytest.raises(ValueError, match="Unsupported client"):
        bootstrap_mcp(
            BootstrapOptions(
                file="~/Bookmarks.plist",
                mcp_command=(sys.executable,),
                clients=("nope",),
                project_root=project,
            )
        )


def test_bootstrap_mcp_scope_local_for_codex_is_global_only(tmp_path: Path):
    project = _project_root(tmp_path)
    home = tmp_path.joinpath("home")
    home.mkdir()
    bookmarks = tmp_path.joinpath("Bookmarks.plist")
    bookmarks.write_text("test", encoding="utf-8")
    lines = bootstrap_mcp(
        BootstrapOptions(
            file=str(bookmarks),
            mcp_command=(sys.executable,),
            clients=("codex",),
            scope="local",
            project_root=project,
            home=home,
            write=True,
        )
    )
    assert any("shared/global MCP configuration" in line for line in lines)
