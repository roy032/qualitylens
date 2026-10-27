"""Property-based API tests (Hypothesis). Manual cases: TC-API-PROP-*.

Example-based tests check the inputs someone thought of. These generate hundreds of inputs per run
(any Unicode text, odd numbers, unusual names) and check rules that must hold for all of them:
the server never answers 5xx, what it stores is what it should store (see qualitylens/oracles.py),
and a sequence of issue operations leaves Gitea in the same state as a simple in-memory model.
When a rule breaks, Hypothesis shrinks the input to the smallest one that still breaks it.
That is how BUG-011 (a NUL character crashes six endpoints) was found.

Runs are reproducible: CI uses a fixed seed (profile "ci"); `make fuzz` runs the "deep" profile
with random seeds and ten times more examples. Profiles are defined in tests/conftest.py.
"""
import allure
import pytest
from hypothesis import HealthCheck, assume, given
from hypothesis import settings as hsettings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule, run_state_machine_as_test

from qualitylens import oracles
from qualitylens.api_client import GiteaApi
from qualitylens.config import settings
from qualitylens.data import unique

pytestmark = [pytest.mark.api, pytest.mark.property, allure.feature("API: Property-based")]
OWNER = settings.admin_user

# Fixtures are created once per test, not once per generated example: that is intended here
# (one repository receives every example), so Hypothesis's warning about it is switched off.
reuse_fixtures = hsettings(suppress_health_check=[HealthCheck.function_scoped_fixture])

# Any Unicode text except NUL (BUG-011, pinned separately below) and lone surrogates (not valid JSON).
TEXT_CHARS = st.characters(exclude_categories=("Cs",), exclude_characters="\x00")
any_text = st.text(TEXT_CHARS, max_size=300)
# A valid title: something other than whitespace, within 255 characters after trimming.
issue_titles = (st.text(TEXT_CHARS, min_size=1, max_size=255)
                .filter(lambda t: oracles.stored_issue_title(t) is not None))


@reuse_fixtures
@given(title=issue_titles)
def test_issue_title_stored_as_trimmed_input(api, repo, title):
    resp = api.create_issue(OWNER, repo["name"], title)
    assert resp.status_code == 201, resp.text
    expected = oracles.stored_issue_title(title)
    assert resp.json()["title"] == expected
    assert api.get_issue(OWNER, repo["name"], resp.json()["number"]).json()["title"] == expected


@reuse_fixtures
@given(body=any_text)
def test_issue_body_round_trips_exactly(api, repo, body):
    resp = api.create_issue(OWNER, repo["name"], "body round trip", body=body)
    assert resp.status_code == 201, resp.text
    assert api.get_issue(OWNER, repo["name"], resp.json()["number"]).json()["body"] == body


@reuse_fixtures
@given(body=any_text.filter(lambda b: oracles.go_trim_space(b) != ""))   # blank comments are BUG-007
def test_comment_body_round_trips_exactly(api, repo, issue, body):
    resp = api.add_comment(OWNER, repo["name"], issue["number"], body)
    assert resp.status_code == 201, resp.text
    comment_id = resp.json()["id"]
    assert api.get(f"/repos/{OWNER}/{repo['name']}/issues/comments/{comment_id}").json()["body"] == body


