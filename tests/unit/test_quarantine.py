"""Quarantine list: every entry has an owner, a reason and an expiry, and names a test that exists."""
from datetime import date
from pathlib import Path

import pytest

from qualitylens import quarantine
from qualitylens.quarantine import Entry

pytestmark = pytest.mark.unit
ROOT = Path(__file__).parents[2]
TODAY = date(2026, 10, 22)


def write(tmp_path, text):
    path = tmp_path / "quarantine.toml"
    path.write_text(text)
    return path


VALID = '''
[[test]]
id = " tests/unit/test_quarantine.py::test_load_valid_file "
reason = " flips 1 in 8 "
owner = " roy032 "
issue = "https://example.com/1"
expires = 2026-11-01

[[test]]
id = "tests/unit/test_history.py::test_defaults"
reason = "r"
owner = "o"
expires = 2026-10-30
'''


def test_load_valid_file(tmp_path):
    entries = quarantine.load(write(tmp_path, VALID))
    assert entries == [
        Entry("tests/unit/test_quarantine.py::test_load_valid_file", "flips 1 in 8", "roy032", date(2026, 11, 1),
              "https://example.com/1"),
        Entry("tests/unit/test_history.py::test_defaults", "r", "o", date(2026, 10, 30), ""),
    ]


def test_missing_file_is_an_empty_quarantine(tmp_path):
    assert quarantine.load(tmp_path / "none.toml") == []


def test_repository_quarantine_file_is_valid():
    entries = quarantine.load(ROOT / "quarantine.toml")
    assert quarantine.problems(entries, date.today(), root=ROOT) == []


@pytest.mark.parametrize("body, message", [
    ('id = "a"\nreason = "r"\nowner = "o"', "entry 1 is missing expires"),
    ('id = "a"\nreason = "  "\nowner = ""\nexpires = 2026-11-01', "entry 1 is missing reason, owner"),
    ('reason = "r"\nowner = "o"\nexpires = 2026-11-01', "entry 1 is missing id"),
    ('id = "a"\nreason = "r"\nowner = "o"\nexpires = "soon"', "entry 1: expires must be a date like 2026-11-30"),
])
def test_invalid_entries_are_rejected(tmp_path, body, message):
    with pytest.raises(quarantine.QuarantineError, match=message):
        quarantine.load(write(tmp_path, f"[[test]]\n{body}\n"))


def test_second_entry_is_numbered(tmp_path):
    text = VALID + '\n[[test]]\nid = "x"\nreason = "r"\nowner = "o"\n'
    with pytest.raises(quarantine.QuarantineError, match="entry 3 is missing expires"):
        quarantine.load(write(tmp_path, text))


def test_broken_toml_is_reported_with_the_path(tmp_path):
    path = write(tmp_path, "[[test]\n")
    with pytest.raises(quarantine.QuarantineError, match=str(path).replace("\\", "\\\\")):
        quarantine.load(path)


def test_matching_with_and_without_parameters():
    ids = {"tests/x.py::test_a", "tests/x.py::test_b[2]"}
    assert quarantine.is_quarantined("tests/x.py::test_a", ids)
    assert quarantine.is_quarantined("tests/x.py::test_a[1-x]", ids)
    assert quarantine.is_quarantined("tests/x.py::test_b[2]", ids)
    assert not quarantine.is_quarantined("tests/x.py::test_b[3]", ids)
    assert not quarantine.is_quarantined("tests/x.py::test_ab", ids)
    assert quarantine.base_id("tests/x.py::t[a[b]]") == "tests/x.py::t"
    assert quarantine.is_quarantined("tests/x.py::test_b[2][x]", {"tests/x.py::test_b"})


def entry(test_id="tests/unit/test_history.py::test_defaults", expires=date(2026, 11, 1), owner="o"):
    return Entry(test_id, "r", owner, expires)


def test_valid_entry_has_no_problems():
    assert quarantine.problems([entry()], TODAY, root=ROOT) == []


def test_expired_entry():
    assert quarantine.problems([entry(expires=date(2026, 10, 21), owner="zro")], TODAY) == [
        "tests/unit/test_history.py::test_defaults: quarantine expired on 2026-10-21 (owner zro): "
        "fix the test or renew it with a new reason"]


def test_expiry_day_itself_is_still_valid():
    assert quarantine.problems([entry(expires=TODAY)], TODAY) == []


def test_expiry_too_far_ahead():
    assert quarantine.problems([entry(expires=date(2026, 11, 21))], TODAY) == []
    assert quarantine.problems([entry(expires=date(2026, 11, 22))], TODAY) == [
        "tests/unit/test_history.py::test_defaults: expires 2026-11-22, more than 30 days ahead"]


def test_duplicate_entry():
    assert quarantine.problems([entry(), entry()], TODAY) == [
        "tests/unit/test_history.py::test_defaults: listed twice"]


@pytest.mark.parametrize("test_id", [
    "tests/unit/test_history.py::test_renamed",
    "tests/unit/test_gone.py::test_defaults",
    "tests/unit/test_history.py",
])
def test_unknown_test(test_id):
    assert quarantine.problems([entry(test_id)], TODAY, root=ROOT) == [
        f"{test_id}: no such test (renamed or deleted?)"]


def test_existence_is_not_checked_without_a_root():
    assert quarantine.problems([entry("tests/nope.py::test_x")], TODAY) == []


def test_names_real_test_handles_parameters_and_indentation(tmp_path):
    (tmp_path / "t.py").write_text("class TestX:\n    def test_m(self):\n        pass\n\nasync def test_async():\n")
    assert quarantine.names_real_test("t.py::TestX::test_m[1]", tmp_path)
    assert quarantine.names_real_test("t.py::test_async", tmp_path)
    assert not quarantine.names_real_test("t.py::test_m2", tmp_path)
    assert not quarantine.names_real_test("t.py::test_.", tmp_path)


def test_limits():
    assert quarantine.MAX_DAYS == 30
    assert Path("quarantine.toml") == quarantine.DEFAULT_PATH


def test_pytest_plugin_marks_quarantined_tests(tmp_path):
    """End to end through pytest: listed tests get the marker, so -m can split them out."""
    import subprocess
    import sys

    q = tmp_path / "q.toml"
    q.write_text('[[test]]\nid = "tests/unit/test_quarantine.py::test_limits"\nreason = "r"\nowner = "o"\n'
                 'expires = 2020-01-01\n')

    def pytest(marker):
        # -k keeps this test from running itself recursively
        return subprocess.run([sys.executable, "-m", "pytest", "tests/unit/test_quarantine.py", "-m", marker,
                               "-k", "not test_pytest_plugin",
                               f"--quarantine-file={q}", "-p", "no:cacheprovider", "-q", "-W", "default"],
                              capture_output=True, text=True, cwd=ROOT).stdout

    only = pytest("quarantined")
    assert "1 passed" in only and "quarantine for tests/unit/test_quarantine.py::test_limits expired on 2020-01-01" in only
    assert "2 deselected" in pytest("unit and not quarantined")  # test_limits, and this test via -k
