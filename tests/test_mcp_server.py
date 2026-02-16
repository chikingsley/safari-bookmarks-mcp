import asyncio
from pathlib import Path
from shutil import copyfile
from typing import Any

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from safaribookmarks.mcp.server import FastMCP, build_server

if FastMCP is None:  # pragma: no cover
    pytest.skip("mcp dependency is not installed", allow_module_level=True)

FIXTURE_PATH = Path(__file__).parent.joinpath("support", "fixtures")
BOOKMARKS_BINARY_PATH = FIXTURE_PATH.joinpath("Bookmarks.bin")


def _call_tool(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    _, payload = asyncio.run(server.call_tool(name=name, arguments=arguments))
    return payload


def _call_tool_raw(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(server.call_tool(name=name, arguments=arguments))


@pytest.fixture()
def bookmarks_path(tmp_path: Path) -> Path:
    dest = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, dest)
    return dest


@pytest.fixture()
def server(bookmarks_path: Path):
    return build_server(path=str(bookmarks_path), confirm_write=True)


@pytest.fixture()
def write_enabled_server(bookmarks_path: Path):
    return build_server(path=str(bookmarks_path), confirm_write=True)


@pytest.fixture()
def confirm_required_server(bookmarks_path: Path):
    return build_server(path=str(bookmarks_path))


@pytest.fixture()
def readonly_server(bookmarks_path: Path):
    return build_server(path=str(bookmarks_path), readonly=True)


def test_mcp_tools_registered(server: Any) -> None:
    tools = {tool.name for tool in server._tool_manager.list_tools()}
    assert tools == {
        "add_bookmark",
        "add_folder",
        "edit_item",
        "empty_folder",
        "list_bookmarks",
        "move_item",
        "remove_item",
        "search_bookmarks",
        "snapshot",
    }


def test_mcp_list_returns_envelope(server: Any) -> None:
    result = _call_tool(server, "list_bookmarks", {"path": None, "recursive": False})
    assert result["status"] == "ok"
    assert result["operation"] == "list_bookmarks"
    assert result["changed_count"] == 4
    assert result["changed_ids"] == [
        "7551D1F4-38C1-4DB3-88AC-90C15F10338D",
        "3B5180DB-831D-4F1A-AE4A-6482D28D66D5",
        "20ABDC16-B491-47F4-B252-2A3065CFB895",
        "E3B5B464-B6D2-457C-9F62-7B2316F7EF20",
    ]


def test_mcp_path_resolution_by_uuid_and_title(server: Any) -> None:
    by_uuid = _call_tool(
        server,
        "snapshot",
        {"path": ["AB38D373-1266-495A-8CAC-422A771CF70A"], "recursive": True},
    )
    by_title = _call_tool(
        server,
        "snapshot",
        {"path": ["BookmarksBar", "Safari"], "recursive": True},
    )

    assert by_uuid["result"]["id"] == by_title["result"]["id"]


def test_mcp_add_folder_and_dry_run(server: Any) -> None:
    payload = _call_tool(
        server,
        "add_folder",
        {
            "path": ["BookmarksMenu"],
            "title": "MCP folder",
            "dry_run": True,
            "id": "11111111-2222-3333-4444-555555555555",
        },
    )
    assert payload["status"] == "ok"
    assert payload["dry_run"]
    assert payload["result"]["title"] == "MCP folder"
    assert payload["changed_count"] == 1


def test_mcp_remove_respects_dry_run(server: Any, bookmarks_path: Path) -> None:
    original = bookmarks_path.read_bytes()
    payload = _call_tool(
        server,
        "remove_item",
        {"path": ["AB38D373-1266-495A-8CAC-422A771CF70A"], "dry_run": True},
    )

    assert payload["status"] == "ok"
    assert payload["changed_ids"] == ["AB38D373-1266-495A-8CAC-422A771CF70A"]
    assert bookmarks_path.read_bytes() == original


def test_mcp_remove_without_confirmation_fails(confirm_required_server: Any) -> None:
    with pytest.raises(ToolError):
        _call_tool_raw(
            confirm_required_server,
            "remove_item",
            {"path": ["AB38D373-1266-495A-8CAC-422A771CF70A"], "dry_run": False},
        )


def test_mcp_remove_with_confirmation_persists(write_enabled_server: Any) -> None:
    payload = _call_tool(
        write_enabled_server,
        "remove_item",
        {
            "path": ["AB38D373-1266-495A-8CAC-422A771CF70A"],
            "dry_run": False,
        },
    )
    assert payload["changed_ids"] == ["AB38D373-1266-495A-8CAC-422A771CF70A"]
    with pytest.raises(ToolError):
        _call_tool_raw(
            write_enabled_server,
            "snapshot",
            {
                "path": ["AB38D373-1266-495A-8CAC-422A771CF70A"],
                "recursive": True,
            },
        )


def test_mcp_readonly_blocks_write(readonly_server: Any) -> None:
    with pytest.raises(ToolError):
        _call_tool_raw(
            readonly_server,
            "edit_item",
            {
                "path": ["AB38D373-1266-495A-8CAC-422A771CF70A"],
                "title": "No-op",
                "dry_run": False,
            },
        )

    payload = _call_tool(
        readonly_server,
        "edit_item",
        {
            "path": ["AB38D373-1266-495A-8CAC-422A771CF70A"],
            "title": "Preview",
            "dry_run": True,
        },
    )
    assert payload["status"] == "ok"


def test_mcp_validation_rules_enforced(server: Any) -> None:
    with pytest.raises(ToolError):
        _call_tool_raw(
            server,
            "search_bookmarks",
            {"query": "   ", "path": ["BookmarksBar"]},
        )

    with pytest.raises(ToolError):
        _call_tool_raw(
            server,
            "add_bookmark",
            {
                "path": ["BookmarksMenu"],
                "title": "Bad URL",
                "url": "not-a-url",
                "dry_run": True,
            },
        )

    with pytest.raises(ToolError):
        _call_tool_raw(
            server,
            "add_folder",
            {
                "path": ["BookmarksMenu"],
                "title": "Bad ID",
                "id": "not-a-uuid",
                "dry_run": True,
            },
        )
