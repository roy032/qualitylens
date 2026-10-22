"""Database checks: what the UI and API show must match what is stored.

Two kinds of test:
* Trace tests create data through the UI or API, then read the exact row back with SQL.
* Integrity rules (sql/integrity_checks.sql) scan the whole database for broken invariants.
Manual cases: TC-DB-*.
"""
from pathlib import Path

import allure
import pytest
from playwright.sync_api import expect

from pages.issue_pages import IssuePage, NewIssuePage
from pages.new_repo_page import NewRepoPage
from qualitylens.config import settings
from qualitylens.data import unique

pytestmark = [pytest.mark.db, allure.feature("Database")]
OWNER = settings.admin_user
_SQL = Path(__file__).parents[2].joinpath("sql/integrity_checks.sql").read_text()
_SQL = "\n".join(line.split("--")[0] for line in _SQL.splitlines())  # drop comments
RULES = [q.strip() for q in _SQL.split(";") if q.strip()]
RULE_NAMES = ["repo-issue-counters", "no-orphan-issues", "comment-counters", "label-counters",
              "closed-timestamp", "primary-email", "lower-names"]


def repo_row(db, name):
    return db.one("SELECT id, is_private, num_issues, num_closed_issues FROM repository "
                  "WHERE owner_name = %s AND lower_name = %s", (OWNER, name.lower()))


@pytest.mark.smoke
@allure.title("Issue created in the UI is stored with the right title, repo and author")
def test_ui_issue_matches_db(admin_page, repo, db):
    title = unique("DB trace issue")
    NewIssuePage(admin_page, OWNER, repo["name"]).open().create(title, "body from UI")
    expect(IssuePage(admin_page, OWNER, repo["name"], 1).heading).to_contain_text(title)

    row = db.one("""
        SELECT i.name AS title, i.content, i.is_closed, u.name AS author, r.name AS repo
        FROM issue i
        JOIN repository r ON r.id = i.repo_id
        JOIN "user" u     ON u.id = i.poster_id
        WHERE r.id = %s AND i.index = 1
    """, (repo["id"],))
    assert row == {"title": title, "content": "body from UI", "is_closed": False,
                   "author": OWNER, "repo": repo["name"]}


@allure.title("Private repository created in the UI is private in the database")
def test_ui_private_repo_matches_db(admin_page, api, db):
    name = unique("db-private")
    try:
        NewRepoPage(admin_page).open().create(name, private=True)
        expect(admin_page).to_have_url(f"{settings.base_url}/{OWNER}/{name}")
        assert repo_row(db, name)["is_private"] is True
    finally:
        api.delete_repo(OWNER, name)


@allure.title("Open/closed counters on the repository follow issue state changes")
def test_repo_counters_follow_issue_state(api, repo, db):
    numbers = [api._ok(api.create_issue(OWNER, repo["name"], f"counter {i}"))["number"] for i in range(3)]
    api.edit_issue(OWNER, repo["name"], numbers[0], state="closed")

    row = repo_row(db, repo["name"])
    assert (row["num_issues"], row["num_closed_issues"]) == (3, 1)

    counts = db.one("""
        SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE is_closed) AS closed
        FROM issue WHERE repo_id = %s AND is_pull = false
    """, (repo["id"],))
    assert counts == {"total": 3, "closed": 1}
    # ...and the API reports the same open count the database implies.
    assert api.get_repo(OWNER, repo["name"]).json()["open_issues_count"] == 2


@allure.title("Comment counter and stored text match what was posted")
def test_comments_stored(api, repo, issue, db):
    for text in ("first", "second"):
        api._ok(api.add_comment(OWNER, repo["name"], issue["number"], text))
    rows = db.query("""
        SELECT c.content FROM comment c
        WHERE c.issue_id = %s AND c.type = 0 ORDER BY c.id
    """, (issue["id"],))
    assert [r["content"] for r in rows] == ["first", "second"]
    assert db.one("SELECT num_comments FROM issue WHERE id = %s", (issue["id"],))["num_comments"] == 2


@allure.title("Deleting a repository removes its issues (no orphans)")
def test_repo_delete_cascades(api, db):
    name = unique("db-cascade")
    repo_id = api._ok(api.create_repo(name))["id"]
    api._ok(api.create_issue(OWNER, name, "will be deleted"))
    api.delete_repo(OWNER, name)
    assert db.one("SELECT COUNT(*) AS n FROM issue WHERE repo_id = %s", (repo_id,))["n"] == 0


@allure.title("Email uniqueness is enforced case-insensitively at the database level")
def test_email_stored_lowercase_unique(temp_user, db):
    rows = db.query("SELECT email, lower_email FROM email_address WHERE lower_email = %s",
                    (temp_user["email"].lower(),))
    assert len(rows) == 1


@pytest.mark.serial  # a counter checked while another worker is mid-write would look broken
@pytest.mark.parametrize("sql", RULES, ids=RULE_NAMES)
@allure.title("Integrity rule holds across the whole database")
def test_integrity_rule(db, sql):
    violations = db.query(sql)
    assert violations == [], f"{len(violations)} violating rows, e.g. {violations[:3]}"
