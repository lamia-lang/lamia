"""Tests for BrowserOverlay."""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

from lamia.engine.managers.web.selector_resolution.visual_picker.overlay import BrowserOverlay


@pytest.fixture
def mock_browser_adapter():
    """Create mock browser adapter."""
    adapter = AsyncMock()
    adapter.execute_script = AsyncMock()
    return adapter


class TestBrowserOverlayInitialization:
    """Test BrowserOverlay initialization."""

    def test_overlay_initialization(self, mock_browser_adapter):
        """Test browser overlay initialization."""
        overlay = BrowserOverlay(mock_browser_adapter)

        assert overlay.browser == mock_browser_adapter
        assert overlay._picker_js is None
        assert overlay._selection_result is None
        assert overlay._selection_event is None


class TestBrowserOverlayExpandScope:
    """Test BrowserOverlay expand_scope method."""

    @pytest.mark.asyncio
    async def test_expand_scope_success(self, mock_browser_adapter):
        """Test expanding selection scope."""
        mock_browser_adapter.execute_script.return_value = {
            "tagName": "DIV",
            "xpath": "//div[@class='parent']"
        }

        overlay = BrowserOverlay(mock_browser_adapter)
        current_element = {"xpath": "//button[@id='child']"}

        result = await overlay.expand_scope(current_element, levels=1)

        assert result["tagName"] == "DIV"
        assert result["xpath"] == "//div[@class='parent']"
        mock_browser_adapter.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_scope_no_xpath(self, mock_browser_adapter):
        """Test expanding scope without xpath raises error."""
        overlay = BrowserOverlay(mock_browser_adapter)
        current_element = {}

        with pytest.raises(ValueError, match="Cannot expand scope"):
            await overlay.expand_scope(current_element, levels=1)

    @pytest.mark.asyncio
    async def test_expand_scope_empty_xpath(self, mock_browser_adapter):
        """Test expanding scope with empty xpath raises error."""
        overlay = BrowserOverlay(mock_browser_adapter)
        current_element = {"xpath": ""}

        with pytest.raises(ValueError, match="Cannot expand scope"):
            await overlay.expand_scope(current_element, levels=1)

    @pytest.mark.asyncio
    async def test_expand_scope_no_result(self, mock_browser_adapter):
        """Test expanding scope when no parent found raises error."""
        mock_browser_adapter.execute_script.return_value = None

        overlay = BrowserOverlay(mock_browser_adapter)
        current_element = {"xpath": "//button[@id='child']"}

        with pytest.raises(ValueError, match="Could not expand scope"):
            await overlay.expand_scope(current_element, levels=1)

    @pytest.mark.asyncio
    async def test_expand_scope_exception(self, mock_browser_adapter):
        """Test expanding scope when exception occurs."""
        mock_browser_adapter.execute_script.side_effect = Exception("Script error")

        overlay = BrowserOverlay(mock_browser_adapter)
        current_element = {"xpath": "//button[@id='child']"}

        with pytest.raises(ValueError, match="Scope expansion failed"):
            await overlay.expand_scope(current_element, levels=1)


class TestBrowserOverlayShowUserMessage:
    """Test BrowserOverlay show_user_message method."""

    @pytest.mark.asyncio
    async def test_show_user_message(self, mock_browser_adapter):
        """Test showing user message."""
        overlay = BrowserOverlay(mock_browser_adapter)

        await overlay.show_user_message(
            title="Test Title",
            message="Test message content",
            timeout=5
        )

        mock_browser_adapter.execute_script.assert_called_once()
        call_args = mock_browser_adapter.execute_script.call_args[0][0]
        assert "Test Title" in call_args
        assert "Test message content" in call_args

    @pytest.mark.asyncio
    async def test_show_user_message_default_timeout(self, mock_browser_adapter):
        """Test showing user message with default timeout."""
        overlay = BrowserOverlay(mock_browser_adapter)

        await overlay.show_user_message(
            title="Title",
            message="Message"
        )

        mock_browser_adapter.execute_script.assert_called_once()
        call_args = mock_browser_adapter.execute_script.call_args[0][0]
        assert "5000" in call_args

    @pytest.mark.asyncio
    async def test_show_user_message_handles_exception(self, mock_browser_adapter):
        """Test that exceptions when showing message are handled."""
        mock_browser_adapter.execute_script.side_effect = Exception("Script error")

        overlay = BrowserOverlay(mock_browser_adapter)

        await overlay.show_user_message(
            title="Title",
            message="Message"
        )

        mock_browser_adapter.execute_script.assert_called_once()


