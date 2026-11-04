from __future__ import annotations

import os
from io import UnsupportedOperation
from typing import TYPE_CHECKING

from safaribookmarks.bookmarks import SafariBookmarkItem, SafariBookmarks

if TYPE_CHECKING:
    from pathlib import Path
    from typing import IO

DEFAULT_LIST_FORMAT = "{grey}{icon}{reset} {title: <50} {dark_grey}{id: <38}{cyan}{url}{reset}"
SIMPLE_FORMAT = "{grey}{icon}{reset} {title: <50} {cyan}{url}{reset}"
ICON_FIRST_LEAF = "┌"
ICON_MIDDLE_LEAF = "├"
ICON_LAST_LEAF = "└"
ICON_SINGLE_LEAF = "─"
ICON_LIST_CONTAINER = "│"

# Source: https://github.com/termcolor/termcolor/blob/main/src/termcolor/termcolor.py
COLORS: dict[str, int] = {
    "reset": 0,
    "black": 30,
    "grey": 30,
    "red": 31,
    "green": 32,
    "yellow": 33,
    "blue": 34,
    "magenta": 35,
    "cyan": 36,
    "light_grey": 37,
    "dark_grey": 90,
    "light_red": 91,
    "light_green": 92,
    "light_yellow": 93,
    "light_blue": 94,
    "light_magenta": 95,
    "light_cyan": 96,
    "white": 97,
}


class CLI:
    def __init__(self, path: str, out: IO[str]) -> None:
        self.bookmarks = SafariBookmarks.open(path)
        self.output = out
        self.colors = generate_colors(out)

    @property
    def path(self) -> Path | None:
        return self.bookmarks.path

    def run(self, command: str, **kwargs: object) -> None:
        if command is None:
            raise ValueError("No command specified")
        func = getattr(self, command, None)
        if command.startswith("_") or not callable(func):
            raise ValueError(f"Invalid command: {command}")
        func(**kwargs)

    def _resolve(self, path: list[str]) -> SafariBookmarkItem | None:
        return self.bookmarks.resolve_path(path)

    def _save(self) -> None:
        self.bookmarks.save()

    def _render_item(
        self,
        item: SafariBookmarkItem,
        item_format: str,
        depth: int = 0,
        icon: str = "",
    ) -> None:
        self.output.write(
            f"{item_format}\n".format(
                **self.colors,
                icon=icon,
                depth=depth,
                title=item.title.replace("\n", ""),
                type=item.type,
                url=item.url,
                id=item.id,
            )
        )
        if item.is_folder:
            self._render_children(item, item_format=item_format, depth=depth + 1)

    def _render_children(
        self,
        item: SafariBookmarkItem,
        item_format: str,
        depth: int = 0,
    ) -> None:
        last_index = len(item) - 1
        for index, child in enumerate(item):
            icon = ICON_LAST_LEAF if index == last_index else ICON_MIDDLE_LEAF
            if depth == 0 and index == 0:
                icon = ICON_FIRST_LEAF
            if depth == 0 and last_index == 0:
                icon = ICON_SINGLE_LEAF
            if depth > 0:
                icon = f"{ICON_LIST_CONTAINER * depth} {icon}"
            self._render_item(child, item_format, depth=depth, icon=icon)

    def _render(
        self,
        root: SafariBookmarkItem,
        item_format: str,
        only_children: bool = False,
        json: bool = False,
    ) -> None:
        if json:
            self.output.write(root.json())
        elif only_children:
            self._render_children(root, item_format=item_format)
        else:
            self._render_item(root, item_format=item_format)

    def list_bookmarks(
        self,
        path: list[str] | None = None,
        output_format: str | None = None,
        simple_format: bool = False,
        json: bool = False,
    ) -> None:
        path = path or []
        target = self._resolve(path)
        if target is None:
            raise ValueError("Target not found")
        if simple_format:
            output_format = SIMPLE_FORMAT
        elif output_format is None:
            output_format = DEFAULT_LIST_FORMAT
        self._render(
            target,
            only_children=target.is_folder,
            item_format=output_format,
            json=json,
        )

    def add(
        self,
        title: str | None,
        uuid: str | None = None,
        url: str | None = None,
        path: list[str] | None = None,
        folder: bool = False,
    ) -> None:
        path = path or []
        target = self._resolve(path)
        if target is None or not target.is_folder:
            raise ValueError("Invalid destination")
        if folder:
            if url is not None and url:
                raise ValueError("URL is not supported by lists")
            if title is None or not title:
                raise ValueError("Title is required")
            target.add_folder(title=title, bookmark_id=uuid)
        elif url is None:
            raise ValueError("URL is required")
        else:
            target.add_bookmark(url=url, bookmark_id=uuid, title=title)
        self._save()

    def remove(self, path: list[str]) -> None:
        target = self._resolve(path)
        if target is None:
            raise ValueError("Target not found")
        parent = target.parent
        if parent is not None:
            parent.remove(target)
        self._save()

    def move(self, path: list[str], to: list[str] | None = None) -> None:
        to = to or []
        target = self._resolve(path)
        if target is None:
            raise ValueError("Target not found")
        if not to:
            raise ValueError("Missing destination")
        dest = self._resolve(to)
        if dest is None or not dest.is_folder:
            raise ValueError("Invalid destination")
        current: SafariBookmarkItem | None = dest
        while current is not None:
            if current == target:
                raise ValueError("Invalid destination")
            current = current.parent
        dest.append(target)
        self._save()

    def edit(
        self,
        path: list[str],
        title: str | None = None,
        url: str | None = None,
    ) -> None:
        target = self._resolve(path)
        if target is None:
            raise ValueError("Target not found")
        if title is not None:
            target.title = title
        if url is not None:
            if not target.is_bookmark:
                raise ValueError("Cannot update target url")
            target.url = url
        self._save()

    def empty(self, path: list[str]) -> None:
        target = self._resolve(path)
        if target is None:
            raise ValueError("Target not found")
        if not target.is_folder:
            raise ValueError("Target is not a list")
        target.empty()
        self._save()


def generate_colors(output: IO[str]) -> dict[str, str]:
    if supports_colors(output):
        return {name: f"\033[{code}m" for name, code in COLORS.items()}
    return dict.fromkeys(COLORS.keys(), "")


def supports_colors(tty: IO[str]) -> bool:
    if (
        "ANSI_COLORS_DISABLED" in os.environ
        or "NO_COLOR" in os.environ
        or os.environ.get("TERM") == "dumb"
        or not hasattr(tty, "fileno")
    ):
        return False
    if "FORCE_COLOR" in os.environ:
        return True
    try:
        return os.isatty(tty.fileno())
    except UnsupportedOperation:
        return tty.isatty()
