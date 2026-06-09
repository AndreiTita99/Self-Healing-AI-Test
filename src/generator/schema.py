from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


class Step(BaseModel):
    action: Literal["navigate", "fill", "click", "assert_visible", "assert_text"]
    target: str | None = None
    value: str | None = None


class TestCase(BaseModel):
    test_name: str
    description: str
    steps: list[Step]

    @field_validator("test_name")
    @classmethod
    def must_start_with_test(cls, v: str) -> str:
        if not v.startswith("test_"):
            raise ValueError(f"test_name must start with 'test_', got '{v}'")
        return v


class TestPlan(BaseModel):
    source_story: str
    tests: list[TestCase]
