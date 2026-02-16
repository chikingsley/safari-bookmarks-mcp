from pathlib import Path
from shutil import copyfile
from typing import Any

import pytest

from safaribookmarks.mcp.service import SafariBookmarksService

FIXTURE_PATH = Path(__file__).parent.joinpath("support", "fixtures")
BOOKMARKS_BINARY_PATH = FIXTURE_PATH.joinpath("Bookmarks.bin")


@pytest.fixture()
def bookmarks_path(tmp_path: Path) -> Path:
    dest = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, dest)
    return dest


@pytest.fixture()
def service(bookmarks_path: Path) -> SafariBookmarksService:
    return SafariBookmarksService(bookmarks_path)


def read_plist(path: Path) -> Any:
    import plistlib

    with path.open("rb") as file:
        return plistlib.load(file)


def assert_plists(path: Path, fixture: Path) -> None:
    assert read_plist(path) == read_plist(fixture)


def test_list_bookmarks_root(service: SafariBookmarksService):
    items = service.list_bookmarks()
    assert [item["title"] for item in items] == [
        "History",
        "BookmarksBar",
        "BookmarksMenu",
        "com.apple.ReadingList",
    ]


def test_search_bookmarks(service: SafariBookmarksService):
    results = service.search_bookmarks(query="Safari", path=["BookmarksBar"])
    ids = {item["id"] for item in results}
    assert "AB38D373-1266-495A-8CAC-422A771CF70A" in ids


def test_add_bookmark_service(
    service: SafariBookmarksService,
    bookmarks_path: Path,
    monkeypatch,
):
    with monkeypatch.context() as m:
        m.setattr("uuid.uuid4", lambda: "8693E85C-83FC-4F42-AFB2-40B9CFACAAA0")
        service.add_bookmark(
            path=["20ABDC16-B491-47F4-B252-2A3065CFB895"],
            title=None,
            url="http://example.com",
        )
        assert_plists(
            bookmarks_path,
            FIXTURE_PATH.joinpath("add-fixed-uuid-no-title-leaf.plist"),
        )


def test_add_folder_service(
    service: SafariBookmarksService,
    bookmarks_path: Path,
):
    service.add_folder(
        path=["BookmarksMenu"],
        title="Example",
        id="38691E76-D8F0-4946-B68D-370213EFEB9E",
    )
    assert_plists(bookmarks_path, FIXTURE_PATH.joinpath("add-list.plist"))


def test_move_service(service: SafariBookmarksService, bookmarks_path: Path):
    service.move(
        path=["AB38D373-1266-495A-8CAC-422A771CF70A"],
        to=["20ABDC16-B491-47F4-B252-2A3065CFB895"],
    )
    assert_plists(bookmarks_path, FIXTURE_PATH.joinpath("move-leaf.plist"))


def test_edit_service(service: SafariBookmarksService, bookmarks_path: Path):
    service.edit(
        path=["AB38D373-1266-495A-8CAC-422A771CF70A"],
        title="Updated example",
        url="http://example.com",
    )
    assert_plists(bookmarks_path, FIXTURE_PATH.joinpath("edit-title-url-leaf.plist"))


def test_remove_service(service: SafariBookmarksService, bookmarks_path: Path):
    service.remove(path=["B441CA58-1880-4151-929E-743090B66587"])
    assert_plists(bookmarks_path, FIXTURE_PATH.joinpath("remove-leaf.plist"))


def test_empty_service(service: SafariBookmarksService, bookmarks_path: Path):
    service.empty(path=["BookmarksBar"])
    assert_plists(bookmarks_path, FIXTURE_PATH.joinpath("empty.plist"))


def test_service_dry_run_does_not_persist(service: SafariBookmarksService, bookmarks_path: Path):
    original = bookmarks_path.read_bytes()
    service.add_bookmark(
        path=["20ABDC16-B491-47F4-B252-2A3065CFB895"],
        title="Dry run bookmark",
        url="http://example.com",
        dry_run=True,
    )
    assert bookmarks_path.read_bytes() == original
