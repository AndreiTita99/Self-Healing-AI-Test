# Self-Healing AI Test Framework — Project Spec

> A Playwright-based end-to-end test framework where an LLM (1) generates test cases
> from plain-English user stories and (2) repairs broken element locators automatically
> when the UI changes, instead of just failing the test.

This document is the build spec. Hand it to Claude Code phase by phase. Each phase is
self-contained and produces something runnable, so you always have a working checkpoint.

---

## 1. The pitch (what this proves on your CV)

Flaky, high-maintenance tests are the single biggest pain point in test automation. When a
developer renames a CSS class or restructures the DOM, dozens of tests break even though the
app still works. This framework attacks that directly: it keeps a normal, fast, deterministic
test suite, but when a locator breaks at runtime, an LLM inspects the new page, proposes a
corrected locator, validates it, and retries — turning a red build into a self-documenting heal.

It hits both halves of the "test automation with AI" job market: using AI to *do* testing
(generation + healing) and demonstrating that you understand test architecture, not just
prompt-calling an API.

---

## 2. Scope (read this before building anything)

**In scope (MVP):**
- A small page-object / locator-registry test structure against a real public demo site.
- LLM-powered test generation: English story in → reviewable test file out.
- LLM-powered self-healing: broken locator → validated replacement → retry → report.
- A healing report and a CI pipeline with a green badge.

**Explicitly OUT of scope** (say no to these to avoid scope creep — and mention in your README that you deliberately bounded it):
- Healing anything other than element locators (no "fix my assertions with AI").
- A web dashboard/UI. A clean terminal + markdown report is enough.
- Supporting multiple LLM providers. Pick one, abstract it behind one interface, move on.
- Visual-regression testing, mobile, cross-browser matrices.

**Target app under test:** use a stable public sandbox so you're not also maintaining an app.
Good options: `https://www.saucedemo.com`, `https://demoqa.com`, or `https://the-internet.herokuapp.com`. Pick one and commit to it.

---

## 3. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Standard in QA/AI tooling; pytest ecosystem |
| Browser automation | Playwright (Python) | Modern, reliable, great auto-waiting + DOM access |
| Test runner | pytest | Industry standard; fixtures fit this well |
| LLM | Anthropic API via `anthropic` SDK | One provider, behind an interface |
| Config | `pydantic-settings` + `.env` | Typed config, API key out of code |
| Reporting | Plain markdown + JSON | Simple, diffable, CI-friendly |
| CI | GitHub Actions | The green badge IS the proof for a testing role |

> Alternative: TypeScript + Playwright is equally valid and Playwright is TS-native. Choose Python
> if you want the project to also signal "I can do LLM/eval tooling," which is Python-heavy.

---

## 4. Architecture

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

**Key design principle — the determinism boundary:** the LLM is called *only* at two moments:
test-generation time, and the instant a locator fails. Normal passing runs make **zero** LLM
calls, so the suite stays fast, cheap, and deterministic. State this explicitly; it's the
detail that separates a thoughtful engineer from someone who sprinkles AI everywhere.

---

## 5. Module breakdown

```
src/
  config.py            # typed settings, loads ANTHROPIC_API_KEY, base URL, thresholds
  llm/
    client.py          # thin wrapper around the Anthropic SDK (one interface)
    prompts.py         # generation + healing prompt templates (versioned strings)
  registry/
    locators.yaml      # logical_name -> { selector, description, role, expected_text }
    registry.py        # load/lookup/update; "propose diff" mode (don't silently rewrite)
  framework/
    page.py            # base page object; resolve(logical_name) goes through healing
    healing.py         # the healing engine (capture DOM, call LLM, validate, retry)
    reporter.py        # collects heal events -> report.md + report.json
  generator/
    generate.py        # CLI: story (txt) -> structured test plan (JSON) -> test file
tests/
  test_*.py            # generated + hand-written pytest tests
  conftest.py          # Playwright fixtures (browser, page, healing hooks)
.github/workflows/ci.yml
```

---

## 6. Feature detail

### 6.1 Locator registry (the foundation)
Tests never hardcode selectors. They reference logical names; the registry maps each to a
selector plus metadata used for healing validation:

```yaml
login_button:
  selector: "#login-button"
  description: "The primary button that submits the login form"
  role: "button"
  expected_text: "Login"
```

`page.resolve("login_button")` tries the selector; on failure it hands the *whole record* to
the healing engine. The `description`, `role`, and `expected_text` are what let the LLM and the
validator agree on what "correct" means.

