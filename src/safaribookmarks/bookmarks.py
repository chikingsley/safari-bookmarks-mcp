from __future__ import annotations

import base64
import json as json_module
import os
import plistlib
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import TracebackType
    from typing import IO, Self

from .models import (
    WebBookmarkType,
    WebBookmarkTypeLeaf,
    WebBookmarkTypeList,
    WebBookmarkTypeProxy,
)


class SafariBookmarkItem:
    __slots__ = ("_node", "_parent")

    def __init__(
        self,
        node: WebBookmarkType,
        parent: SafariBookmarkItem | None = None,
    ) -> None:
        if not getattr(parent, "is_folder", True):
            raise ValueError("Parent must be a folder")
        self._node = node
        self._parent = parent

    @override
    def __str__(self) -> str:
        return self.title

    @override
    def __repr__(self) -> str:
        return repr(self._node)

    def __len__(self) -> int:
        return len(self.children)

    def __bool__(self) -> bool:
        return True

    @override
    def __hash__(self) -> int:
        return hash(self._node)

    def __iter__(self) -> Iterator[SafariBookmarkItem]:
        for child in getattr(self._node, "children", []):
            yield SafariBookmarkItem(
                node=child,
                parent=self,
            )

    def __contains__(self, other: object) -> bool:
        return any(child == other for child in self)

    @override
    def __eq__(self, value: object) -> bool:
        return type(self) is type(value) and self._node == getattr(value, "_node", None)

    def __getitem__(self, key: str | tuple[str, ...]) -> SafariBookmarkItem:
        if isinstance(key, tuple):
            item = self
            for x in key:
                item = item[x]
            return item
        if not isinstance(key, str):
            raise TypeError(type(key).__name__)
        for child in self:
            if key in {child.id, child.title}:
                return child
        raise KeyError(key)

    @property
    def movable(self) -> bool:
        return self.is_bookmark or self.is_folder

    @property
    def is_bookmark(self) -> bool:
        return isinstance(self._node, WebBookmarkTypeLeaf)

    @property
    def is_folder(self) -> bool:
        return isinstance(self._node, WebBookmarkTypeList)

    @property
    def type(self) -> str:
        if isinstance(self._node, WebBookmarkTypeProxy):
            return "proxy"
        if self.is_bookmark:
            return "bookmark"
        if self.is_folder:
            return "folder"
        return ""

    @property
    def id(self) -> str:
        return self._node.web_bookmark_uuid

    @property
    def title(self) -> str:
        if isinstance(
            self._node,
            (WebBookmarkTypeProxy, WebBookmarkTypeList, WebBookmarkTypeLeaf),
        ):
            return self._node.title
        return ""

    @title.setter
    def title(self, title: str) -> None:
        if isinstance(
            self._node,
            (WebBookmarkTypeProxy, WebBookmarkTypeList, WebBookmarkTypeLeaf),
        ):
            self._node.title = title

    @property
    def url(self) -> str:
        if isinstance(self._node, WebBookmarkTypeLeaf):
            return self._node.url_string
        return ""

    @url.setter
    def url(self, url: str) -> None:
        if isinstance(self._node, WebBookmarkTypeLeaf):
            self._node.url_string = url

    @property
    def children(self) -> list[SafariBookmarkItem]:
        return list(iter(self))

    @property
    def parent(self) -> SafariBookmarkItem | None:
        return self._parent

    def get(self, bookmark_id: str) -> SafariBookmarkItem | None:
        if self.id.lower() == bookmark_id.lower():
            return self
        for child in self:
            result = child.get(bookmark_id)
            if result is not None:
                return result
        return None

    def walk(self, *titles: str) -> SafariBookmarkItem | None:
        if len(titles) == 0:
            return self
        title = titles[0]
        for child in self:
            if child.title == title:
                return child.walk(*titles[1:])
        return None

    def resolve_path(self, path: list[str] | None = None) -> SafariBookmarkItem | None:
        path = path or []
        if len(path) == 1:
            item = self.get(path[0])
            if item is not None:
                return item
        return self.walk(*path)

    def remove(self, item: SafariBookmarkItem) -> None:
        if item not in self:
            raise RuntimeError("Not a child")
        if not item.movable:
            raise RuntimeError("Invalid item")
        getattr(self._node, "children", []).remove(item._node)
        item._parent = None

    def empty(self) -> None:
        getattr(self._node, "children", []).clear()

    def append(self, item: SafariBookmarkItem) -> None:
        if not self.is_folder:
            raise RuntimeError("Not a folder")
        if not item.movable:
            raise RuntimeError("Invalid item")
        if item in self:
            return
        parent = item.parent
        if parent is not None:
            parent.remove(item)
        getattr(self._node, "children", []).append(item._node)
        item._parent = self

    def add_bookmark(
        self, url: str, title: str | None = None, bookmark_id: str | None = None
    ) -> SafariBookmarkItem:
        uri_dictionary = {"title": title} if title is not None else {}
        leaf = WebBookmarkTypeLeaf(URLString=url, URIDictionary=uri_dictionary)
        if bookmark_id is not None:
            leaf.web_bookmark_uuid = bookmark_id
        item = SafariBookmarkItem(node=leaf)
        self.append(item)
        return item

    def add_folder(self, title: str, bookmark_id: str | None = None) -> SafariBookmarkItem:
        folder = WebBookmarkTypeList(Title=title, Children=[])
        if bookmark_id is not None:
            folder.web_bookmark_uuid = bookmark_id
        item = SafariBookmarkItem(node=folder)
        self.append(item)
        return item

    def json(self) -> str:
        data = self._node.model_dump(by_alias=True)
        return json_module.dumps(
            data, default=self._json_default, separators=(",", ":"), ensure_ascii=False
        )

    @staticmethod
    def _json_default(obj: object) -> str:
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("ascii")
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


