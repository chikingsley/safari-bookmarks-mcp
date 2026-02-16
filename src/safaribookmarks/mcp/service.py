from pathlib import Path
from typing import Any

from safaribookmarks.safaribookmarks import SafariBookmarkItem, SafariBookmarks


class SafariBookmarksService:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._bookmarks = SafariBookmarks.open(self._path)

    @property
    def path(self) -> Path:
        return self._path

    def _reload(self) -> None:
        self._bookmarks = SafariBookmarks.open(self._path)

    def _resolve(self, path: list[str] | None = None) -> SafariBookmarkItem:
        path = path or []
        if len(path) == 1:
            item = self._bookmarks.get(path[0])
            if item is not None:
                return item
        item = self._bookmarks.walk(*path)
        if item is None:
            raise ValueError("Target not found")
        return item

    def _serialize(self, item: SafariBookmarkItem, *, recursive: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": item.id,
            "title": item.title,
            "type": item.type,
        }
        if item.is_bookmark:
            payload["url"] = item.url
        if item.is_folder:
            payload["child_count"] = len(item)
            if recursive:
                payload["children"] = [self._serialize(child, recursive=True) for child in item]
        return payload

    def _finalize(self, *, dry_run: bool) -> None:
        if dry_run:
            self._reload()
        else:
            self._bookmarks.save()

    def list_bookmarks(
        self, path: list[str] | None = None, *, recursive: bool = False
    ) -> list[dict[str, Any]]:
        item = self._resolve(path)
        if item.is_folder:
            return [self._serialize(child, recursive=recursive) for child in item]
        return [self._serialize(item, recursive=recursive)]

    def snapshot(self, path: list[str] | None = None, *, recursive: bool = True) -> dict[str, Any]:
        item = self._resolve(path)
        return self._serialize(item, recursive=recursive)

    def search_bookmarks(self, query: str, path: list[str] | None = None) -> list[dict[str, Any]]:
        query = query.strip().lower()
        if not query:
            raise ValueError("Query is required")
        target = self._resolve(path)

        matches: list[dict[str, Any]] = []

        def walk(item: SafariBookmarkItem) -> None:
            if query in item.title.lower() or (item.is_bookmark and query in item.url.lower()):
                matches.append(self._serialize(item, recursive=False))
            if item.is_folder:
                for child in item:
                    walk(child)

        walk(target)
        return matches

    def add_bookmark(
        self,
        path: list[str] | None,
        title: str | None,
        url: str,
        *,
        id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.is_folder:
            raise ValueError("Invalid destination")
        if not url:
            raise ValueError("URL is required")
        item = target.add_bookmark(url=url, title=title, id=id)
        result = self._serialize(item, recursive=True)
        self._finalize(dry_run=dry_run)
        return result

    def add_folder(
        self,
        path: list[str] | None,
        title: str | None,
        *,
        id: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.is_folder:
            raise ValueError("Invalid destination")
        if not title:
            raise ValueError("Title is required")
        item = target.add_folder(title=title, id=id)
        result = self._serialize(item, recursive=True)
        self._finalize(dry_run=dry_run)
        return result

    def remove(self, path: list[str], *, dry_run: bool = False) -> dict[str, Any]:
        target = self._resolve(path)
        if target is self._bookmarks:
            raise ValueError("Target not found")
        parent = target.parent
        if parent is None:
            raise ValueError("Target not found")
        parent.remove(target)
        result = self._serialize(target, recursive=True)
        self._finalize(dry_run=dry_run)
        return result

    def move(
        self,
        path: list[str],
        to: list[str] | None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if not to:
            raise ValueError("Missing destination")
        target = self._resolve(path)
        destination = self._resolve(to)
        if target is self._bookmarks:
            raise ValueError("Invalid source")
        if not destination.is_folder:
            raise ValueError("Invalid destination")
        current = destination
        while current is not None:
            if current is target:
                raise ValueError("Invalid destination")
            current = current.parent
        destination.append(target)
        result = self._serialize(target, recursive=True)
        self._finalize(dry_run=dry_run)
        return result

    def edit(
        self,
        path: list[str],
        title: str | None = None,
        url: str | None = None,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        target = self._resolve(path)
        if title is not None:
            target.title = title
        if url is not None:
            if not target.is_bookmark:
                raise ValueError("Cannot update target url")
            target.url = url
        result = self._serialize(target, recursive=True)
        self._finalize(dry_run=dry_run)
        return result

    def empty(self, path: list[str], *, dry_run: bool = False) -> dict[str, Any]:
        target = self._resolve(path)
        if not target.is_folder:
            raise ValueError("Target is not a list")
        target.empty()
        result = self._serialize(target, recursive=True)
        self._finalize(dry_run=dry_run)
        return result
