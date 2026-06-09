from playwright.sync_api import Page

from src.config import settings
from src.framework.page import BasePage
from src.registry.registry import LocatorRegistry


def test_login_valid_credentials(page: Page, registry: LocatorRegistry) -> None:
    bp = BasePage(page, registry)
    bp.navigate(settings.base_url)
    bp.resolve("username_input").fill("standard_user")
    bp.resolve("password_input").fill("secret_sauce")
    bp.resolve("login_button").click()
    bp.resolve("inventory_container").wait_for()


def test_login_invalid_credentials(page: Page, registry: LocatorRegistry) -> None:
    bp = BasePage(page, registry)
    bp.navigate(settings.base_url)
    bp.resolve("username_input").fill("standard_user")
    bp.resolve("password_input").fill("wrong_password")
    bp.resolve("login_button").click()
    bp.resolve("error_message").wait_for()
