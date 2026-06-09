from src.config import settings
from src.framework.page import BasePage


def test_login_valid_credentials(base_page: BasePage) -> None:
    base_page.navigate(settings.base_url)
    base_page.resolve("username_input").fill("standard_user")
    base_page.resolve("password_input").fill("secret_sauce")
    base_page.resolve("login_button").click()
    base_page.resolve("inventory_container").wait_for()


def test_login_invalid_credentials(base_page: BasePage) -> None:
    base_page.navigate(settings.base_url)
    base_page.resolve("username_input").fill("standard_user")
    base_page.resolve("password_input").fill("wrong_password")
    base_page.resolve("login_button").click()
    base_page.resolve("error_message").wait_for()
