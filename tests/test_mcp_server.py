from __future__ import annotations

import asyncio
from pathlib import Path
from shutil import copyfile
from typing import Any

import pytest
from mcp.client import Client
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from safaribookmarks.mcp.server import build_server
from safaribookmarks.mcp.service import SafariBookmarksService

FIXTURE_PATH = Path(__file__).parent.joinpath("support", "fixtures")
BOOKMARKS_BINARY_PATH = FIXTURE_PATH.joinpath("Bookmarks.bin")


def _call_tool(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(server.call_tool(name=name, arguments=arguments)).structured_content


def _assert_refused(server: Any, name: str, arguments: dict[str, Any], reason: str) -> None:
    # UnexpectedToolError subclasses ToolError but hides the reason from the client.
    with pytest.raises(ToolError, match=reason) as excinfo:
        _call_tool(server, name, arguments)
    assert not isinstance(excinfo.value, UnexpectedToolError)


@pytest.fixture
def bookmarks_path(tmp_path: Path) -> Path:
    dest = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, dest)
    return dest


@pytest.fixture
def server(bookmarks_path: Path) -> Any:
    return build_server(path=str(bookmarks_path), confirm_write=True)


@pytest.fixture
def write_enabled_server(bookmarks_path: Path) -> Any:
    return build_server(path=str(bookmarks_path), confirm_write=True)


@pytest.fixture
def confirm_required_server(bookmarks_path: Path) -> Any:
    return build_server(path=str(bookmarks_path))


@pytest.fixture
def readonly_server(bookmarks_path: Path) -> Any:
    return build_server(path=str(bookmarks_path), readonly=True)


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
    _assert_refused(
        confirm_required_server,
        "remove_item",
        {"path": ["AB38D373-1266-495A-8CAC-422A771CF70A"], "dry_run": False},
        "Writes are disabled",
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
    _assert_refused(
        write_enabled_server,
        "snapshot",
        {"path": ["AB38D373-1266-495A-8CAC-422A771CF70A"], "recursive": True},
        "Target not found",
    )


def test_mcp_empty_folder_reports_child_count(write_enabled_server: Any) -> None:
    payload = _call_tool(
        write_enabled_server,
        "empty_folder",
        {"path": ["BookmarksBar"], "dry_run": True},
    )
    assert payload["status"] == "ok"
    assert payload["changed_count"] == 3


def test_mcp_readonly_blocks_write(readonly_server: Any) -> None:
    _assert_refused(
        readonly_server,
        "edit_item",
        {
            "path": ["AB38D373-1266-495A-8CAC-422A771CF70A"],
            "title": "No-op",
            "dry_run": False,
        },
        "Read-only mode is enabled",
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
    _assert_refused(
        server,
        "search_bookmarks",
        {"query": "   ", "path": ["BookmarksBar"]},
        "Query is required",
    )
    _assert_refused(
        server,
        "add_bookmark",
        {
            "path": ["BookmarksMenu"],
            "title": "Bad URL",
            "url": "not-a-url",
            "dry_run": True,
        },
        "URL must include a scheme",
    )
    _assert_refused(
        server,
        "add_folder",
        {
            "path": ["BookmarksMenu"],
            "title": "Bad ID",
            "id": "not-a-uuid",
            "dry_run": True,
        },
        "badly formed hexadecimal UUID string",
    )


def test_mcp_client_receives_refusal_reason(readonly_server: Any) -> None:
    async def call() -> Any:
        async with Client(readonly_server) as client:
            return await client.call_tool(
                "remove_item",
                {"path": ["AB38D373-1266-495A-8CAC-422A771CF70A"], "dry_run": False},
            )

    result = asyncio.run(call())
    assert result.is_error
    assert result.content[0].text == "Error executing tool remove_item: Read-only mode is enabled"


def test_mcp_client_sees_generic_message_for_crash(
    server: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(*_args: Any, **_kwargs: Any) -> None:
        raise KeyError("internal detail")

    monkeypatch.setattr(SafariBookmarksService, "snapshot", crash)

    with pytest.raises(UnexpectedToolError) as excinfo:
        _call_tool(server, "snapshot", {"path": None})
    assert "internal detail" not in str(excinfo.value)
