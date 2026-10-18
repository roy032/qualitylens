from pages.base_page import BasePage


class LoginPage(BasePage):
    path = "/user/login"

    def __init__(self, page):
        super().__init__(page)
        self.username = page.locator("#user_name")
        self.password = page.locator("#password")
        self.remember = page.locator("input[name=remember]")
        self.submit = page.get_by_role("button", name="Sign In")

    def login(self, username: str, password: str, remember: bool = False):
        self.username.fill(username)
        self.password.fill(password)
        if remember:
            self.remember.check()
        self.submit.click()
        return self