class TestBrowserOverlayPickSingleElement:
    """Test BrowserOverlay pick_single_element method error handling."""

    @pytest.mark.asyncio
    async def test_pick_single_element_injects_js(self, mock_browser_adapter):
        """Test that pick_single_element attempts to inject JavaScript."""
        overlay = BrowserOverlay(mock_browser_adapter)

        with patch.object(overlay, '_inject_picker_js', new_callable=AsyncMock) as mock_inject:
            with patch.object(overlay, '_start_picker', new_callable=AsyncMock) as mock_start:
                with patch('asyncio.Event') as mock_event:
                    mock_event_instance = Mock()
                    mock_event_instance.wait = AsyncMock()
                    mock_event_instance.is_set = Mock(return_value=False)
                    mock_event.return_value = mock_event_instance

                    overlay._selection_event = mock_event_instance
                    overlay._selection_result = None

                    with pytest.raises(ValueError, match="No element was selected"):
                        await overlay.pick_single_element("test instruction")

                    mock_inject.assert_called_once()
                    mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_single_element_cleans_up(self, mock_browser_adapter):
        """Test that pick_single_element cleans up after itself."""
        overlay = BrowserOverlay(mock_browser_adapter)

        with patch.object(overlay, '_inject_picker_js', new_callable=AsyncMock):
            with patch.object(overlay, '_start_picker', new_callable=AsyncMock):
                with patch.object(overlay, '_cleanup_picker', new_callable=AsyncMock) as mock_cleanup:
                    with patch('asyncio.Event') as mock_event:
                        mock_event_instance = Mock()
                        mock_event_instance.wait = AsyncMock()
                        mock_event_instance.is_set = Mock(return_value=False)
                        mock_event.return_value = mock_event_instance

                        overlay._selection_event = mock_event_instance
                        overlay._selection_result = None

                        try:
                            await overlay.pick_single_element("test instruction")
                        except ValueError:
                            pass

                        mock_cleanup.assert_called_once()


class TestBrowserOverlayPickContainerForMultiple:
    """Test BrowserOverlay pick_container_for_multiple method error handling."""

    @pytest.mark.asyncio
    async def test_pick_container_for_multiple_injects_js(self, mock_browser_adapter):
        """Test that pick_container_for_multiple attempts to inject JavaScript."""
        overlay = BrowserOverlay(mock_browser_adapter)

        with patch.object(overlay, '_inject_picker_js', new_callable=AsyncMock) as mock_inject:
            with patch.object(overlay, '_start_picker', new_callable=AsyncMock) as mock_start:
                with patch('asyncio.Event') as mock_event:
                    mock_event_instance = Mock()
                    mock_event_instance.wait = AsyncMock()
                    mock_event_instance.is_set = Mock(return_value=False)
                    mock_event.return_value = mock_event_instance

                    overlay._selection_event = mock_event_instance
                    overlay._selection_result = None

                    with pytest.raises(ValueError, match="No container was selected"):
                        await overlay.pick_container_for_multiple("test instruction")

                    mock_inject.assert_called_once()
                    mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_pick_container_for_multiple_cleans_up(self, mock_browser_adapter):
        """Test that pick_container_for_multiple cleans up after itself."""
        overlay = BrowserOverlay(mock_browser_adapter)

        with patch.object(overlay, '_inject_picker_js', new_callable=AsyncMock):
            with patch.object(overlay, '_start_picker', new_callable=AsyncMock):
                with patch.object(overlay, '_cleanup_picker', new_callable=AsyncMock) as mock_cleanup:
                    with patch('asyncio.Event') as mock_event:
                        mock_event_instance = Mock()
                        mock_event_instance.wait = AsyncMock()
                        mock_event_instance.is_set = Mock(return_value=False)
                        mock_event.return_value = mock_event_instance

                        overlay._selection_event = mock_event_instance
                        overlay._selection_result = None

                        try:
                            await overlay.pick_container_for_multiple("test instruction")
                        except ValueError:
                            pass

                        mock_cleanup.assert_called_once()
