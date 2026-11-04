from .bookmarks import SafariBookmarkItem, SafariBookmarks

open = SafariBookmarks.open  # ruff: ignore[builtin-variable-shadowing, non-empty-init-module]

__all__ = ["SafariBookmarkItem", "SafariBookmarks", "open"]
