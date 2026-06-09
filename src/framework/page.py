from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import Locator
from playwright.sync_api import Page as PlaywrightPage
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.registry.registry import LocatorRecord, LocatorRegistry

if TYPE_CHECKING:
    from src.framework.healing import HealingEngine


class HealableLocator:
    """Proxies a Playwright Locator; on TimeoutError calls the healing engine and retries."""

    def __init__(
        self,
        locator: Locator,
        page: PlaywrightPage,
        record: LocatorRecord,
        engine: HealingEngine,
        test_name: str,
    ) -> None:
        self._locator = locator
        self._page = page
        self._record = record
        self._engine = engine
        self._test_name = test_name

    def __getattr__(self, name: str):
        attr = getattr(self._locator, name)
        if not callable(attr):
            return attr

        def wrapper(*args, **kwargs):
            try:
                return attr(*args, **kwargs)
            except PlaywrightTimeoutError:
                try:
                    new_selector = self._engine.heal(
                        self._record, self._page, self._test_name
                    )
                except Exception:
                    new_selector = None

                if new_selector is not None:
                    healed = self._page.locator(new_selector)
                    return getattr(healed, name)(*args, **kwargs)
                raise

        return wrapper


class BasePage:
    def __init__(
        self,
        page: PlaywrightPage,
        registry: LocatorRegistry,
        healing_engine: HealingEngine | None = None,
        test_name: str = "",
    ) -> None:
        self._page = page
        self._registry = registry
        self._healing_engine = healing_engine
        self._test_name = test_name

    def navigate(self, url: str) -> None:
        self._page.goto(url)

    def resolve(self, logical_name: str) -> Locator | HealableLocator:
        record = self._registry.get(logical_name)
        locator = self._page.locator(record.selector)
        if self._healing_engine is not None:
            return HealableLocator(
                locator, self._page, record, self._healing_engine, self._test_name
            )
        return locator
