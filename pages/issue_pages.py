from pages.base_page import BasePage


class NewIssuePage(BasePage):
    def __init__(self, page, owner: str, repo: str):
        super().__init__(page)
        self.path = f"/{owner}/{repo}/issues/new"
        self.title = page.locator("#issue_title")
        self.body = page.locator("form#new-issue textarea[name=content]")
        self.submit = page.get_by_role("button", name="Create Issue")

    def create(self, title: str, body: str = ""):
        self.title.fill(title)
        if body:
            self.body.fill(body)
        self.submit.click()
        return self


class IssuePage(BasePage):
    def __init__(self, page, owner: str, repo: str, number: int | None = None):
        super().__init__(page)
        self.path = f"/{owner}/{repo}/issues/{number}"
        self.heading = page.locator("#issue-title-display h1")
        self.state = page.locator(".issue-state-label")
        self.comment_box = page.locator("form#comment-form textarea[name=content]")
        self.comment_button = page.locator("form#comment-form").get_by_role("button", name="Comment", exact=True)
        self.close_button = page.locator("#status-button")
        self.comments = page.locator(".timeline-item.comment .render-content")

    def add_comment(self, text: str):
        self.comment_box.fill(text)
        self.comment_button.click()
        return self

    def close_issue(self):
        self.close_button.click()
        return self


class IssueListPage(BasePage):
    def __init__(self, page, owner: str, repo: str):
        super().__init__(page)
        self.path = f"/{owner}/{repo}/issues"
        self.titles = page.locator("#issue-list .flex-item-title a")
