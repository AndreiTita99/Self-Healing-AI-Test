"""CLI: plain-English story -> JSON plan -> pytest file.

Usage
-----
LLM mode (requires ANTHROPIC_API_KEY with credits):
    python -m src.generator.generate --story stories/login.txt --out tests/test_login_gen.py

Plan mode (skip LLM, use a pre-existing plan file):
    python -m src.generator.generate --plan stories/login.plan.json --out tests/test_login_gen.py

The generated file should be reviewed before committing. The LLM produces the plan;
deterministic Python templating (codegen.py) produces the test code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.generator.codegen import render
from src.generator.schema import TestPlan


def _plan_from_llm(story_path: Path) -> TestPlan:
    from src.llm.client import LLMClient
    from src.llm.prompts import generation_prompt
    from src.registry.registry import LocatorRegistry

    story = story_path.read_text(encoding="utf-8")
    registry = LocatorRegistry()
    locators = "\n".join(
        f"  {name}: {rec.description}" for name, rec in registry.all().items()
    )
    prompt = generation_prompt(story=story, locators=locators, story_name=story_path.name)

    raw = LLMClient().complete(prompt)
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return TestPlan.model_validate(json.loads(text.strip()))


def _plan_from_file(plan_path: Path) -> TestPlan:
    return TestPlan.model_validate(json.loads(plan_path.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate pytest tests from a plain-English story"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--story", metavar="FILE", help="Plain-English story .txt file (calls LLM)"
    )
    source.add_argument(
        "--plan", metavar="FILE", help="Pre-existing JSON plan file (skips LLM)"
    )
    parser.add_argument("--out", required=True, metavar="FILE", help="Output .py file")
    args = parser.parse_args(argv)

    if args.story:
        plan = _plan_from_llm(Path(args.story))
        story_ref = args.story
    else:
        plan = _plan_from_file(Path(args.plan))
        story_ref = plan.source_story

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(plan, story_ref), encoding="utf-8")

    print(f"Generated {len(plan.tests)} test(s) -> {out_path}")
    for tc in plan.tests:
        print(f"  {tc.test_name} ({len(tc.steps)} steps)")


if __name__ == "__main__":
    main()
