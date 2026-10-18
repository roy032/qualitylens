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
        if private:
            self.private.check()
        self.submit.click()
        return self
