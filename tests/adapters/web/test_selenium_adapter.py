import pytest
from unittest.mock import Mock, MagicMock, patch

from lamia.adapters.web.browser import selenium_adapter as selenium_module
from lamia.adapters.web.browser.selenium_adapter import SeleniumAdapter
from lamia.errors import (
    ExternalOperationPermanentError, 
    ExternalOperationTransientError,
    MultipleSelectableInputsError,
    NoSelectableInputError
)
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
    
    # Clear cache to ensure clean test
    adapter.selector_cache.clear_all()

    attempted: List[str] = []

    def fake_wait(self, by, value, timeout, scope_element=None):
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

@pytest.mark.asyncio
async def test_get_options_radio_buttons():
    """Test get_options() extracts radio button labels."""
    from selenium.webdriver.common.by import By
    from unittest.mock import PropertyMock
    
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    # Mock labels with proper text property
    mock_label1 = Mock()
    type(mock_label1).text = PropertyMock(return_value="Entry Level  ")
    
    mock_label2 = Mock()
    type(mock_label2).text = PropertyMock(return_value="  Senior")
    
    # Mock radio elements
    mock_radio1 = Mock()
    mock_radio1.get_attribute.side_effect = lambda attr: "r1" if attr == "id" else ("experience" if attr == "name" else None)
    
    mock_radio2 = Mock()
    mock_radio2.get_attribute.side_effect = lambda attr: "r2" if attr == "id" else ("experience" if attr == "name" else None)
    
    # Mock driver
    mock_driver = Mock()
    
    def find_elements_mock(by, selector):
        if selector == ".//input[@type='radio']":
            return [mock_radio1, mock_radio2]
        elif selector == ".//input[@type='checkbox']":
            return []
        elif selector == "select" and by == By.TAG_NAME:
            return []
        return []
    
    def find_element_mock(by, selector):
        # Called by search_root.find_element(By.XPATH, f".//label[@for='{input_id}']")
        if selector == ".//label[@for='r1']":
            return mock_label1
        elif selector == ".//label[@for='r2']":
            return mock_label2
        raise NoSuchElementException("Label not found")
    
    mock_driver.find_elements.side_effect = find_elements_mock
    mock_driver.find_element.side_effect = find_element_mock
    adapter.driver = mock_driver
    
    params = BrowserActionParams(selector=None)
    options = await adapter.get_options(params)
    
    assert len(options) == 2
    assert "Entry Level" in options
    assert "Senior" in options


@pytest.mark.asyncio
async def test_get_options_multiple_radio_groups_error():
    """Test that multiple radio groups (different names) throws error."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    # Mock radio elements with DIFFERENT names
    mock_radio1 = Mock()
    mock_radio1.get_attribute.return_value = "experience"
    
    mock_radio2 = Mock()
    mock_radio2.get_attribute.return_value = "availability"  # Different name!
    
    mock_driver = Mock()
    mock_driver.find_elements.side_effect = lambda by, sel: {
        ".//input[@type='radio']": [mock_radio1, mock_radio2],
        ".//input[@type='checkbox']": [],
    }.get(sel, [])
    adapter.driver = mock_driver
    
    params = BrowserActionParams(selector=None)
    
    with pytest.raises(MultipleSelectableInputsError) as exc_info:
        await adapter.get_options(params)
    
    assert "different names" in str(exc_info.value).lower()
    assert "experience" in str(exc_info.value) or "availability" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_options_multiple_selects_error():
    """Test that multiple <select> elements throws error."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    mock_select1 = Mock()
    mock_select2 = Mock()
    
    mock_driver = Mock()
    mock_driver.find_elements.side_effect = lambda by, tag: {
        "select": [mock_select1, mock_select2],
        ".//input[@type='radio']": [],
        ".//input[@type='checkbox']": [],
    }.get(tag if by.lower() == "tag name" else "unknown", [])
    adapter.driver = mock_driver
    
    params = BrowserActionParams(selector=None)
    
    with pytest.raises(MultipleSelectableInputsError) as exc_info:
        await adapter.get_options(params)
    
    assert "2 dropdown" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_options_mixed_types_error():
    """Test that radio + checkbox throws error."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    mock_radio = Mock()
    mock_radio.get_attribute.return_value = "exp"
    
    mock_checkbox = Mock()
    mock_checkbox.get_attribute.return_value = "skills"
    
    mock_driver = Mock()
    mock_driver.find_elements.side_effect = lambda by, sel: {
        ".//input[@type='radio']": [mock_radio],
        ".//input[@type='checkbox']": [mock_checkbox],
    }.get(sel, [])
    adapter.driver = mock_driver
    
    params = BrowserActionParams(selector=None)
    
    with pytest.raises(MultipleSelectableInputsError) as exc_info:
        await adapter.get_options(params)
    
    assert "multiple input types" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_options_no_inputs_error():
    """Test that no selectable inputs throws error."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    mock_driver = Mock()
    mock_driver.find_elements.return_value = []
    adapter.driver = mock_driver
    
    params = BrowserActionParams(selector=None)
    
    with pytest.raises(NoSelectableInputError):
        await adapter.get_options(params)


@pytest.mark.asyncio
async def test_upload_file():
    """Test file upload calls send_keys with file path."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    mock_element = Mock()
    mock_driver = Mock()
    adapter.driver = mock_driver
    adapter._find_element = Mock(return_value=(mock_element, "input[type='file']"))
    
    params = BrowserActionParams(
        selector="input[type='file']",
        value="/path/to/resume.pdf"
    )
    
    await adapter.upload_file(params)
    
    # Verify send_keys was called with file path
    mock_element.send_keys.assert_called_once_with("/path/to/resume.pdf")


@pytest.mark.asyncio  
async def test_get_elements():
    """Test get_elements() returns list of elements."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    mock_elem1 = Mock()
    mock_elem1.tag_name = "input"
    mock_elem2 = Mock()
    mock_elem2.tag_name = "input"
    
    mock_driver = Mock()
    mock_driver.find_elements.return_value = [mock_elem1, mock_elem2]
    adapter.driver = mock_driver
    adapter._wait_for_presence = Mock(side_effect=lambda by, val, timeout, scope=None: mock_elem1)
    
    params = BrowserActionParams(selector="input[type='radio']")
    
    elements = await adapter.get_elements(params)
    
    assert len(elements) == 2
    assert elements[0] == mock_elem1
    assert elements[1] == mock_elem2


@pytest.mark.asyncio
async def test_get_input_type_returns_enum_value():
    """Test get_input_type() returns InputType enum value."""
    adapter = SeleniumAdapter()
    adapter.initialized = True
    
    mock_element = Mock()
    mock_element.tag_name = "input"
    mock_element.get_attribute.return_value = "checkbox"
    
    adapter._find_element = Mock(return_value=(mock_element, "input"))
    
    params = BrowserActionParams(selector="input")
    result = await adapter.get_input_type(params)
    
    assert result == "checkbox"  # Should return the enum value as string
