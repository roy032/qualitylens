"""Base class for all Page Objects.

A Page Object owns the selectors and actions for one screen. Tests talk to pages
("log in as X", "create issue Y") and never touch raw selectors, so a UI change
means editing one class instead of every test.
"""
from playwright.sync_api import Locator, Page, expect

from qualitylens.config import settings


class BasePage:
    path = "/"

    def __init__(self, page: Page):
        self.page = page

    def open(self):
        self.page.goto(f"{settings.base_url}{self.path}")
        return self

    @property
    def flash_error(self) -> Locator:
        return self.page.locator(".flash-error, .ui.negative.message")

    @property
    def flash_success(self) -> Locator:
        return self.page.locator(".flash-success, .ui.positive.message")

    @property
    def toast(self) -> Locator:
        return self.page.locator(".toastify")

    def user_menu(self) -> Locator:
        return self.page.get_by_label("Profile and Settings…")

    def expect_logged_in(self):
        expect(self.user_menu()).to_be_visible()

    def expect_logged_out(self):
        expect(self.page.get_by_role("link", name="Sign In")).to_be_visible()
