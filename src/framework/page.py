from playwright.sync_api import Locator
from playwright.sync_api import Page as PlaywrightPage

from src.registry.registry import LocatorRegistry


class BasePage:
    def __init__(self, page: PlaywrightPage, registry: LocatorRegistry) -> None:
        self._page = page
        self._registry = registry

    def navigate(self, url: str) -> None:
        self._page.goto(url)

    def resolve(self, logical_name: str) -> Locator:
        record = self._registry.get(logical_name)
        return self._page.locator(record.selector)
