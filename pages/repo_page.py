from pages.base_page import BasePage


class RepoPage(BasePage):
    def __init__(self, page, owner: str, repo: str):
        super().__init__(page)
        self.path = f"/{owner}/{repo}"
        self.title = page.locator(".repo-header .flex-item-title")
        self.private_badge = page.locator(".repo-header").get_by_text("Private", exact=True)
        self.issues_tab = page.locator(".repository .secondary.menu").get_by_role("link", name="Issues")
