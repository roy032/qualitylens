"""`qualitylens init`: the generated project is valid, safe to re-run and points at the given app."""
import ast
import configparser

import pytest
import yaml

from qualitylens import project as project_config
from qualitylens import scaffold

pytestmark = pytest.mark.unit
OPTIONS = scaffold.Options(name='My "Shop"', base_url="http://shop:8000/", health_path="health", api_prefix="/api/")


def test_config_parses_and_points_at_the_app(tmp_path):
    scaffold.write(tmp_path, OPTIONS)
    p = project_config.load(tmp_path / "qualitylens.toml", env={})
    assert p.name == 'My "Shop"' and p.root == tmp_path
    assert p.health_url == "http://shop:8000/health" and p.api_url == "http://shop:8000/api"
    assert p.layers == ("smoke", "api", "ui") and set(p.requires_app) == set(p.layers)
    assert {"smoke", "full", "quarantined"} <= set(p.profiles) and p.browser


def test_markers_match_layers(tmp_path):
    scaffold.write(tmp_path, OPTIONS)
    ini = configparser.ConfigParser()
    ini.read(tmp_path / "pytest.ini")
    markers = {line.split(":")[0].strip() for line in ini["pytest"]["markers"].splitlines() if line.strip()}
    assert markers == set(project_config.load(tmp_path / "qualitylens.toml", env={}).layers)


def test_python_files_compile():
    for path, content in scaffold.files(OPTIONS).items():
        if path.endswith(".py"):
            ast.parse(content, path)


def test_workflow_is_valid_yaml_with_pinned_actions():
    workflow = yaml.safe_load(scaffold.files(OPTIONS)[".github/workflows/qualitylens.yml"])
    steps = workflow["jobs"]["qa"]["steps"]
    uses = [s["uses"] for s in steps if "uses" in s]
    assert uses and all("@" in u and len(u.split("@")[1]) == 40 for u in uses)
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["qa"]["env"]["QL_BASE_URL"] == "${{ vars.QL_BASE_URL }}"


def test_no_secrets_written():
    text = "".join(scaffold.files(OPTIONS).values())
    assert "password =" not in text.lower()


def test_existing_files_are_kept_unless_forced(tmp_path):
    (tmp_path / "pytest.ini").write_text("mine")
    written, kept = scaffold.write(tmp_path, OPTIONS)
    assert kept == [tmp_path / "pytest.ini"] and (tmp_path / "pytest.ini").read_text() == "mine"
    assert len(written) == len(scaffold.files(OPTIONS)) - 1
    written, kept = scaffold.write(tmp_path, OPTIONS, force=True)
    assert kept == [] and (tmp_path / "pytest.ini").read_text() != "mine"
