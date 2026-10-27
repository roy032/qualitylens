"""The engine's pytest plugin, run on small throwaway projects (pytester)."""
import pytest

from qualitylens import pytest_plugin

pytestmark = pytest.mark.unit

CONFIG = """
[project]
name = "Shop"
layers = ["api", "unit"]
[target]
base_url = "http://127.0.0.1:9"
health_path = "/health"
requires_app = ["api"]
start_hint = "make up"
api_prefix = "/api"
[target.login]
path = "/me"
user_env = "SHOP_USER"
password_env = "SHOP_PASSWORD"
"""
TESTS = """
import pytest

@pytest.mark.api
def test_api(api):
    assert api.base_url == "http://127.0.0.1:9/api"
    assert api.session.auth == ("ann", "pw")

@pytest.mark.unit
def test_flaky():
    pass

@pytest.mark.unit
def test_project(ql_project, pytestconfig):
    assert ql_project.name == "Shop"
    assert pytestconfig.option.base_url == "http://127.0.0.1:9"
"""


@pytest.fixture
def shop(pytester, monkeypatch):
    monkeypatch.setenv("SHOP_USER", "ann")
    monkeypatch.setenv("SHOP_PASSWORD", "pw")
    monkeypatch.delenv("QL_BASE_URL", raising=False)
    pytester.makefile(".toml", qualitylens=CONFIG)
    pytester.makeini("[pytest]\nmarkers =\n    api: a\n    unit: u\n")
    pytester.makepyfile(test_shop=TESTS)
    return pytester


def test_stops_with_start_hint_when_app_is_down(shop):
    result = shop.runpytest("-p", "qualitylens.pytest_plugin")
    assert result.ret == 3
    result.stdout.fnmatch_lines(["*Shop is not reachable at http://127.0.0.1:9/health (ConnectionError)*make up*"])


def test_runs_without_the_app_when_no_selected_test_needs_it(shop):
    result = shop.runpytest("-p", "qualitylens.pytest_plugin", "-m", "unit")
    result.assert_outcomes(passed=2)
    assert shop.runpytest("-p", "qualitylens.pytest_plugin", "--collect-only").ret == 0


def test_fixtures_and_base_url_when_app_is_up(shop, monkeypatch):
    class Up:
        def raise_for_status(self):
            pass

    seen = []
    monkeypatch.setattr(pytest_plugin.requests, "get", lambda url, timeout: seen.append(url) or Up())
    shop.runpytest("-p", "qualitylens.pytest_plugin").assert_outcomes(passed=3)
    assert seen == ["http://127.0.0.1:9/health"]


def test_quarantine_marks_tests(shop):
    shop.makefile(".toml", quarantine='[[test]]\nid = "test_shop.py::test_flaky"\nreason = "r"\nowner = "o"\n'
                                      'expires = 2999-01-01\n')
    result = shop.runpytest("-p", "qualitylens.pytest_plugin", "-m", "unit and not quarantined")
    result.assert_outcomes(passed=1, deselected=2)  # test_api by marker, test_flaky by quarantine


def test_quarantine_file_option_and_expiry_warning(shop):
    shop.makefile(".toml", other='[[test]]\nid = "test_shop.py::test_flaky"\nreason = "r"\nowner = "o"\n'
                                 'expires = 2000-01-01\n')
    result = shop.runpytest("-p", "qualitylens.pytest_plugin", "--quarantine-file", "other.toml", "-m", "quarantined")
    result.assert_outcomes(passed=1, deselected=2, warnings=1)
    result.stdout.fnmatch_lines(["*quarantine for test_shop.py::test_flaky expired on 2000-01-01*"])


def test_api_without_login(pytester, monkeypatch):
    monkeypatch.delenv("QL_BASE_URL", raising=False)
    pytester.makefile(".toml", qualitylens='[target]\nbase_url = "http://x"\n')
    pytester.makepyfile("def test_api(api):\n    assert api.session.auth is None and api.base_url == 'http://x'\n")
    pytester.runpytest("-p", "qualitylens.pytest_plugin").assert_outcomes(passed=1)
