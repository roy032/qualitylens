"""pytest plugin: tests listed in quarantine.toml get the `quarantined` marker.

CI deselects them from the blocking run (`-m "... and not quarantined"`) and runs them in a separate
step that may fail, so they keep producing history without turning the build red.
"""
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import pytest

from qualitylens import quarantine


def pytest_addoption(parser):
    parser.addoption("--quarantine-file", default=None,
                     help="flaky-test quarantine list (default: quarantine.toml in the rootdir)")


def pytest_configure(config):
    config.addinivalue_line("markers", "quarantined: listed in quarantine.toml; runs, but must not block CI")


@pytest.hookimpl(tryfirst=True)  # before -m deselects, so "not quarantined" sees the marker
def pytest_collection_modifyitems(config, items):
    path = Path(config.getoption("--quarantine-file") or Path(config.rootpath) / quarantine.DEFAULT_PATH)
    entries = quarantine.load(path)
    if not entries:
        return
    ids = {e.test_id for e in entries}
    for e in entries:
        if e.expires < date.today():
            warnings.warn(f"quarantine for {e.test_id} expired on {e.expires}", stacklevel=1)
    for item in items:
        if quarantine.is_quarantined(item.nodeid, ids):
            item.add_marker(pytest.mark.quarantined)
