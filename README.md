# Self-Healing AI Test Framework

![CI](https://github.com/AndreiTita99/Self-Healing-AI-Test/actions/workflows/ci.yml/badge.svg)

A Playwright-based end-to-end test framework where an LLM (1) generates test cases from
plain-English user stories and (2) repairs broken element locators automatically when the UI
changes, instead of just failing the test.

## The problem

Flaky, high-maintenance tests are the single biggest pain point in test automation. When a
developer renames a CSS class or restructures the DOM, dozens of tests break even though the
app still works. This framework attacks that directly: it keeps a normal, fast, deterministic
test suite, but when a locator breaks at runtime, an LLM inspects the new page, proposes a
corrected locator, validates it, and retries — turning a red build into a self-documenting heal.

## Architecture

```
+-------------------+        +------------------------+
|  Test Generator   |        |   pytest test suite    |
|  (English -> JSON  | -----> |   (page objects +      |
|   -> test file)   |        |    locator registry)   |
+-------------------+        +-----------+------------+
                                         |
                              locator lookup fails (timeout / not found)
                                         v
                             +-----------------------+
                             |   Healing Engine      |
                             |  - capture DOM        |
                             |  - ask LLM for fix    |
                             |  - VALIDATE candidate |
                             |  - retry action       |
                             +-----------+-----------+
                                         |
                                         v
                             +-----------------------+
                             |  Heal Report (md/json)|
                             |  + registry update    |
                             |    (proposed diff)    |
                             +-----------------------+
```

## Quick start

```bash
# 1. Clone and create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Copy and configure environment
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env (only needed for healing + generation)

# 4. Run the suite
pytest tests/ -v
```

## Project structure

```
src/
  config.py            # typed settings via pydantic-settings
  llm/
    client.py          # thin Anthropic SDK wrapper
    prompts.py         # versioned prompt templates
  registry/
    locators.yaml      # logical_name -> selector + metadata
    registry.py        # load / lookup / propose-diff
  framework/
    page.py            # BasePage — resolve() goes through healing
    healing.py         # healing engine
    reporter.py        # collects heal events -> report.md + report.json
  generator/
    generate.py        # CLI: story.txt -> JSON plan -> pytest file
tests/
  conftest.py          # Playwright fixtures + reporter hooks
  test_login.py        # login flow tests
```

## Design decisions

**Determinism boundary** — the LLM is called *only* at two moments: test-generation time and
the instant a locator fails. Normal passing runs make zero LLM calls, keeping the suite fast,
cheap, and fully deterministic.

**Validation gate** — before trusting a healed selector, the engine checks that it (a) resolves
to exactly one element, (b) matches the expected ARIA role, and (c) matches expected text if
specified. Without this, the LLM can "heal" a test into a false pass by pointing at the wrong
element.

**Propose, don't auto-commit** — healed selectors are written to a diff report; a human
approves the registry change via PR. This preserves git history and keeps the suite's
trustworthiness under human oversight.

**Human-in-the-loop generation** — generated test files are reviewed and committed by a human
before they enter the suite. The LLM produces a plan; deterministic code templating produces
the file; you decide if it's correct.

## Deliberately out of scope

- Healing anything other than element locators (no AI-powered assertion repair)
- A web dashboard — a clean terminal + markdown report is sufficient
- Multiple LLM providers — one provider behind one interface
- Visual regression, mobile, or cross-browser matrices

## Target app under test

[Sauce Demo](https://www.saucedemo.com) — a stable public sandbox maintained for automation
practice.
