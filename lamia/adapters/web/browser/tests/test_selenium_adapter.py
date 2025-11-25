import pytest

from lamia.adapters.web.browser import selenium_adapter as selenium_module
from lamia.adapters.web.browser.selenium_adapter import SeleniumAdapter
from lamia.errors import ExternalOperationPermanentError, ExternalOperationTransientError
from lamia.internal_types import BrowserActionParams, SelectorType
from typing import Any, TYPE_CHECKING, cast, List

if TYPE_CHECKING:
    from selenium.webdriver.chrome.webdriver import WebDriver as ChromeWebDriver
else:
    ChromeWebDriver = Any


class ScriptableDriver:
    """Minimal execute_script stub to emulate DOM stability reports."""

    def __init__(self, responses):
        self._responses = list(responses)
        self._last_response = responses[-1] if responses else {}

    def execute_script(self, script):
        if script == selenium_module.DOM_STABILITY_CHECK_SCRIPT:
            if self._responses:
                self._last_response = self._responses.pop(0)
            return self._last_response
        return None


def _stable_payload(time_since=selenium_module.DOM_STABLE_MUTATION_QUIET_MS):
    return {
        "readyStateComplete": True,
        "pendingFetches": 0,
        "pendingXhrs": 0,
        "timeSinceMutation": time_since,
    }


def test_dom_stability_treats_missing_time_since_as_infinite():
    adapter = SeleniumAdapter()
    adapter.driver = cast(ChromeWebDriver, ScriptableDriver([
        {
            "readyStateComplete": True,
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": None,
        }
    ]))

    assert adapter._is_dom_stable_sync() is True


def test_raise_dom_error_permanent_on_stable_dom():
    adapter = SeleniumAdapter()
    adapter.driver = cast(ChromeWebDriver, ScriptableDriver([_stable_payload()]))

    with pytest.raises(ExternalOperationPermanentError):
        adapter._raise_dom_classified_error("element missing", RuntimeError("boom"))


def test_raise_dom_error_transient_on_unstable_dom():
    adapter = SeleniumAdapter()
    adapter.driver = cast(ChromeWebDriver, ScriptableDriver([
        {
            "readyStateComplete": False,
            "pendingFetches": 1,
            "pendingXhrs": 0,
            "timeSinceMutation": 0,
        }
    ]))

    with pytest.raises(ExternalOperationTransientError):
        adapter._raise_dom_classified_error("element missing", RuntimeError("boom"))


def test_interactive_ready_state_counts_as_stable_when_quiet():
    """readyState and mutation time are ignored; only pending resources matter."""
    adapter = SeleniumAdapter()
    adapter.driver = cast(ChromeWebDriver, ScriptableDriver([
        {
            "readyStateComplete": False,
            "readyState": "loading",
            "pendingFetches": 0,
            "pendingXhrs": 0,
            "timeSinceMutation": 0.0,
        }
    ]))

    assert adapter._is_dom_stable_sync() is True


def test_ready_dom_with_stuck_pending_fetches_should_be_transient():
    adapter = SeleniumAdapter()
    adapter.driver = cast(ChromeWebDriver, ScriptableDriver([
        {
            "readyStateComplete": True,
            "pendingFetches": 1,
            "pendingXhrs": 0,
            "timeSinceMutation": selenium_module.DOM_STABLE_MUTATION_QUIET_MS * 2,
        }
    ]))

    with pytest.raises(ExternalOperationTransientError):
        adapter._raise_dom_classified_error("element missing", RuntimeError("boom"))


def test_find_element_falls_back_to_secondary_selector(monkeypatch):
    adapter = SeleniumAdapter()
    adapter.initialized = True
    adapter.driver = cast(ChromeWebDriver, object())

    attempted: List[str] = []

    def fake_wait(self, by, value, timeout):
        selector = value
        attempted.append(selector)
        if selector == "primary":
            raise selenium_module.TimeoutException("primary missing")
        return f"ELEMENT:{selector}"

    monkeypatch.setattr(SeleniumAdapter, "_wait_for_presence", fake_wait, raising=False)

    params = BrowserActionParams(
        selector="primary",
        fallback_selectors=["fallback"],
    )

    try:
        element, active_selector = adapter._find_element(params)
    except Exception as exc:  # pragma: no cover - added for easier debugging
        pytest.fail(f"Fallback selector resolution raised {exc!r}; attempted={attempted}")

    assert element == "ELEMENT:fallback"
    assert active_selector == "fallback"
    assert attempted == ["primary", "fallback"]


@pytest.mark.asyncio
async def test_click_missing_selector_yields_permanent_error(monkeypatch):
    adapter = SeleniumAdapter()
    adapter.initialized = True
    adapter.driver = cast(ChromeWebDriver, object())
    adapter._is_dom_stable_sync = lambda: True  # Force stable classification

    class FailingWait:
        def __init__(self, driver, timeout):
            pass

        def until(self, condition):
            raise selenium_module.TimeoutException("not found")

    monkeypatch.setattr(selenium_module, "WebDriverWait", FailingWait)

    params = BrowserActionParams(
        selector="button.submit",
        selector_type=SelectorType.CSS,
    )

    with pytest.raises(ExternalOperationPermanentError):
        await adapter.click(params)

