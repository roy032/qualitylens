"""Creating repositories through the UI. Manual cases: TC-REPO-*."""
import allure
import pytest
from playwright.sync_api import expect

from pages.new_repo_page import NewRepoPage
from pages.repo_page import RepoPage
from qualitylens.config import settings
from qualitylens.data import unique

pytestmark = [pytest.mark.ui, allure.feature("Repositories")]
OWNER = settings.admin_user


@pytest.fixture
def repo_name(api):
    name = unique("ui-repo")
    yield name
    api.delete_repo(OWNER, name)


@pytest.mark.smoke
@allure.title("Create a public repository")
def test_create_public_repo(admin_page, repo_name, api):
    NewRepoPage(admin_page).open().create(repo_name, description="Created by Playwright")
    expect(admin_page).to_have_url(f"{settings.base_url}/{OWNER}/{repo_name}")
    repo = RepoPage(admin_page, OWNER, repo_name)
    expect(repo.title).to_contain_text(repo_name)
    expect(repo.private_badge).to_have_count(0)
    # The API must agree with what the UI just did.
    assert api.get_repo(OWNER, repo_name).json()["private"] is False


@allure.title("Create a private repository shows the Private badge")
def test_create_private_repo(admin_page, repo_name, api):
    NewRepoPage(admin_page).open().create(repo_name, private=True)
    expect(RepoPage(admin_page, OWNER, repo_name).private_badge).to_be_visible()
    assert api.get_repo(OWNER, repo_name).json()["private"] is True


@allure.title("Duplicate repository name is rejected")
def test_duplicate_repo_name(admin_page, repo):
    page = NewRepoPage(admin_page).open().create(repo["name"])
    expect(page.flash_error).to_have_text("The repository name is already used.")


@pytest.mark.parametrize("bad_name", ["has space", "semi;colon", "ends.git"])
@allure.title("Invalid repository names are rejected")
def test_invalid_repo_name(admin_page, bad_name):
    page = NewRepoPage(admin_page).open().create(bad_name)
    expect(page.flash_error).to_be_visible()
    expect(admin_page).to_have_url(f"{settings.base_url}/repo/create")


@allure.title("Repository name field enforces the 100 character limit")
def test_repo_name_maxlength(admin_page):
    page = NewRepoPage(admin_page).open()
    page.name.fill("a" * 150)
    assert len(page.name.input_value()) == 100
