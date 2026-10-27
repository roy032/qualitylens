"""qualitylens.toml: parsing, defaults, environment overrides and error messages."""
from pathlib import Path

import pytest

from qualitylens import project as project_config
from qualitylens.project import ConfigError, Login

pytestmark = pytest.mark.unit
ROOT = Path(__file__).parents[2]


def parse(data, env=None, root=Path("/p")):
    return project_config.parse(data, root, env or {})


def test_defaults_for_an_empty_file():
    p = parse({})
    assert p.name == "p" and p.layers == () and p.base_url == "http://localhost:8000"
    assert p.health_url == "" and p.login is None and p.database_dsn == ""
    assert p.profiles == project_config.DEFAULT_PROFILES
    assert p.impact_rules == project_config.DEFAULT_IMPACT_RULES and p.impact_fallback == "full"
    assert p.history_path == Path("/p/test-history/history.json") and p.quarantine_path == Path("/p/quarantine.toml")
    assert (p.history_keep, p.flaky_min_runs, p.flaky_threshold) == (50, 10, 0.1)


def test_target_and_urls():
    p = parse({"project": {"name": "Shop", "layers": ["api"]},
               "target": {"base_url": "http://shop:8000/", "health_path": "/health", "api_prefix": "/api/",
                          "requires_app": ["api"], "start_hint": "make up"}})
    assert (p.name, p.layers, p.requires_app, p.start_hint) == ("Shop", ("api",), ("api",), "make up")
    assert p.base_url == "http://shop:8000"
    assert p.health_url == "http://shop:8000/health" and p.api_url == "http://shop:8000/api"


def test_base_url_env_override():
    p = parse({"target": {"base_url": "http://a"}}, env={"QL_BASE_URL": "https://staging"})
    assert p.base_url == "https://staging"


def test_login_and_database_from_env():
    data = {"target": {"login": {"path": "/me", "user_env": "U", "password_env": "P", "default_user": "dev"},
                       "database": {"dsn_env": "DSN", "default_dsn": "postgresql://local"}}}
    assert parse(data).login == Login("/me", "dev", "")
    assert parse(data).database_dsn == "postgresql://local"
    p = parse(data, env={"U": "ci", "P": "secret", "DSN": "postgresql://ci"})
    assert p.login == Login("/me", "ci", "secret") and p.database_dsn == "postgresql://ci"


def test_default_env_names():
    env = {"QL_USER": "u", "QL_PASSWORD": "p", "QL_DB_DSN": "postgresql://env"}
    p = parse({"target": {"login": {"path": "/me"}, "database": {"default_dsn": "x"}}}, env=env)
    assert p.login == Login("/me", "u", "p") and p.database_dsn == "postgresql://env"
    assert parse({}, env=env).database_dsn == ""  # no [target.database]: no database check
    assert parse({"target": {"login": {"path": "/me"}}}).login == Login("/me", "", "")


def test_default_hint_and_browser():
    p = parse({"target": {}, "doctor": {}})
    assert p.start_hint == "start the app under test" and p.browser is False
    assert p.packages == ("pytest", "requests")


def test_login_without_path_is_ignored():
    assert parse({"target": {"login": {"user_env": "U"}}}).login is None


def test_profiles_merge_with_defaults():
    p = parse({"profiles": {"api": [["-m", "api"], ["-m", "contract"]], "smoke": [["tests/smoke"]]}})
    assert p.profiles["api"] == [["-m", "api"], ["-m", "contract"]]
    assert p.profiles["smoke"] == [["tests/smoke"]] and "quarantined" in p.profiles


def test_impact_rules_before_defaults():
    p = parse({"impact": {"rule": [{"glob": "src/*", "layers": ["api"]}], "fallback_profile": "smoke"}})
    assert p.impact_rules[0] == ("src/*", ("api",)) and p.impact_rules[1:] == project_config.DEFAULT_IMPACT_RULES
    assert p.impact_fallback == "smoke"
    bare = parse({"impact": {"rule": [{"glob": "x"}], "keep_defaults": False}})
    assert bare.impact_rules == (("x", ()),)


