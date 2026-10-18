from pages.base_page import BasePage


class DashboardPage(BasePage):
    path = "/"

    def logout(self):
        self.user_menu().click()
        self.page.get_by_role("menuitem", name="Sign Out").click()
        return self
