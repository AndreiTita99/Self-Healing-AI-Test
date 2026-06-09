import logging
from dataclasses import dataclass

from playwright.sync_api import Locator
from playwright.sync_api import Page as PlaywrightPage

from src.config import settings
from src.framework.reporter import HealEvent, Reporter
from src.llm.client import LLMClient
from src.llm.prompts import healing_prompt
from src.registry.registry import LocatorRecord

logger = logging.getLogger(__name__)


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
        proposal = self._get_proposal(record, page)
        if proposal is None:
            return None

        if proposal.confidence < settings.heal_confidence_threshold:
            logger.info(
                "Heal rejected for '%s': confidence %.2f below threshold %.2f",
                record.name,
                proposal.confidence,
                settings.heal_confidence_threshold,
            )
            self._record_event(test_name, record, proposal, applied=False)
            return None

        if not self._validate(proposal.selector, record, page):
            logger.warning(
                "Heal proposal failed validation for '%s': selector=%r",
                record.name,
                proposal.selector,
            )
            self._record_event(test_name, record, proposal, applied=False)
            return None

        logger.info(
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

    def _get_proposal(self, record: LocatorRecord, page: PlaywrightPage) -> HealProposal | None:
        dom = page.evaluate("document.body.innerHTML")[:20_000]
        prompt = healing_prompt(record, dom)
        try:
            raw = self._llm.complete(prompt)
            return self._parse_response(raw)
        except Exception as exc:
            logger.warning("LLM call failed for '%s': %s", record.name, exc)
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
