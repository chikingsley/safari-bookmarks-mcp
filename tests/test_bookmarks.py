from __future__ import annotations

import hashlib
import json
import stat
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from shutil import copyfile
from typing import Any, cast

import pytest

import safaribookmarks
from safaribookmarks.bookmarks import SafariBookmarkItem, SafariBookmarks
from safaribookmarks.models import WebBookmarkType, WebBookmarkTypeLeaf, WebBookmarkTypeList

FIXTURE_PATH = Path(__file__).parent.joinpath("support", "fixtures")
BOOKMARKS_BINARY_PATH = FIXTURE_PATH.joinpath("Bookmarks.bin")
BOOKMARKS_XML_PATH = FIXTURE_PATH.joinpath("Bookmarks.xml")


@pytest.fixture
def bookmarks() -> SafariBookmarks:
    safari = WebBookmarkTypeLeaf(
        WebBookmarkUUID="AB38D373-1266-495A-8CAC-422A771CF70A",
        URLString="http://apple.com/safari",
        URIDictionary={"title": "Safari"},
    )
    bar = WebBookmarkTypeList(
        WebBookmarkUUID="3B5180DB-831D-4F1A-AE4A-6482D28D66D5",
        Title="BookmarksBar",
        Children=[safari],
    )
    menu = WebBookmarkTypeList(
        WebBookmarkUUID="20ABDC16-B491-47F4-B252-2A3065CFB895",
        Title="BookmarksMenu",
        Children=[],
    )
    return SafariBookmarks(WebBookmarkTypeList(Title="", Children=[bar, menu]))


def test_resolves_root_titles_and_uuid(bookmarks: SafariBookmarks) -> None:
    assert bookmarks.resolve_path([]) is bookmarks
    assert bookmarks.resolve_path(["BookmarksBar"]) == bookmarks.get(
        "3B5180DB-831D-4F1A-AE4A-6482D28D66D5"
    )

    safari = bookmarks.resolve_path(["BookmarksBar", "Safari"])
    by_uuid = bookmarks.resolve_path(["AB38D373-1266-495A-8CAC-422A771CF70A"])

    assert safari == by_uuid
    assert safari is not None
    assert safari.url == "http://apple.com/safari"
    assert bookmarks.resolve_path(["Missing"]) is None


def test_add_move_remove_and_empty_update_tree(bookmarks: SafariBookmarks) -> None:
    menu = bookmarks["BookmarksMenu"]
    added = menu.add_bookmark(
        "https://example.com",
        title="Example",
        bookmark_id="11111111-1111-1111-1111-111111111111",
    )
    folder = menu.add_folder("Reading", bookmark_id="22222222-2222-2222-2222-222222222222")

    assert added.parent == menu
    assert folder.parent == menu
    assert menu["Example"] == added

    folder.append(added)
    assert added.parent == folder
    assert added not in menu

    folder.remove(added)
    assert added.parent is None
    folder.empty()
    assert len(folder) == 0


def test_rejects_invalid_parent_and_non_folder_append(bookmarks: SafariBookmarks) -> None:
    leaf = bookmarks["BookmarksBar", "Safari"]
    detached = SafariBookmarkItem(WebBookmarkTypeLeaf(URLString="https://example.com"))

    with pytest.raises(ValueError, match="Parent must be a folder"):
        SafariBookmarkItem(WebBookmarkTypeLeaf(URLString="https://example.com"), parent=leaf)

    with pytest.raises(RuntimeError, match="Not a folder"):
        leaf.append(detached)

    with pytest.raises(RuntimeError, match="Invalid item"):
        bookmarks["BookmarksMenu"].append(SafariBookmarkItem(WebBookmarkType()))


def test_empty_items_are_truthy() -> None:
    folder = SafariBookmarkItem(WebBookmarkTypeList(Title="Empty", Children=[]))
    leaf = SafariBookmarkItem(WebBookmarkTypeLeaf(URLString="https://example.com"))

    assert len(folder) == 0
    assert bool(folder) is True
    assert len(leaf) == 0
    assert bool(leaf) is True


