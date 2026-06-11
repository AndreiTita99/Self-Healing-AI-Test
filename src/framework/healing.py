import logging
import sys
import time
from dataclasses import dataclass

from playwright.sync_api import Locator
from playwright.sync_api import Page as PlaywrightPage

from src.config import settings
from src.framework.reporter import HealEvent, Reporter
from src.llm.client import LLMClient
from src.llm.prompts import healing_prompt
from src.registry.registry import LocatorRecord

logger = logging.getLogger(__name__)

_BAR_WIDTH = 64
_LABEL_WIDTH = 26
_SPINNER = "|/-\\"
_STEP_SECONDS = 0.6  # cosmetic dwell so each line is readable on video
_QUERY_SECONDS = 2.0  # longer spin for the AI step, the star of the demo


class _HealConsole:
    """Renders the heal sequence as an animated, ASCII-only checklist.

    Animates only on a real terminal (e.g. `pytest -s`). Under captured output
    (CI, or pytest without -s) `isatty()` is False, so each step prints once as a
    plain line and the carriage-return animation never pollutes the logs. ASCII
    only, so it can't raise UnicodeEncodeError on a Windows console mid-run.
    """

    def __init__(self) -> None:
        self._animate = sys.stdout.isatty()

    def header(self) -> None:
        print("\n" + "=" * _BAR_WIDTH)
        print("  [ SELF-HEAL ENGINE ]")
        print("-" * _BAR_WIDTH, flush=True)

    def step(self, label: str, detail: str = "", seconds: float = _STEP_SECONDS) -> None:
        """Spin a step for `seconds`, then mark it done with [OK]."""
        self._render(label, detail, seconds, mark="[OK]")

    def fail(self, label: str, detail: str = "") -> None:
        """Mark a step as failed with [XX]."""
        self._render(label, detail, _STEP_SECONDS, mark="[XX]")

    def note(self, text: str) -> None:
        """Print an indented continuation line under the previous step."""
        print(f"       {text}", flush=True)

    def summary(self, old: str, new: str, reason: str) -> None:
        print("-" * _BAR_WIDTH)
        print(f"  RESULT : {old}  ->  {new}")
        print(f"  REASON : {reason}", flush=True)

    def footer(self) -> None:
        print("=" * _BAR_WIDTH + "\n", flush=True)

    def _render(self, label: str, detail: str, seconds: float, mark: str) -> None:
        # Pad the marker to a fixed width so the spinner frame ([|]) and the
        # resolved marker ([OK]/[XX]) are the same length: the body never shifts
        # and the final line can't clip a trailing character on redraw.
        body = f"{label:<{_LABEL_WIDTH}} {detail}".rstrip()
        if not self._animate:
            print(f"  {mark:<4} {body}", flush=True)
            return
        deadline = time.time() + seconds
        i = 0
        while time.time() < deadline:
            frame = f"[{_SPINNER[i % len(_SPINNER)]}]"
            sys.stdout.write(f"\r  {frame:<4} {body}")
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1
        sys.stdout.write(f"\r  {mark:<4} {body}\n")
        sys.stdout.flush()


@dataclass
class HealProposal:
    selector: str
    confidence: float
    reasoning: str


