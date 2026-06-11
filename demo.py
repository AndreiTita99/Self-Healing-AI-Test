import os
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from src.config import settings
from src.framework.healing import HealingEngine
from src.framework.reporter import Reporter
from src.registry.registry import LocatorRegistry

SLOW_MO_MS = 700  # delay per browser action so a human can follow along
BEAT = 2.5  # default seconds to dwell on a narration beat
BAR = "=" * 64


class _StubLLMClient:
    """Returns a pre-recorded correct response -- no API call, no cost."""

    def complete(self, prompt: str) -> str:
        return (
            '{"selector": "#login-button", "confidence": 0.97, '
            '"reasoning": "The login form submit button has id=login-button on saucedemo.com"}'
        )


def _make_llm():
    """Real Anthropic client when LIVE_TESTS=1 and a key is set, else the stub."""
    if os.getenv("LIVE_TESTS") and settings.anthropic_api_key:
        from src.llm.client import LLMClient

        return LLMClient()
    return _StubLLMClient()


def say(*lines: str, beat: float = BEAT) -> None:
    """Print a plain-English narration beat, then pause so it can be read on camera."""
    print()
    for line in lines:
        print(f"  {line}")
    print(flush=True)
    time.sleep(beat)


def main() -> None:
    registry = LocatorRegistry()
    reporter = Reporter()
    engine = HealingEngine(_make_llm(), reporter)

    print("\n" + BAR)
    print("  SELF-HEALING TEST DEMO")
    print("  An automated login test that repairs itself when the app changes.")
    print(BAR, flush=True)
    time.sleep(2.5)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=SLOW_MO_MS)
        page = browser.new_page()
        page.set_default_timeout(settings.locator_timeout_ms)

        # 1. Open the login page and fill in valid credentials (slow + visible).
        say("Step 1  Opening the login page and entering valid credentials...", beat=1)
        page.goto(settings.base_url)
        page.locator(registry.get("username_input").selector).fill("standard_user")
        page.locator(registry.get("password_input").selector).fill("secret_sauce")

        # 2. The broken attempt: the test looks for an outdated button name.
        broken = registry.get("login_button_broken")
        say(
            "Step 2  The test clicks 'Login'.",
            f"        A developer renamed that button, but the test still looks for: {broken.selector}",
            "        Watch the browser -- nothing happens. The button can't be found.",
            beat=1,
        )
        try:
            page.locator(broken.selector).click(timeout=3000)
        except PlaywrightTimeoutError:
            say(
                "[X]  BUTTON NOT FOUND -- the test is stuck.",
                "     Normally this means a broken test and a failed (red) build,",
                "     and a QA engineer has to hunt down the new button name by hand.",
                beat=3,
            )

        # 3. Self-heal: inspect the live page, ask the AI, validate, repair.
        say("Step 3  Instead, the self-healing engine takes over:", beat=1)
        new_selector = engine.heal(broken, page, test_name="demo_login")

        if not new_selector:
            say("[X]  Healing could not find a safe replacement. Stopping demo.")
            browser.close()
            return

        # 4. Retry the action with the repaired locator -> success.
        say("Step 4  Retrying the click with the repaired locator...", beat=1)
        page.locator(new_selector).click()
        page.locator(registry.get("inventory_container").selector).wait_for()

        say(
            "[OK]  LOGGED IN -- we're on the Products page.",
            "      The test passed. The locator was repaired automatically, with no human edits.",
            beat=2,
        )
        time.sleep(5)  # dwell on the Products page for the recording
        browser.close()

    reporter.write(passed=1, failed=0)
    print(BAR)
    print("  A full report was written to report.md")
    print("  (old selector, new selector, confidence, and the AI's reasoning).")
    print(BAR + "\n", flush=True)


if __name__ == "__main__":
    main()
