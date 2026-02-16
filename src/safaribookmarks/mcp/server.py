from argparse import ArgumentParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, ValidationError, field_validator, model_validator

from .service import SafariBookmarksService

FastMCP: Any | None = None
try:
    from mcp.server.fastmcp import FastMCP as _FastMCP
except ModuleNotFoundError:  # pragma: no cover
    pass
else:
    FastMCP = _FastMCP


def _build_service(path: str) -> SafariBookmarksService:
    return SafariBookmarksService(Path(path).expanduser())


def _normalize_uuid(value: str | None) -> str | None:
    if value is None:
        return None
    return str(UUID(value)).upper()


def _parse_payload(model: type[Any], payload: dict[str, Any]) -> Any:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field = ".".join(str(item) for item in first_error.get("loc", ()))
        raise ValueError(f"{field}: {first_error.get('msg', 'Invalid input')}") from exc


def _validate_path(path: list[str] | None, *, required: bool = False) -> list[str] | None:
    if path is None:
        if required:
            raise ValueError("Path is required")
        return None

    for segment in path:
        if not segment.strip():
            raise ValueError("Path segment cannot be empty")

    if required and not path:
        raise ValueError("Path is required")

    return path


def _validate_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("URL is required")
    if not urlparse(value).scheme:
        raise ValueError("URL must include a scheme")
    return value


def _result_payload(
    operation: str,
    *,
    result: dict[str, Any] | list[dict[str, Any]] | None,
    changed_ids: list[str] | tuple[str, ...],
    dry_run: bool,
    changed_count: int | None = None,
) -> dict[str, Any]:
    if changed_count is None:
        if isinstance(result, list):  # noqa: SIM108
            changed_count = len(result)
        else:
            changed_count = 0 if result is None else 1
    return {
        "status": "ok",
        "operation": operation,
        "result": result,
        "changed_count": changed_count,
        "changed_ids": list(changed_ids),
        "dry_run": dry_run,
    }


class _ListBookmarksRequest(BaseModel):
    path: list[str] | None = None
    recursive: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: list[str] | None) -> list[str] | None:
        return _validate_path(value)


class _SnapshotRequest(BaseModel):
    path: list[str] | None = None
    recursive: bool = True

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: list[str] | None) -> list[str] | None:
        return _validate_path(value)


class _SearchBookmarksRequest(BaseModel):
    query: str
    path: list[str] | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query is required")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: list[str] | None) -> list[str] | None:
        return _validate_path(value)


class _RequiredPathRequest(BaseModel):
    path: list[str]
    dry_run: bool = False

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: list[str]) -> list[str]:
        return _validate_path(value, required=True) or []


class _AddBookmarkRequest(_RequiredPathRequest):
    title: str | None = None
    url: str
    id: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_url(value)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        return _normalize_uuid(value)


class _AddFolderRequest(_RequiredPathRequest):
    title: str
    id: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title is required")
        return value

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str | None) -> str | None:
        return _normalize_uuid(value)


class _MoveItemRequest(BaseModel):
    path: list[str]
    to: list[str]
    dry_run: bool = False

    @field_validator("path", "to")
    @classmethod
    def validate_path(cls, value: list[str]) -> list[str]:
        return _validate_path(value, required=True) or []


class _EditItemRequest(_RequiredPathRequest):
    title: str | None = None
    url: str | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_url(value)

    @model_validator(mode="after")
    def validate_payload(self) -> "_EditItemRequest":
        if self.title is None and self.url is None:
            raise ValueError("title or url is required")
        return self