def test_json_serializes_safari_extra_fields() -> None:
    item = SafariBookmarkItem(
        WebBookmarkTypeLeaf(
            URLString="https://example.com",
            URIDictionary={"title": "Example"},
            ReadingList={"DateAdded": datetime(2022, 3, 2, 2, 30, 51, tzinfo=UTC)},
            Sync={"Data": b"\x00\x01\x02\xff"},
        )
    )

    payload = json.loads(item.json())

    assert payload["ReadingList"]["DateAdded"] == "2022-03-02T02:30:51+00:00"
    assert payload["Sync"]["Data"] == "AAEC/w=="


@pytest.mark.parametrize(
    ("path", "binary"),
    [
        (BOOKMARKS_BINARY_PATH, True),
        (BOOKMARKS_XML_PATH, False),
    ],
)
def test_loads_fixture_plists(path: Path, binary: bool) -> None:
    with path.open("rb") as file:
        bookmarks = SafariBookmarks.load(file, binary=binary)

    assert bookmarks["BookmarksBar", "Safari"].url == "http://apple.com/safari"


def test_package_open_alias_is_preserved() -> None:
    bookmarks = safaribookmarks.open(BOOKMARKS_BINARY_PATH)

    assert bookmarks["BookmarksBar", "Safari"].url == "http://apple.com/safari"


@pytest.mark.parametrize(
    ("digest", "binary"),
    [
        ("d511ce45ce3f14a2cccb18a07a05e7e75cb7d7b7", True),
        ("27cad5206ac74ba085f67ecb0a56649e37ad206d", False),
    ],
)
def test_dump_preserves_fixture_output_format(digest: str, binary: bool) -> None:
    with BOOKMARKS_BINARY_PATH.open("rb") as file:
        bookmarks = SafariBookmarks.load(file)

    with BytesIO() as buffer:
        bookmarks.dump(buffer, binary=binary)
        assert hashlib.sha1(buffer.getvalue()).hexdigest() == digest


def test_save_backs_up_and_writes_atomically(tmp_path: Path) -> None:
    path = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, path)
    bookmarks = SafariBookmarks.open(path)

    bookmarks.save()

    backups = list(tmp_path.glob("Bookmarks.plist.*.bak"))
    assert len(backups) == 1
    assert not list(tmp_path.glob("*.tmp"))
    # The saved file is still a valid, reloadable plist.
    assert SafariBookmarks.open(path)["BookmarksBar", "Safari"].url == "http://apple.com/safari"


def test_save_preserves_existing_file_mode(tmp_path: Path) -> None:
    path = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, path)
    path.chmod(0o644)
    bookmarks = SafariBookmarks.open(path)

    bookmarks.save()

    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_save_creates_distinct_backups(tmp_path: Path) -> None:
    path = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, path)
    bookmarks = SafariBookmarks.open(path)

    bookmarks.save()
    bookmarks.save()

    assert len(list(tmp_path.glob("Bookmarks.plist.*.bak"))) == 2


def test_save_skips_backup_when_disabled(tmp_path: Path) -> None:
    path = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, path)
    bookmarks = SafariBookmarks.open(path)

    bookmarks.save(backup=False)

    assert not list(tmp_path.glob("*.bak"))


def test_load_and_dump_require_binary_streams(tmp_path: Path) -> None:
    with (
        pytest.raises(OSError, match="Must be in binary mode"),
        BOOKMARKS_BINARY_PATH.open("r") as file,
    ):
        SafariBookmarks.load(cast(Any, file))

    with (
        pytest.raises(OSError, match="Must be in binary mode"),
        tmp_path.joinpath("Bookmarks.plist").open("w") as file,
    ):
        SafariBookmarks(WebBookmarkTypeList(Title="")).dump(cast(Any, file))
