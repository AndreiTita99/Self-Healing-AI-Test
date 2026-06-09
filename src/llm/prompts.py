from src.registry.registry import LocatorRecord

_GENERATION_PROMPT_V1 = """\
You are a test automation engineer. Given a plain-English acceptance criterion, produce a \
structured JSON test plan.

## Acceptance criterion
{story}

## Available locators
{locators}

## Rules
- Only use logical names from the Available locators list above.
- Actions must be one of: navigate, fill, click, assert_visible, assert_text.
- test_name must be snake_case and start with "test_".
- Each distinct scenario in the story becomes one TestCase.
- For navigate: set target to null, value to the URL.
- For assert_visible / click: set value to null.

## Response format
Return ONLY a JSON object — no prose, no markdown fences:
{{
  "source_story": "{story_name}",
  "tests": [
    {{
      "test_name": "test_snake_case_name",
      "description": "one line description",
      "steps": [
        {{"action": "navigate", "target": null, "value": "<url>"}},
        {{"action": "fill", "target": "<logical_name>", "value": "<text>"}},
        {{"action": "click", "target": "<logical_name>", "value": null}},
        {{"action": "assert_visible", "target": "<logical_name>", "value": null}}
      ]
    }}
  ]
}}
"""


def generation_prompt(story: str, locators: str, story_name: str = "story") -> str:
    return _GENERATION_PROMPT_V1.format(story=story, locators=locators, story_name=story_name)




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
