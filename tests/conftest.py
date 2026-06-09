import pytest

from src.config import settings
from src.framework.reporter import Reporter
from src.registry.registry import LocatorRegistry


def pytest_configure(config) -> None:
    config._reporter = Reporter()


def pytest_sessionfinish(session, exitstatus) -> None:
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    passed = len(tr.stats.get("passed", [])) if tr else 0
    failed = len(tr.stats.get("failed", [])) if tr else 0
    session.config._reporter.write(passed=passed, failed=failed)


@pytest.fixture(scope="session")
def registry() -> LocatorRegistry:
    return LocatorRegistry()


@pytest.fixture(scope="session")
def reporter(pytestconfig) -> Reporter:
    return pytestconfig._reporter


@pytest.fixture(scope="session")
def healing_engine(reporter):
    if not settings.anthropic_api_key:
        return None
    from src.framework.healing import HealingEngine
    from src.llm.client import LLMClient

    return HealingEngine(LLMClient(), reporter)


@pytest.fixture
def base_page(page, registry, healing_engine, request):
    from src.framework.page import BasePage

    return BasePage(page, registry, healing_engine, test_name=request.node.name)
