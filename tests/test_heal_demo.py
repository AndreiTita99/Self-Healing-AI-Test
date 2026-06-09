"""
Demonstrates self-healing end to end.

Two variants:
  test_broken_login_button_heals      — stub LLM response, runs always (no API key needed)
  test_broken_login_button_heals_live — real Anthropic API, skipped without ANTHROPIC_API_KEY

The broken locator '#login-btn' does not exist on saucedemo.com.
The healing engine captures the DOM, feeds it (real or stub) to the LLM,
validates the candidate selector, and retries the click — all without the
test knowing anything went wrong.
"""

import os

import pytest

from src.config import settings
from src.framework.healing import HealingEngine
from src.framework.page import BasePage


class _StubLLMClient:
    """Returns a pre-recorded correct response — no API call, no cost."""

    def complete(self, prompt: str) -> str:
        return (
            '{"selector": "#login-button", "confidence": 0.97, '
            '"reasoning": "The login form submit button has id=login-button on saucedemo.com"}'
        )


@pytest.fixture
def stub_base_page(page, registry, reporter, request):
    engine = HealingEngine(_StubLLMClient(), reporter)
    return BasePage(page, registry, engine, test_name=request.node.name)


def test_broken_login_button_heals(stub_base_page: BasePage) -> None:
    """Full healing flow with a stub LLM — DOM capture, validation, and retry all run for real."""
    stub_base_page.navigate(settings.base_url)
    stub_base_page.resolve("username_input").fill("standard_user")
    stub_base_page.resolve("password_input").fill("secret_sauce")
    # '#login-btn' does not exist — healed to '#login-button' via stub response
    stub_base_page.resolve("login_button_broken").click()
    stub_base_page.resolve("inventory_container").wait_for()


@pytest.mark.skipif(
    not os.getenv("LIVE_TESTS"),
    reason="set LIVE_TESTS=1 to run against the real Anthropic API",
)
def test_broken_login_button_heals_live(base_page: BasePage) -> None:
    """Same scenario using the real Anthropic API.

    Run with: LIVE_TESTS=1 pytest tests/test_heal_demo.py
    """
    base_page.navigate(settings.base_url)
    base_page.resolve("username_input").fill("standard_user")
    base_page.resolve("password_input").fill("secret_sauce")
    base_page.resolve("login_button_broken").click()
    base_page.resolve("inventory_container").wait_for()