def build_server(
    path: str,
    *,
    readonly: bool = False,
    confirm_write: bool = False,
) -> Any:
    if FastMCP is None:  # pragma: no cover
        raise RuntimeError("Install safari-bookmarks-mcp[mcp] to run the MCP server")

    service = _build_service(path)
    mcp = FastMCP("safari-bookmarks")

    def _require_write_permission(*, dry_run: bool) -> None:
        if dry_run:
            return
        if readonly:
            raise ValueError("Read-only mode is enabled")
        if not confirm_write:
            raise ValueError("Writes are disabled. Use --confirm-write or pass dry_run=True.")

    @mcp.tool()
    def list_bookmarks(path: list[str] | None = None, *, recursive: bool = False) -> dict[str, Any]:
        request = _parse_payload(_ListBookmarksRequest, {"path": path, "recursive": recursive})
        result = service.list_bookmarks(path=request.path, recursive=request.recursive)
        return _result_payload(
            "list_bookmarks",
            result=result,
            changed_ids=[item["id"] for item in result],
            dry_run=False,
            changed_count=len(result),
        )

    @mcp.tool()
    def snapshot(path: list[str] | None = None, *, recursive: bool = True) -> dict[str, Any]:
        request = _parse_payload(_SnapshotRequest, {"path": path, "recursive": recursive})
        result = service.snapshot(path=request.path, recursive=request.recursive)
        return _result_payload(
            "snapshot",
            result=result,
            changed_ids=[result["id"]],
            dry_run=False,
            changed_count=1,
        )

    @mcp.tool()
    def search_bookmarks(query: str, path: list[str] | None = None) -> dict[str, Any]:
        request = _parse_payload(_SearchBookmarksRequest, {"query": query, "path": path})
        result = service.search_bookmarks(query=request.query, path=request.path)
        return _result_payload(
            "search_bookmarks",
            result=result,
            changed_ids=[item["id"] for item in result],
            dry_run=False,
            changed_count=len(result),
        )

    @mcp.tool()
    def add_bookmark(
        path: list[str] | None,
        title: str | None,
        url: str,
        *,
        id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        request = _parse_payload(
            _AddBookmarkRequest,
            {
                "path": path or [],
                "title": title,
                "url": url,
                "id": id,
                "dry_run": dry_run,
            },
        )
        _require_write_permission(dry_run=request.dry_run)
        result = service.add_bookmark(
            path=request.path,
            title=request.title,
            url=request.url,
            id=request.id,
            dry_run=request.dry_run,
        )
        return _result_payload(
            "add_bookmark",
            result=result,
            changed_ids=[result["id"]],
            dry_run=request.dry_run,
            changed_count=1,
        )

    @mcp.tool()
    def add_folder(
        path: list[str] | None,
        title: str,
        *,
        id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        request = _parse_payload(
            _AddFolderRequest,
            {
                "path": path or [],
                "title": title,
                "id": id,
                "dry_run": dry_run,
            },
        )
        _require_write_permission(dry_run=request.dry_run)
        result = service.add_folder(
            path=request.path,
            title=request.title,
            id=request.id,
            dry_run=request.dry_run,
        )
        return _result_payload(
            "add_folder",
            result=result,
            changed_ids=[result["id"]],
            dry_run=request.dry_run,
            changed_count=1,
        )

    @mcp.tool()
    def move_item(
        path: list[str],
        to: list[str],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        request = _parse_payload(
            _MoveItemRequest,
            {"path": path, "to": to, "dry_run": dry_run},
        )
        _require_write_permission(dry_run=request.dry_run)
        result = service.move(
            path=request.path,
            to=request.to,
            dry_run=request.dry_run,
        )
        return _result_payload(
            "move_item",
            result=result,
            changed_ids=[result["id"]],
            dry_run=request.dry_run,
            changed_count=1,
        )

    @mcp.tool()
    def remove_item(
        path: list[str],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        request = _parse_payload(_RequiredPathRequest, {"path": path, "dry_run": dry_run})
        _require_write_permission(dry_run=request.dry_run)
        result = service.remove(path=request.path, dry_run=request.dry_run)
        return _result_payload(
            "remove_item",
            result=result,
            changed_ids=[result["id"]],
            dry_run=request.dry_run,
            changed_count=1,
        )

    @mcp.tool()
    def edit_item(
        path: list[str],
        title: str | None = None,
        url: str | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        request = _parse_payload(
            _EditItemRequest,
            {
                "path": path,
                "title": title,
                "url": url,
                "dry_run": dry_run,
            },
        )
        _require_write_permission(dry_run=request.dry_run)
        result = service.edit(
            path=request.path,
            title=request.title,
            url=request.url,
            dry_run=request.dry_run,
        )
        return _result_payload(
            "edit_item",
            result=result,
            changed_ids=[result["id"]],
            dry_run=request.dry_run,
            changed_count=1,
        )

    @mcp.tool()
    def empty_folder(
        path: list[str],
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        request = _parse_payload(_RequiredPathRequest, {"path": path, "dry_run": dry_run})
        _require_write_permission(dry_run=request.dry_run)
        before = service.snapshot(path=request.path, recursive=False)
        child_count = len(before.get("children", []))
        result = service.empty(path=request.path, dry_run=request.dry_run)
        return _result_payload(
            "empty_folder",
            result=result,
            changed_ids=[result["id"]],
            dry_run=request.dry_run,
            changed_count=child_count,
        )

    return mcp


def main() -> None:
    parser = ArgumentParser(
        prog="safari-bookmarks-mcp",
        description="Start an MCP server for Safari bookmarks.",
    )
    parser.add_argument(
        "--file",
        "-f",
        default="~/Library/Safari/Bookmarks.plist",
        help="The path to the Safari bookmarks file.",
    )
    parser.add_argument(
        "--readonly",
        action="store_true",
        help="Start in read-only mode. Mutating operations are blocked.",
    )
    parser.add_argument(
        "--confirm-write",
        action="store_true",
        help=(
            "Allow write operations when dry_run is False. "
            "Without this flag, write tools require dry_run=True."
        ),
    )
    args = parser.parse_args()
    server = build_server(
        path=args.file,
        readonly=args.readonly,
        confirm_write=args.confirm_write,
    )
    server.run()
