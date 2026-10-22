"""Expected-behaviour models ("oracles") for property-based tests.

A property test sends hundreds of generated inputs, so it cannot list the expected answer for each one.
Instead it asks these functions what Gitea *should* do with an input and compares that with what it did.
They model the rules Gitea documents or enforces in its Go code, not what the server happens to return,
so a disagreement is a finding to investigate, not something to copy into the model.
"""
from __future__ import annotations

import re

# Go's strings.TrimSpace removes Unicode White_Space characters. Python's str.strip() uses a different
# set (it also removes the ASCII separators \x1c-\x1f), so the set is spelled out here.
GO_WHITESPACE = ("\t\n\x0b\x0c\r \x85\xa0 "
                 + "".join(chr(c) for c in range(0x2000, 0x200B))
                 + "    　")

ISSUE_TITLE_MAX = 255           # characters (Go runes), models/issues/issue.go
REPO_NAME_MAX = 100             # binding:"MaxSize(100)" on CreateRepoOption.Name
REPO_NAME_RESERVED = {".", "..", "-"}
REPO_NAME_RESERVED_SUFFIXES = (".git", ".wiki", ".rss", ".atom")
_REPO_NAME_CHARS = re.compile(r"[-\w.]+", re.ASCII)   # binding:"AlphaDashDot"


def go_trim_space(text: str) -> str:
    """What Gitea stores for a title it trims: strings.TrimSpace."""
    return text.strip(GO_WHITESPACE)


def stored_issue_title(title: str) -> str | None:
    """The title Gitea should store, or None when it should reject the request.

    A title that is blank after trimming should be rejected (BUG-001: it is stored as ""), and one over
    255 characters should be rejected rather than cut (BUG-002). Property tests generate inside the valid
    range; the known_bug tests cover the edges.
    """
    trimmed = go_trim_space(title)
    if not trimmed or len(trimmed) > ISSUE_TITLE_MAX:
        return None
    return trimmed


def repo_name_allowed(name: str) -> bool:
    """Whether POST /user/repos should accept this name (otherwise 422)."""
    return (0 < len(name) <= REPO_NAME_MAX
            and _REPO_NAME_CHARS.fullmatch(name) is not None
            and name not in REPO_NAME_RESERVED
            and not name.lower().endswith(REPO_NAME_RESERVED_SUFFIXES))


_HEX_COLOR = re.compile(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def is_hex_color(color: str) -> bool:
    """Label colours Gitea accepts: three or six hex digits, with or without '#'."""
    return _HEX_COLOR.fullmatch(color) is not None


def normalised_label_color(color: str) -> str:
    """Gitea stores label colours as six lower-case hex digits: '#ABC' -> 'aabbcc', 'F00BA4' -> 'f00ba4'."""
    digits = color.removeprefix("#").lower()
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return digits