def test_history_flaky_quarantine():
    p = parse({"history": {"path": "h/runs.json", "keep": 5}, "flaky": {"min_runs": 3, "threshold": 0.5},
               "quarantine": {"path": "q.toml"}, "doctor": {"packages": ["x"], "browser": True}})
    assert p.history_path == Path("/p/h/runs.json") and p.history_keep == 5
    assert (p.flaky_min_runs, p.flaky_threshold) == (3, 0.5)
    assert p.quarantine_path == Path("/p/q.toml") and p.packages == ("x",) and p.browser


@pytest.mark.parametrize("data, message", [
    ({"project": "x"}, "^project must be a table"),
    ({"target": 1}, "^target must be a table"),
    ({"doctor": 1}, "^doctor must be a table"),
    ({"history": 1}, "^history must be a table"),
    ({"flaky": 1}, "^flaky must be a table"),
    ({"impact": 1}, "^impact must be a table"),
    ({"profiles": 1}, "^profiles must be a table"),
    ({"quarantine": 1}, "^quarantine must be a table"),
    ({"target": {"database": 1}}, "^target.database must be a table"),
    ({"doctor": {"packages": "x"}}, "^doctor.packages must be a list of strings"),
    ({"target": {"login": 1}}, "target.login must be a table"),
    ({"project": {"layers": "api"}}, "project.layers must be a list of strings"),
    ({"target": {"requires_app": [1]}}, "target.requires_app must be a list of strings"),
    ({"profiles": {"x": ["-m", "api"]}}, "profiles.x must be a list of pytest argument lists"),
    ({"profiles": {"x": []}}, "profiles.x must be a list of pytest argument lists"),
    ({"profiles": {"x": [[1]]}}, "profiles.x must be a list of strings"),
    ({"impact": {"rule": [{"layers": ["api"]}]}}, "impact.rule 1 needs a glob"),
    ({"impact": {"rule": [{"glob": "a", "layers": "api"}]}}, "impact.rule 1 layers must be a list of strings"),
])
def test_errors(data, message):
    with pytest.raises(ConfigError, match=message):
        parse(data)


def test_find_walks_up(tmp_path):
    (tmp_path / "qualitylens.toml").write_text("")
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert project_config.find(deep) == tmp_path / "qualitylens.toml"


def test_load(tmp_path):
    (tmp_path / "qualitylens.toml").write_text('[project]\nname = "Shop"\n')
    sub = tmp_path / "tests"
    sub.mkdir()
    assert project_config.load(start=sub, env={}).name == "Shop"
    assert project_config.load(tmp_path / "qualitylens.toml", env={}).root == tmp_path
    assert project_config.load(start=sub, env={"QL_BASE_URL": "http://env"}).base_url == "http://env"


def test_load_without_file(tmp_path):
    p = project_config.load(start=tmp_path, env={})
    assert p.root == tmp_path and p.name == tmp_path.name
    assert project_config.load(start=tmp_path, env={"QL_BASE_URL": "http://env"}).base_url == "http://env"


def test_load_errors_name_the_file(tmp_path):
    bad = tmp_path / "qualitylens.toml"
    bad.write_text("[project\n")
    with pytest.raises(ConfigError, match=f"{bad}: "):
        project_config.load(bad)
    bad.write_text("[project]\nlayers = 1\n")
    with pytest.raises(ConfigError, match=f"{bad}: project.layers"):
        project_config.load(bad)


def test_repository_config_is_valid():
    gitea = project_config.load(ROOT / "qualitylens.toml", env={})
    assert gitea.name == "Gitea" and "api" in gitea.layers
    assert gitea.health_url == "http://localhost:3000/api/v1/version"
    assert gitea.login and gitea.login.user == "qa_admin"
    assert set(gitea.requires_app) <= set(gitea.layers)
    assert gitea.impact_fallback in gitea.profiles