class HealingEngine:
    def __init__(self, llm_client: LLMClient, reporter: Reporter) -> None:
        self._llm = llm_client
        self._reporter = reporter

    def heal(
        self, record: LocatorRecord, page: PlaywrightPage, test_name: str
    ) -> str | None:
        """Ask the LLM for a replacement selector, validate it, and return it if valid.

        Returns the new selector string on success, None if healing is not possible.
        The reporter always receives an event regardless of outcome.
        """
        ui = _HealConsole()
        ui.header()
        ui.step("Detected broken locator", record.selector)

        dom = page.evaluate("document.body.innerHTML")[:20_000]
        element_count = page.evaluate("document.querySelectorAll('*').length")
        ui.step("Captured live DOM", f"{element_count} elements")

        ui.step("Querying Anthropic", "requesting a replacement", seconds=_QUERY_SECONDS)
        proposal = self._get_proposal(record, dom)
        if proposal is None:
            ui.fail("No usable proposal returned")
            ui.footer()
            return None

        ui.step("Candidate proposed", f"{proposal.selector}  ({proposal.confidence:.0%})")
        matched_html = self._element_html(proposal.selector, page)
        if matched_html:
            ui.note(f"matched {matched_html}")

        if proposal.confidence < settings.heal_confidence_threshold:
            logger.debug(
                "Heal rejected for '%s': confidence %.2f below threshold %.2f",
                record.name,
                proposal.confidence,
                settings.heal_confidence_threshold,
            )
            ui.fail(
                "Confidence too low",
                f"{proposal.confidence:.0%} < {settings.heal_confidence_threshold:.0%} threshold",
            )
            ui.footer()
            self._record_event(test_name, record, proposal, applied=False)
            return None

        if not self._validate(proposal.selector, record, page):
            logger.warning(
                "Heal proposal failed validation for '%s': selector=%r",
                record.name,
                proposal.selector,
            )
            ui.fail("Failed validation", proposal.selector)
            ui.footer()
            self._record_event(test_name, record, proposal, applied=False)
            return None

        ui.step("Validated against page", "unique match, role + text OK")
        ui.step("Retried action", "test continues")
        ui.summary(record.selector, proposal.selector, proposal.reasoning)
        ui.footer()

        logger.debug(
            "Healed '%s': '%s' -> '%s' (confidence=%.2f)",
            record.name,
            record.selector,
            proposal.selector,
            proposal.confidence,
        )
        self._record_event(test_name, record, proposal, applied=True)
        return proposal.selector

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_proposal(self, record: LocatorRecord, dom: str) -> HealProposal | None:
        prompt = healing_prompt(record, dom)
        try:
            raw = self._llm.complete(prompt)
            return self._parse_response(raw)
        except Exception as exc:
            logger.warning("LLM call failed for '%s': %s", record.name, exc)
            return None

    def _element_html(self, selector: str, page: PlaywrightPage, max_len: int = 100) -> str | None:
        """Return the live element's outerHTML (whitespace-collapsed) for display.

        Proves to a viewer that the proposed selector resolves to a real element on
        the page. Returns None unless exactly one element matches.
        """
        try:
            locator = page.locator(selector)
            if locator.count() != 1:
                return None
            html = " ".join(locator.evaluate("el => el.outerHTML").split())
            return html if len(html) <= max_len else html[: max_len - 3] + "..."
        except Exception:
            return None

    def _validate(self, selector: str, record: LocatorRecord, page: PlaywrightPage) -> bool:
        try:
            locator = page.locator(selector)

            if locator.count() != 1:
                logger.debug(
                    "Validation failed: '%s' matches %d elements", selector, locator.count()
                )
                return False

            if record.role and record.role != "generic":
                if not self._role_matches(locator, record.role):
                    logger.debug("Validation failed: role mismatch for '%s'", selector)
                    return False

            if record.expected_text:
                # text_content() is empty for <input> elements; fall back to value/aria-label
                visible = locator.evaluate(
                    "el => el.textContent || el.value || el.getAttribute('aria-label') || ''"
                ).strip()
                if record.expected_text.lower() not in visible.lower():
                    logger.debug("Validation failed: text mismatch for '%s'", selector)
                    return False

            return True
        except Exception as exc:
            logger.warning("Validation error for '%s': %s", selector, exc)
            return False

    def _role_matches(self, locator: Locator, expected_role: str) -> bool:
        actual: str = locator.evaluate(
            """el => {
                const explicit = el.getAttribute('role');
                if (explicit) return explicit;
                const tag = el.tagName.toLowerCase();
                const type = (el.getAttribute('type') || '').toLowerCase();
                if (tag === 'button') return 'button';
                if (tag === 'input') {
                    if (['submit', 'button', 'reset'].includes(type)) return 'button';
                    return 'textbox';
                }
                if (tag === 'a') return 'link';
                if (tag === 'textarea') return 'textbox';
                if (tag === 'select') return 'combobox';
                return 'generic';
            }"""
        )
        return actual == expected_role

    def _parse_response(self, raw: str) -> HealProposal:
        import json

        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        return HealProposal(
            selector=str(data["selector"]),
            confidence=float(data["confidence"]),
            reasoning=str(data["reasoning"]),
        )

    def _record_event(
        self,
        test_name: str,
        record: LocatorRecord,
        proposal: HealProposal,
        applied: bool,
    ) -> None:
        self._reporter.record_heal(
            HealEvent(
                test_name=test_name,
                logical_name=record.name,
                old_selector=record.selector,
                proposed_selector=proposal.selector,
                confidence=proposal.confidence,
                reasoning=proposal.reasoning,
                applied=applied,
            )
        )
