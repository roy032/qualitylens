"""Issue lifecycle through the UI: create, comment, close. Manual cases: TC-ISSUE-*."""
import allure
import pytest
from playwright.sync_api import expect

from pages.issue_pages import IssueListPage, IssuePage, NewIssuePage
from suite.config import settings
from suite.data import unique

pytestmark = [pytest.mark.ui, allure.feature("Issues")]
OWNER = settings.admin_user


@pytest.mark.smoke
@allure.title("Create an issue with title and description")
def test_create_issue(admin_page, repo):
    title = unique("Login button unresponsive")
    NewIssuePage(admin_page, OWNER, repo["name"]).open().create(title, "Steps: click login twice")
    expect(admin_page).to_have_url(f"{settings.base_url}/{OWNER}/{repo['name']}/issues/1")
    issue = IssuePage(admin_page, OWNER, repo["name"], 1)
    expect(issue.heading).to_contain_text(title)
    expect(issue.state).to_have_text("Open")
    expect(issue.comments.first).to_contain_text("Steps: click login twice")


@pytest.mark.parametrize("title", ["   ", "\t"], ids=["spaces", "tab"])
@allure.title("Whitespace-only title is rejected in the UI")
def test_whitespace_title_rejected(admin_page, repo, title):
    page = NewIssuePage(admin_page, OWNER, repo["name"]).open().create(title)
    expect(page.toast).to_contain_text("Title cannot be empty")
    expect(admin_page).to_have_url(f"{settings.base_url}/{OWNER}/{repo['name']}/issues/new")


@allure.title("Issue title field enforces the 255 character limit")
def test_issue_title_maxlength(admin_page, repo):
    page = NewIssuePage(admin_page, OWNER, repo["name"]).open()
    page.title.fill("x" * 300)
    assert len(page.title.input_value()) == 255


@allure.title("Add a comment to an issue")
def test_comment_on_issue(admin_page, repo, issue):
    page = IssuePage(admin_page, OWNER, repo["name"], issue["number"]).open()
    page.add_comment("Reproduced on Chrome 141")
    expect(page.comments.last).to_have_text("Reproduced on Chrome 141")


@allure.title("Closing an issue updates its state and the open/closed counters")
def test_close_issue(admin_page, repo, issue, api):
    page = IssuePage(admin_page, OWNER, repo["name"], issue["number"]).open()
    page.close_issue()
    expect(page.state).to_have_text("Closed")
    assert api.get_issue(OWNER, repo["name"], issue["number"]).json()["state"] == "closed"
    assert api.get_repo(OWNER, repo["name"]).json()["open_issues_count"] == 0


@allure.title("New issue appears in the repository issue list")
def test_issue_listed(admin_page, repo, issue):
    page = IssueListPage(admin_page, OWNER, repo["name"]).open()
    expect(page.titles.filter(has_text=issue["title"])).to_have_count(1)
