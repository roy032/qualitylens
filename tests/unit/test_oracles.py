"""The expected-behaviour models the property-based API tests compare Gitea against."""
import pytest

from suite import oracles

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("text, trimmed", [
    ("  a b  ", "a b"),
    ("\t\n\x0b\x0c\r x \x85\xa0", "x"),
    ("       　x　", "x"),
    ("\x1cx\x1f", "\x1cx\x1f"),          # Python's strip() would remove these, Go's TrimSpace does not
    ("​x", "​x"),              # zero-width space is not White_Space
    ("", ""),
])
def test_go_trim_space(text, trimmed):
    assert oracles.go_trim_space(text) == trimmed


def test_go_whitespace_covers_exactly_the_unicode_white_space_property():
    assert len(oracles.GO_WHITESPACE) == 25
    assert "​" not in oracles.GO_WHITESPACE


@pytest.mark.parametrize("title, stored", [
    ("Bug", "Bug"),
    ("  Bug  ", "Bug"),
    ("   ", None),                       # blank: should be rejected (BUG-001)
    ("", None),
    ("x" * 255, "x" * 255),
    ("x" * 256, None),                   # too long: should be rejected (BUG-002)
    (" " + "x" * 255 + " ", "x" * 255),  # the limit applies after trimming
    ("🐞" * 255, "🐞" * 255),             # counted in characters, not bytes
])
def test_stored_issue_title(title, stored):
    assert oracles.stored_issue_title(title) == stored


@pytest.mark.parametrize("name, allowed", [
    ("a", True), ("a" * 100, True), ("a" * 101, False), ("", False),
    ("my_repo-1.0", True), ("..a", True), ("a..b", True), ("_", True), (".-", True),
    (".", False), ("..", False), ("-", False),
    ("x.git", False), ("X.GIT", False), ("x.wiki", False), ("x.rss", False), ("x.atom", False),
    ("x.gitx", True), ("gitx", True),
    ("a b", False), ("a/b", False), ("é", False), ("a\n", False),
])
def test_repo_name_allowed(name, allowed):
    assert oracles.repo_name_allowed(name) is allowed


@pytest.mark.parametrize("color, valid", [
    ("#abc", True), ("abc", True), ("#A1b2C3", True), ("a1b2c3", True),
    ("#ab", False), ("#abcd", False), ("#abcdefa", False), ("##abc", False), ("#abg", False), ("", False),
    (" #abc", False), ("#abc\n", False),
])
def test_is_hex_color(color, valid):
    assert oracles.is_hex_color(color) is valid


@pytest.mark.parametrize("color, stored", [
    ("#ABC", "aabbcc"), ("abc", "aabbcc"), ("#F00BA4", "f00ba4"), ("123456", "123456"),
])
def test_normalised_label_color(color, stored):
    assert oracles.normalised_label_color(color) == stored
