from src.registry.registry import LocatorRecord

_HEALING_PROMPT_V1 = """\
You are a test automation assistant. A Playwright locator has stopped working after a UI change.
Your job is to find a replacement CSS selector that points to the same element.

## Failed locator
- Logical name: {logical_name}
- Old selector: {old_selector}
- Description: {description}
- Expected ARIA role: {role}
- Expected text content: {expected_text}

## Current page DOM (trimmed)
{dom}

## Task
Return ONLY a JSON object — no prose, no markdown fences — in this exact shape:
{{"selector": "<CSS selector>", "confidence": <float 0.0-1.0>, "reasoning": "<one sentence>"}}
"""


def healing_prompt(record: LocatorRecord, dom: str) -> str:
    return _HEALING_PROMPT_V1.format(
        logical_name=record.name,
        old_selector=record.selector,
        description=record.description,
        role=record.role,
        expected_text=record.expected_text or "(none)",
        dom=dom,
    )
