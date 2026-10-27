import os

import pytest
import requests

from suite.config import settings


def pytest_collection_modifyitems(config, items):
    """Screenshots only match inside the pinned Playwright image, so skip elsewhere (see `make visual`)."""
    if os.getenv("QL_VISUAL") == "1":
        return
    skip = pytest.mark.skip(reason="visual tests run inside the pinned Playwright container: make visual")
    for item in items:
        if item.get_closest_marker("visual"):
            item.add_marker(skip)


@pytest.fixture(scope="session")
def update_snapshots(request) -> bool:
    return request.config.getoption("--update-snapshots")


@pytest.fixture(scope="session")
def gitea_version() -> str:
    return requests.get(f"{settings.api_url}/version", timeout=5).json()["version"]


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    # Same viewport, locale, timezone and colour scheme on every machine.
    return {**browser_context_args, "viewport": {"width": 1280, "height": 800}, "locale": "en-US",
            "timezone_id": "UTC", "color_scheme": "light", "device_scale_factor": 1}
