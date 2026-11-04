from __future__ import annotations

import inspect
import plistlib
from io import StringIO
from pathlib import Path
from shutil import copyfile
from typing import Any, cast

import pytest

from safaribookmarks.cli import CLI
from safaribookmarks.cli.main import parse_args

FIXTURE_PATH = Path(__file__).parent.joinpath("support", "fixtures")
BOOKMARKS_BINARY_PATH = FIXTURE_PATH.joinpath("Bookmarks.bin")
Plist = dict[str, object]


@pytest.fixture
def bookmarks_path(tmp_path: Path) -> Path:
    dest = tmp_path.joinpath("Bookmarks.plist")
    copyfile(BOOKMARKS_BINARY_PATH, dest)
    return dest


@pytest.fixture
def cli(bookmarks_path: Path) -> CLI:
    return CLI(str(bookmarks_path), StringIO())


def read_plist(path: Path) -> Plist:
    with path.open("rb") as file:
        return cast(Plist, plistlib.load(file))


def assert_plists(actual: Path | None, expected: Path) -> None:
    assert actual is not None
    assert read_plist(actual) == read_plist(expected)


def reset_bookmarks(path: Path | None) -> Path:
    assert path is not None
    copyfile(BOOKMARKS_BINARY_PATH, path)
    return path


def test_run_rejects_missing_and_private_commands(cli: CLI) -> None:
    with pytest.raises(ValueError, match="No command specified"):
        cli.run(cast(Any, None))
    with pytest.raises(ValueError, match="Invalid command"):
        cli.run("_resolve")


def test_list_renders_default_json_and_target(cli: CLI) -> None:
    cli.list_bookmarks(path=[])
    cli.output.seek(0)
    assert cli.output.read() == FIXTURE_PATH.joinpath("list.txt").read_text()

    cli.output = StringIO()
    cli.list_bookmarks(path=["BookmarksBar"], json=True)
    cli.output.seek(0)
    assert '"Title":"BookmarksBar"' in cli.output.read()

    cli.output = StringIO()
    cli.list_bookmarks(path=["BookmarksBar", "Safari Bookmarks CLI"])
    cli.output.seek(0)
    assert cli.output.read() == FIXTURE_PATH.joinpath("list-leaf.txt").read_text()


def test_add_bookmark_and_folder(cli: CLI) -> None:
    cli.add(
        path=["BookmarksMenu"],
        title="Example",
        url="http://example.com",
        uuid="38691E76-D8F0-4946-B68D-370213EFEB9E",
    )
    assert_plists(cli.path, FIXTURE_PATH.joinpath("add-leaf.plist"))

    fresh = CLI(str(reset_bookmarks(cli.path)), StringIO())
    fresh.add(
        path=["BookmarksMenu"],
        title="Example",
        folder=True,
        uuid="38691E76-D8F0-4946-B68D-370213EFEB9E",
    )
    assert_plists(fresh.path, FIXTURE_PATH.joinpath("add-list.plist"))


def test_remove_move_edit_and_empty(cli: CLI) -> None:
    cli.remove(path=["B441CA58-1880-4151-929E-743090B66587"])
    assert_plists(cli.path, FIXTURE_PATH.joinpath("remove-leaf.plist"))

    cli = CLI(str(reset_bookmarks(cli.path)), StringIO())
    cli.move(
        path=["AB38D373-1266-495A-8CAC-422A771CF70A"],
        to=["20ABDC16-B491-47F4-B252-2A3065CFB895"],
    )
    assert_plists(cli.path, FIXTURE_PATH.joinpath("move-leaf.plist"))

    cli = CLI(str(reset_bookmarks(cli.path)), StringIO())
    cli.edit(
        path=["AB38D373-1266-495A-8CAC-422A771CF70A"],
        title="Updated example",
        url="http://example.com",
    )
    assert_plists(cli.path, FIXTURE_PATH.joinpath("edit-title-url-leaf.plist"))

    cli = CLI(str(reset_bookmarks(cli.path)), StringIO())
    cli.empty(path=["BookmarksBar"])
    assert_plists(cli.path, FIXTURE_PATH.joinpath("empty.plist"))


def test_move_into_own_descendant_is_rejected(cli: CLI) -> None:
    cli.add(
        path=["BookmarksBar"],
        title="child",
        folder=True,
        uuid="38691E76-D8F0-4946-B68D-370213EFEB9E",
    )
    with pytest.raises(ValueError, match="Invalid destination"):
        cli.move(path=["BookmarksBar"], to=["BookmarksBar", "child"])


@pytest.mark.parametrize(
    ("operation", "kwargs", "message"),
    [
        ("list_bookmarks", {"path": ["Missing"]}, "Target not found"),
        (
            "add",
            {"path": ["BookmarksBar", "Safari"], "title": "Bad", "url": "https://x.test"},
            "Invalid destination",
        ),
        ("move", {"path": ["Missing"], "to": ["BookmarksMenu"]}, "Target not found"),
        ("edit", {"path": ["BookmarksBar"], "url": "https://x.test"}, "Cannot update target url"),
        ("empty", {"path": ["BookmarksBar", "Safari"]}, "Target is not a list"),
    ],
)
def test_invalid_commands_raise(
    cli: CLI,
    operation: str,
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        getattr(cli, operation)(**kwargs)


def test_move_argparse_kwargs_match_method_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["safari-bookmarks", "move", "BookmarksBar", "--to", "BookmarksMenu"],
    )
    args = parse_args().__dict__
    args.pop("file")
    command = args.pop("command")

    assert command == "move"
    inspect.signature(CLI.move).bind(None, **args)
