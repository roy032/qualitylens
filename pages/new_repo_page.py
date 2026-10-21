from pages.base_page import BasePage


class NewRepoPage(BasePage):
    path = "/repo/create"

    def __init__(self, page):
        super().__init__(page)
        self.name = page.locator("#repo_name")
        self.description = page.locator("#description")
        self.private = page.locator("input[name=private]")
        self.submit = page.get_by_role("button", name="Create Repository")

    def create(self, name: str, description: str = "", private: bool = False):
        self.name.fill(name)
        if description:
            self.description.fill(description)
        # Always set the box explicitly: Gitea pre-ticks it when the user's last repository was private
        # (repository.DEFAULT_PRIVATE = last), so relying on the default made tests order-dependent.
        self.private.set_checked(private)
        self.submit.click()
        return self