### 6.2 Self-healing engine (the headline feature)
On a locator miss:
1. Capture context: current DOM (trimmed/serialized), and the accessibility tree if available.
2. Build a healing prompt: the failed selector, its description/role/expected_text, plus the
   candidate DOM region. Ask for **one** replacement selector + a confidence score + reasoning,
   returned as strict JSON.
3. **Validate before trusting** (critical): the proposed selector must (a) resolve to exactly
   one element, (b) match the expected role, and (c) match expected text if specified. If it
   fails validation, do NOT heal — fail the test honestly.
4. If valid and confidence ≥ threshold: retry the original action and record a heal event.
5. Registry update: write the proposed change to a diff/report. Default to **propose, not
   auto-commit** — a human approves the registry change via PR.

> Interview gold: explain why step 3 exists. Without validation, an LLM can "heal" a test into a
> false pass by pointing at the wrong element. The validator is what keeps healing from
> silently destroying the suite's trustworthiness.

### 6.3 Test generation
```
python -m generator.generate --story stories/login.txt --out tests/test_login.py
```
- Input: a plain-English acceptance criterion ("A user with valid credentials lands on the
  inventory page; an invalid password shows an error.").
- The LLM returns a structured plan as JSON: ordered steps (action + target logical name) and
  assertions. Validate the JSON against a schema.
- A deterministic code generator (Python string templating, not the LLM) turns the JSON plan
  into a pytest file using the page-object + registry pattern.
- **Human-in-the-loop:** generated tests are reviewed and committed by you, never auto-run into
  the suite unseen. Say this out loud in the README.

### 6.4 Reporting
After a run, emit `report.md` and `report.json`: how many tests passed, how many healed, and for
each heal — the old selector, the proposed selector, confidence, and whether it was applied or
left pending. This artifact is what you screenshot for your README.

---

## 7. Build phases (hand to Claude Code one at a time)

1. **Skeleton + first real test.** Repo, venv, Playwright, pytest, config, one hand-written
   page object + locator registry, one passing test against the demo site. Green locally.
2. **Reporter + CI.** Wire `reporter.py`, add GitHub Actions running the suite headless on push.
   Get the green badge. *Now the project already looks credible.*
3. **Healing engine — detection + LLM call.** Catch locator failure, capture DOM, call the LLM,
   parse strict JSON. Log proposals only (no retry yet).
4. **Healing engine — validation + retry.** Add the validation gate and the retry. Force a heal
   by deliberately breaking a selector in the registry and watching it recover. Demo GIF here.
5. **Test generator.** Story → JSON plan → generated test file. Generate one test end to end.
6. **Polish.** README, architecture diagram, cost/latency notes, the "what I deliberately left
   out" section, demo GIFs.

Each phase ends runnable. Never let Claude Code build phases 3–5 before 1–2 are green.

---

## 8. Testing & CI (the suite must itself be tested — it's a testing tool)
- Unit-test the validation logic and the registry with mocked LLM responses (no live API calls
  in CI — record a couple of fixture responses).
- The generator's JSON-schema validation gets its own unit tests.
- CI runs: lint (ruff), unit tests, and the Playwright suite headless. Add the status badge to
  the README.
- Keep live-LLM behavior out of CI to stay deterministic and free; gate it behind a marker you
  run locally.

---

## 9. README checklist (this is where CV points are won)
- One-paragraph problem statement (flaky locators) and the solution.
- Architecture diagram (the ASCII one above is fine, or redraw it).
- A demo GIF of a heal happening: break a selector, run, watch it recover.
- "Design decisions" section: the determinism boundary, the validation gate, propose-not-
  auto-commit, human-in-the-loop generation.
- "Deliberately out of scope" section (shows judgment).
- Cost & latency note: roughly how many tokens a heal costs and why normal runs cost nothing.
- Run instructions that actually work from a clean clone.

---

## 10. Interview talking points to rehearse
- Why is the LLM only called on failure, not on every locator lookup?
- How do you stop the model from "healing" a test into a false pass? (validation gate)
- Why propose a registry diff instead of auto-rewriting? (trust, reviewability, git history)
- What happens on a low-confidence heal? (fail honestly, flag for human)
- How would you control cost at 10,000 tests? (heal-on-failure only, caching, batching)
- Where does this break down / what would you build next? (semantic assertion drift, visual diffs)

---

## 11. CV line
> Built a self-healing E2E test framework (Python, Playwright, Claude API) that generates tests
> from plain-English user stories and recovers from selector drift at runtime via a validated,
> human-reviewable healing engine — keeping normal runs fully deterministic.
