from pages.base_page import BasePage


class RegisterPage(BasePage):
    path = "/user/sign_up"

    def __init__(self, page):
        super().__init__(page)
        self.username = page.locator("#user_name")
        self.email = page.locator("#email")
        self.password = page.locator("#password")
        self.retype = page.locator("#retype")
        self.submit = page.get_by_role("button", name="Register Account")

    def register(self, username: str, email: str, password: str, retype: str | None = None):
        self.username.fill(username)
        self.email.fill(email)
        self.password.fill(password)
        self.retype.fill(password if retype is None else retype)
        self.submit.click()
        return self
