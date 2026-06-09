import json
import logging
from dataclasses import dataclass

from playwright.sync_api import Page as PlaywrightPage

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

    def propose(
        self, record: LocatorRecord, page: PlaywrightPage, test_name: str
    ) -> HealProposal | None:
        dom = self._capture_dom(page)
        prompt = healing_prompt(record, dom)

        try:
            raw = self._llm.complete(prompt)
            proposal = self._parse_response(raw)
        except Exception as exc:
            logger.warning("LLM call failed during healing of '%s': %s", record.name, exc)
            return None

        logger.info(
            "Heal proposal for '%s': selector=%r confidence=%.2f | %s",
            record.name,
            proposal.selector,
            proposal.confidence,
            proposal.reasoning,
        )

        self._reporter.record_heal(
            HealEvent(
                test_name=test_name,
                logical_name=record.name,
                old_selector=record.selector,
                proposed_selector=proposal.selector,
                confidence=proposal.confidence,
                reasoning=proposal.reasoning,
                applied=False,  # Phase 3: log proposal only; retry added in Phase 4
            )
        )

        return proposal

    def _capture_dom(self, page: PlaywrightPage) -> str:
        html: str = page.evaluate("document.body.innerHTML")
        return html[:20_000]

    def _parse_response(self, raw: str) -> HealProposal:
        text = raw.strip()
        # Strip markdown fences in case the model wraps despite instructions
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