class SafariBookmarks(SafariBookmarkItem):
    __slots__ = ("_binary", "_path")

    def __init__(self, root: WebBookmarkTypeList) -> None:
        super().__init__(node=root)
        self._path: Path | None = None
        self._binary: bool | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None and self.path is not None:
            self.save()

    @property
    @override
    def movable(self) -> bool:
        return False

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def binary(self) -> bool | None:
        return self._binary

    def dump(self, fp: IO[bytes], *, binary: bool = True) -> None:
        if hasattr(fp, "mode") and "b" not in fp.mode:
            raise OSError("Must be in binary mode")
        fmt = plistlib.FMT_BINARY if binary else plistlib.FMT_XML
        data = self._node.model_dump(by_alias=True)
        plistlib.dump(data, fp, fmt=fmt, sort_keys=True, skipkeys=False)

    def save(
        self,
        path: os.PathLike[str] | str | None = None,
        *,
        binary: bool | None = None,
        backup: bool = True,
    ) -> None:
        if path is None:
            path = self.path
        if path is None:
            raise RuntimeError("Not opened")
        if binary is None:
            binary = True if self.binary is None else self.binary
        target = Path(path)
        target_mode = target.stat().st_mode if target.exists() else None
        if backup and target.exists():
            timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
            shutil.copy2(target, target.with_name(f"{target.name}.{timestamp}.bak"))
        # Write to a temporary file in the same directory, then atomically
        # replace the target so a crash mid-write cannot corrupt the plist.
        fd, tmp_name = tempfile.mkstemp(prefix=f"{target.name}.", suffix=".tmp", dir=target.parent)
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as file:
                self.dump(fp=file, binary=binary)
            if target_mode is not None:
                tmp_path.chmod(target_mode)
            tmp_path.replace(target)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

    @classmethod
    def load(cls, fp: IO[bytes], *, binary: bool = True) -> SafariBookmarks:
        if hasattr(fp, "mode") and "b" not in fp.mode:
            raise OSError("Must be in binary mode")
        fmt = plistlib.FMT_BINARY if binary else plistlib.FMT_XML
        data = plistlib.load(fp, fmt=fmt)
        obj = cls(WebBookmarkTypeList.model_validate(data))
        obj._binary = binary
        return obj

    @classmethod
    def open(cls, path: os.PathLike[str] | str, *, binary: bool = True) -> SafariBookmarks:
        with Path(path).open("rb") as file:
            obj = cls.load(fp=file, binary=binary)
            obj._path = Path(path)
            return obj
