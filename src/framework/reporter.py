import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class HealEvent:
    test_name: str
    logical_name: str
    old_selector: str
    proposed_selector: str
    confidence: float
    reasoning: str
    applied: bool


class Reporter:
    def __init__(self) -> None:
        self._started_at = datetime.now()
        self._heal_events: list[HealEvent] = []

    def record_heal(self, event: HealEvent) -> None:
        self._heal_events.append(event)

    def write(self, passed: int, failed: int, out_dir: Path = Path(".")) -> None:
        finished_at = datetime.now()
        healed = sum(1 for e in self._heal_events if e.applied)

        data = {
            "started_at": self._started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "total": passed + failed,
            "passed": passed,
            "failed": failed,
            "healed": healed,
            "heal_events": [
                {
                    "test_name": e.test_name,
                    "logical_name": e.logical_name,
                    "old_selector": e.old_selector,
                    "proposed_selector": e.proposed_selector,
                    "confidence": e.confidence,
                    "reasoning": e.reasoning,
                    "applied": e.applied,
                }
                for e in self._heal_events
            ],
        }

        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        (out_dir / "report.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        (out_dir / "report.md").write_text(self._render_md(data), encoding="utf-8")

    def _render_md(self, data: dict) -> str:
        lines = [
            "# Self-Healing Test Report",
            "",
            f"**Run:** {data['started_at']} → {data['finished_at']}",
            (
                f"**Total:** {data['total']} | **Passed:** {data['passed']} | "
                f"**Failed:** {data['failed']} | **Healed:** {data['healed']}"
            ),
            "",
        ]

        if data["heal_events"]:
            lines += ["## Heal Events", ""]
            for e in data["heal_events"]:
                status = "Applied" if e["applied"] else "Pending (not applied)"
                lines += [
                    f"### `{e['logical_name']}` — {status}",
                    f"- **Test:** `{e['test_name']}`",
                    f"- **Old selector:** `{e['old_selector']}`",
                    f"- **Proposed selector:** `{e['proposed_selector']}`",
                    f"- **Confidence:** {e['confidence']:.0%}",
                    f"- **Reasoning:** {e['reasoning']}",
                    "",
                ]
        else:
            lines += ["*No heal events — all locators resolved normally.*", ""]

        return "\n".join(lines)