@reuse_fixtures
@given(color=st.from_regex(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", fullmatch=True))
def test_valid_label_colors_are_normalised(api, repo, color):
    resp = api.create_label(OWNER, repo["name"], unique("label"), color)
    assert resp.status_code == 201, resp.text
    assert resp.json()["color"] == oracles.normalised_label_color(color)


@reuse_fixtures
@given(color=any_text.filter(lambda c: not oracles.is_hex_color(c)))
def test_invalid_label_colors_rejected(api, repo, color):
    assert api.create_label(OWNER, repo["name"], unique("label"), color).status_code == 422


@pytest.fixture
def repo_owner(api, temp_user):
    """Generated repository names go to a throwaway user, so they cannot clash with other tests' repos."""
    return temp_user["username"]


@reuse_fixtures
@given(name=st.text(st.sampled_from("abzAZ09._-/ é"), min_size=1, max_size=110)
       | st.sampled_from([".", "..", "-", "x.git", "X.WIKI", "a.rss", "b.atom", "a" * 100, "a" * 101]))
def test_repo_name_rules(api, repo_owner, name):
    resp = api.post(f"/admin/users/{repo_owner}/repos", json={"name": name})
    try:
        assert resp.status_code < 500, resp.text
        assert resp.status_code == (201 if oracles.repo_name_allowed(name) else 422), resp.text
        if resp.status_code == 201:
            assert resp.json()["name"] == name
    finally:
        if resp.status_code == 201:
            api.delete_repo(repo_owner, name)


@reuse_fixtures
@given(query=any_text.filter(lambda q: len(q) <= 100))
def test_search_never_fails(api, query):
    for path in ("/repos/search", "/users/search", "/repos/issues/search"):
        resp = api.get(path, params={"q": query, "limit": 5})
        assert resp.status_code == 200, f"{path}?q={query!r}: {resp.status_code} {resp.text[:200]}"


@reuse_fixtures
@given(page=st.integers(-10, 2**40), limit=st.integers(-10, 2**40))
def test_pagination_never_fails_and_caps_page_size(api, repo, page, limit):
    resp = api.list_issues(OWNER, repo["name"], page=page, limit=limit, state="all")
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) <= 50          # [api] MAX_RESPONSE_ITEMS


class IssueLifecycle(RuleBasedStateMachine):
    """Random sequences of create / edit / close / reopen / comment, checked against a dict after every step."""

    api: GiteaApi

    @initialize()
    def new_repo(self):
        self.repo = unique("prop-sm")
        self.api._ok(self.api.create_repo(self.repo))
        self.model: dict[int, dict] = {}   # number -> {"title", "state", "comments"}

    @rule(title=issue_titles)
    def create(self, title):
        number = self.api._ok(self.api.create_issue(OWNER, self.repo, title))["number"]
        assert number == len(self.model) + 1, "issue numbers must be sequential per repository"
        self.model[number] = {"title": oracles.stored_issue_title(title), "state": "open", "comments": 0}

    # Edits get titles that are already trimmed: the edit endpoint does not trim (BUG-012, pinned below).
    @rule(data=st.data(), title=issue_titles.filter(lambda t: t == oracles.go_trim_space(t)))
    def rename(self, data, title):
        assume(self.model)
        number = data.draw(st.sampled_from(sorted(self.model)))
        self.api._ok(self.api.edit_issue(OWNER, self.repo, number, title=title))
        self.model[number]["title"] = oracles.stored_issue_title(title)

    @rule(data=st.data(), state=st.sampled_from(["open", "closed"]))
    def set_state(self, data, state):
        assume(self.model)
        number = data.draw(st.sampled_from(sorted(self.model)))
        self.api._ok(self.api.edit_issue(OWNER, self.repo, number, state=state))
        self.model[number]["state"] = state

    @rule(data=st.data())
    def comment(self, data):
        assume(self.model)
        number = data.draw(st.sampled_from(sorted(self.model)))
        self.api._ok(self.api.add_comment(OWNER, self.repo, number, "property comment"))
        self.model[number]["comments"] += 1

    @invariant()
    def gitea_matches_model(self):
        if not hasattr(self, "repo"):
            return
        live = {i["number"]: {"title": i["title"], "state": i["state"], "comments": i["comments"]}
                for i in self.api._ok(self.api.list_issues(OWNER, self.repo, state="all", limit=50, type="issues"))}
        assert live == self.model
        open_count = self.api._ok(self.api.get_repo(OWNER, self.repo))["open_issues_count"]
        assert open_count == sum(i["state"] == "open" for i in self.model.values())

    def teardown(self):
        if hasattr(self, "repo"):
            self.api.delete_repo(OWNER, self.repo)


def test_issue_lifecycle_matches_model(api):
    IssueLifecycle.api = api
    # Each example creates a repository and runs up to 10 steps, so it gets a quarter of the profile's examples.
    budget = hsettings(max_examples=max(5, hsettings.default.max_examples // 4), stateful_step_count=10)
    run_state_machine_as_test(IssueLifecycle, settings=budget)


# --- BUG-011 ----------------------------------------------------------------
NUL = "before\x00after"


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-012: editing an issue title skips the create-time rules: "
                                       "no trimming, whitespace-only titles accepted")
@pytest.mark.parametrize("title, expected", [("  padded  ", "padded"), ("   ", None)], ids=["padded", "blank"])
def test_edit_title_follows_create_rules(api, issue, repo, title, expected):
    resp = api.edit_issue(OWNER, repo["name"], issue["number"], title=title)
    if expected is None:
        assert resp.status_code == 422, f"blank title accepted on edit: {resp.json()['title']!r}"
    else:
        assert resp.json()["title"] == expected


@pytest.fixture
def nul_requests(api, repo, issue):
    base = f"/repos/{OWNER}/{repo['name']}"
    return {
        "issue title": lambda: api.post(f"{base}/issues", json={"title": NUL}),
        "issue body": lambda: api.post(f"{base}/issues", json={"title": "t", "body": NUL}),
        "comment": lambda: api.post(f"{base}/issues/{issue['number']}/comments", json={"body": NUL}),
        "milestone": lambda: api.post(f"{base}/milestones", json={"title": NUL}),
        "label": lambda: api.post(f"{base}/labels", json={"name": NUL, "color": "#ff0000"}),
        "repo search": lambda: api.get("/repos/search", params={"q": NUL}),
    }


@pytest.mark.known_bug
@pytest.mark.xfail(strict=True, reason="BUG-011: a NUL character reaches PostgreSQL and the API answers 500 "
                                       "with the database driver's error message")
@pytest.mark.parametrize("target", ["issue title", "issue body", "comment", "milestone", "label", "repo search"])
def test_nul_character_rejected_cleanly(nul_requests, target):
    resp = nul_requests[target]()
    assert resp.status_code < 500, f"{target}: {resp.status_code} {resp.text[:200]}"
    assert "pq:" not in resp.text, "database driver errors must not reach the client"

