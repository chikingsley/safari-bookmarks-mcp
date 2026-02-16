import builtins
import os
from io import UnsupportedOperation
from pathlib import Path
from typing import IO

from safaribookmarks.safaribookmarks import SafariBookmarkItem, SafariBookmarks

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
    def __init__(self, path: str, out: IO) -> None:
        self.bookmarks = SafariBookmarks.open(path)
        self.output = out
        self.colors = generate_colors(out)

    @property
    def path(self) -> Path | None:
        return self.bookmarks.path

    def run(self, command: str, **kwargs) -> None:
        if command is None:
            raise ValueError("No command specified")
        func = getattr(self, command, None)
        if command.startswith("_") or not callable(func):
            raise ValueError(f"Invalid command: {command}")
        func(**kwargs)

    def _get_or_walk(self, path: builtins.list[str]) -> SafariBookmarkItem | None:
        if len(path) == 1:
            result = self.bookmarks.get(path[0])
            if result is not None:
                return result
        return self.bookmarks.walk(*path)

    def _save(self) -> None:
        self.bookmarks.save()

    def _render_item(self, item: SafariBookmarkItem, format: str, depth: int = 0, icon: str = ""):
        self.output.write(
            f"{format}\n".format(
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
            self._render_children(item, format=format, depth=depth + 1)

    def _render_children(self, item: SafariBookmarkItem, format: str, depth: int = 0):
        last_index = len(item) - 1
        for index, child in enumerate(item):
            icon = ICON_LAST_LEAF if index == last_index else ICON_MIDDLE_LEAF
            if depth == 0 and index == 0:
                icon = ICON_FIRST_LEAF
            if depth == 0 and last_index == 0:
                icon = ICON_SINGLE_LEAF
            if depth > 0:
                icon = f"{ICON_LIST_CONTAINER * depth} {icon}"
            self._render_item(child, format, depth=depth, icon=icon)

    def _render(
        self,
        root: SafariBookmarkItem,
        format: str,
        only_children=False,
        json=False,
    ):
        if json:
            self.output.write(root.json())
        elif only_children:
            self._render_children(root, format=format)
        else:
            self._render_item(root, format=format)

    def list(
        self,
        path: builtins.list[str] | None = None,
        format: str | None = None,
        simple_format=False,
        json=False,
    ):
        path = path or []
        target = self._get_or_walk(path)
        if target is None:
            raise ValueError("Target not found")
        if simple_format:
            format = SIMPLE_FORMAT
        elif format is None:
            format = DEFAULT_LIST_FORMAT
        self._render(target, only_children=target.is_folder, format=format, json=json)

    def add(
        self,
        title: str | None,
        uuid: str | None = None,
        url: str | None = None,
        path: builtins.list[str] | None = None,
        list=False,
    ):
        path = path or []
        target = self._get_or_walk(path)
        if target is None or not target.is_folder:
            raise ValueError("Invalid destination")
        if list:
            if url:
                raise ValueError("URL is not supported by lists")
            if not title:
                raise ValueError("Title is required")
            target.add_folder(title=title, id=uuid)
        elif url is None:
            raise ValueError("URL is required")
        else:
            target.add_bookmark(url=url, id=uuid, title=title)
        self._save()

    def remove(self, path: builtins.list[str]):
        target = self._get_or_walk(path)
        if target is None:
            raise ValueError("Target not found")
        if parent := target.parent:
            parent.remove(target)
        self._save()

    def move(self, path: builtins.list[str], to: builtins.list[str] | None = None):
        to = to or []
        target = self._get_or_walk(path)
        if target is None:
            raise ValueError("Target not found")
        if not to:
            raise ValueError("Missing destination")
        dest = self._get_or_walk(to)
        if dest is None or not dest.is_folder:
            raise ValueError("Invalid destination")
        dest.append(target)
        self._save()

    def edit(
        self,
        path: builtins.list[str],
        title: str | None = None,
        url: str | None = None,
    ):
        target = self._get_or_walk(path)
        if target is None:
            raise ValueError("Target not found")
        if title is not None:
            target.title = title
        if url is not None:
            if not target.is_bookmark:
                raise ValueError("Cannot update target url")
            target.url = url
        self._save()

    def empty(self, path: builtins.list[str]):
        target = self._get_or_walk(path)
        if target is None:
            raise ValueError("Target not found")
        if not target.is_folder:
            raise ValueError("Target is not a list")
        target.empty()
        self._save()


def generate_colors(output: IO) -> dict[str, str]:
    if supports_colors(output):
        return {name: f"\033[{code}m" for name, code in COLORS.items()}
    return dict.fromkeys(COLORS.keys(), "")


def supports_colors(tty: IO) -> bool:
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
