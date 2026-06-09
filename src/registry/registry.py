from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LocatorRecord:
    name: str
    selector: str
    description: str
    role: str
    expected_text: str


class LocatorRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(__file__).parent / "locators.yaml"
        self._records: dict[str, LocatorRecord] = {}
        self._load()

    def _load(self) -> None:
        with open(self._path) as f:
            data: dict = yaml.safe_load(f)
        self._records = {
            name: LocatorRecord(name=name, **entry) for name, entry in data.items()
        }

    def get(self, name: str) -> LocatorRecord:
        if name not in self._records:
            raise KeyError(f"Locator '{name}' not found in registry")
        return self._records[name]

    def all(self) -> dict[str, LocatorRecord]:
        return dict(self._records)
