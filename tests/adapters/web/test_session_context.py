"""Tests for session context and validate_login_completion."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from lamia.adapters.web.session_context import (
    SessionContext,
    SessionLoginFailedError,
    SessionSkipException,
    validate_login_completion,
    pre_validate_session,
    _urls_match_ignoring_params,
    _detect_chrome_user_data_dir,
)


class TestUrlsMatchIgnoringParams:
    """Test URL comparison helper."""

    def test_identical_urls(self):
        assert _urls_match_ignoring_params("https://example.com/feed/", "https://example.com/feed/")

    def test_ignores_query_params(self):
        assert _urls_match_ignoring_params(
            "https://example.com/feed/?trk=onboarding",
            "https://example.com/feed/"
        )

    def test_ignores_trailing_slash(self):
        assert _urls_match_ignoring_params("https://example.com/feed", "https://example.com/feed/")

    def test_different_paths_do_not_match(self):
        assert not _urls_match_ignoring_params("https://example.com/login", "https://example.com/feed/")

    def test_different_hosts_do_not_match(self):
        assert not _urls_match_ignoring_params("https://other.com/feed/", "https://example.com/feed/")


class TestDetectChromeUserDataDir:
    """Test Chrome profile auto-detection."""

    @patch('lamia.adapters.web.session_context.platform')
    @patch('lamia.adapters.web.session_context.Path')
    def test_returns_none_for_unknown_os(self, _mock_path, mock_platform):
        mock_platform.system.return_value = "FreeBSD"
        assert _detect_chrome_user_data_dir() is None


class TestSessionContextChromeProfileMode:
    """Test SessionContext in Chrome-profile mode (name=None)."""

    def test_chrome_profile_mode_flag(self):
        ctx = SessionContext(name=None)
        assert ctx.chrome_profile_mode is True

    def test_lamia_session_mode_flag(self):
        ctx = SessionContext(name="login")
        assert ctx.chrome_profile_mode is False

    @patch('lamia.adapters.web.session_context._chrome_is_running', return_value=False)
    @patch('lamia.adapters.web.session_context._detect_chrome_user_data_dir', return_value="/fake/chrome/dir")
    def test_enter_chrome_profile_sets_user_data_dir(self, _mock_detect, _mock_running):
        mock_bm = Mock()
        mock_web_manager = Mock()
        mock_web_manager.browser_manager = mock_bm

        ctx = SessionContext(name=None, web_manager=mock_web_manager)
        ctx.__enter__()

        mock_bm.set_chrome_user_data_dir.assert_called_once_with("/fake/chrome/dir")

    @patch('lamia.adapters.web.session_context._chrome_is_running', return_value=False)
    def test_enter_chrome_profile_uses_explicit_user_dir(self, _mock_running):
        mock_bm = Mock()
        mock_web_manager = Mock()
        mock_web_manager.browser_manager = mock_bm

        ctx = SessionContext(name=None, web_manager=mock_web_manager, user_dir="/my/chrome")
        ctx.__enter__()

        mock_bm.set_chrome_user_data_dir.assert_called_once_with("/my/chrome")

    @patch('lamia.adapters.web.session_context._chrome_is_running', return_value=False)
    @patch('lamia.adapters.web.session_context._detect_chrome_user_data_dir', return_value=None)
    def test_enter_chrome_profile_raises_when_not_detected(self, _mock_detect, _mock_running):
        ctx = SessionContext(name=None)
        with pytest.raises(RuntimeError, match="Cannot auto-detect"):
            ctx.__enter__()

    @patch('lamia.adapters.web.session_context._chrome_is_running', return_value=False)
    def test_exit_chrome_profile_clears_user_data_dir(self, _mock_running):
        mock_bm = Mock()
        mock_web_manager = Mock()
        mock_web_manager.browser_manager = mock_bm

        ctx = SessionContext(name=None, web_manager=mock_web_manager, user_dir="/my/chrome")
        ctx.__enter__()
        ctx.__exit__(None, None, None)

        mock_bm.set_chrome_user_data_dir.assert_any_call(None)


class TestValidateLoginCompletion:
    """Test validate_login_completion polling and timeout behavior."""

    def _make_lamia(self, results):
        """Create a mock lamia instance that returns results in sequence.

        Args:
            results: list of typed_result values returned by successive lamia.run calls.
                     Each GET_PAGE_SOURCE call consumes the next value from the list.
        """
        mock = Mock()
        it = iter(results)

        def run_side_effect(command, return_type=None):
            from lamia.interpreter.commands import WebActionType
            if command.action == WebActionType.GET_PAGE_SOURCE:
                val = next(it)
                result = Mock()
                result.typed_result = val
                result.result_text = None if val is not None else "validation failed"
                return result
            return Mock()

        mock.run = Mock(side_effect=run_side_effect)
        return mock

    @patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None)
    def test_succeeds_on_first_poll(self, _mock_bm):
        """Test immediate success when page matches on first poll."""
        lamia = self._make_lamia([{"page": "ok"}])
        validate_login_completion(lamia, "https://example.com/feed", "HTML", timeout=10, poll_interval=1)
        assert lamia.run.call_count == 1

    @patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None)
    def test_succeeds_without_probe_url(self, _mock_bm):
        """Test immediate success without probe_url."""
        lamia = self._make_lamia([{"page": "ok"}])
        validate_login_completion(lamia, None, "HTML", timeout=10, poll_interval=1)
        assert lamia.run.call_count == 1

    @patch('lamia.adapters.web.session_context.time')
    @patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None)
    def test_polls_and_eventually_succeeds(self, _mock_bm, mock_time):
        """Test that polling retries and succeeds on a later attempt."""
        lamia = self._make_lamia([None, {"page": "ok"}])
        mock_time.time = Mock(side_effect=[0, 5, 15])
        mock_time.sleep = Mock()

        validate_login_completion(lamia, None, "HTML", timeout=120, poll_interval=10)

        mock_time.sleep.assert_called_once_with(10)
        assert lamia.run.call_count == 2

    @patch('lamia.adapters.web.session_context.time')
    @patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None)
    def test_warns_on_timeout_without_probe_url(self, _mock_bm, mock_time):
        """Test that a warning is logged (not raised) when timeout expires so cookies still get saved."""
        lamia = self._make_lamia([None, None])
        mock_time.time = Mock(side_effect=[0, 5, 125])
        mock_time.sleep = Mock()

        # Should NOT raise -- just warn so __exit__ still saves cookies
        validate_login_completion(lamia, None, "HTML", timeout=120, poll_interval=10)

    @patch('lamia.adapters.web.session_context.time')
    @patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None)
    def test_no_navigation_during_polling(self, _mock_bm, mock_time):
        """Test that no navigation happens during the polling loop."""
        from lamia.interpreter.commands import WebActionType

        lamia = self._make_lamia([None, {"page": "ok"}])
        mock_time.time = Mock(side_effect=[0, 5, 15])
        mock_time.sleep = Mock()

        validate_login_completion(lamia, "https://example.com/feed", "HTML", timeout=120, poll_interval=10)

        navigate_calls = [
            c for c in lamia.run.call_args_list
            if c[0][0].action == WebActionType.NAVIGATE
        ]
        assert len(navigate_calls) == 0

    @patch('lamia.adapters.web.session_context.time')
    @patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None)
    def test_sleep_clamped_to_remaining_time(self, _mock_bm, mock_time):
        """Test that sleep duration doesn't exceed remaining timeout."""
        lamia = self._make_lamia([None, None])
        mock_time.time = Mock(side_effect=[0, 115, 125])
        mock_time.sleep = Mock()

        # No longer raises -- just returns after timeout
        validate_login_completion(lamia, None, "HTML", timeout=120, poll_interval=10)

        mock_time.sleep.assert_called_once_with(5)


class TestValidateLoginFastPath:
    """Test the fast-path URL comparison in validate_login_completion."""

    def _make_lamia_with_result(self, typed_result):
        mock = Mock()
        result = Mock()
        result.typed_result = typed_result
        result.result_text = None
        mock.run = Mock(return_value=result)
        return mock

    def test_fast_path_when_url_matches(self):
        """Test that validation succeeds immediately when current URL matches probe_url (no model validation)."""
        lamia = self._make_lamia_with_result({"page": "ok"})
        browser_manager = Mock()
        browser_manager.get_current_url = AsyncMock(return_value="https://example.com/feed/?trk=nav")

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            validate_login_completion(lamia, "https://example.com/feed/", "HTML", timeout=10)

        # URL match alone is sufficient -- no lamia.run calls needed
        assert lamia.run.call_count == 0

    @patch('lamia.adapters.web.session_context.time')
    def test_no_fast_path_when_url_differs(self, mock_time):
        """Test that polling starts when current URL doesn't match probe_url."""
        browser_manager = Mock()
        browser_manager.get_current_url = AsyncMock(return_value="https://example.com/login")

        first_result = Mock(typed_result=None, result_text="no match")
        second_result = Mock(typed_result={"ok": True}, result_text=None)
        lamia = Mock()
        lamia.run = Mock(side_effect=[first_result, second_result])

        mock_time.time = Mock(side_effect=[0, 5, 15])
        mock_time.sleep = Mock()

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            validate_login_completion(lamia, "https://example.com/feed/", "HTML", timeout=120, poll_interval=10)

        # Fast path GET_PAGE_SOURCE was skipped (URL mismatch), polling ran
        mock_time.sleep.assert_called_once()


class TestValidateLoginProbeNavigation:
    """Test the last-resort probe navigation in validate_login_completion."""

    @patch('lamia.adapters.web.session_context.time')
    def test_probe_uses_tab_browser_manager_and_restores_original(self, mock_time):
        """Test Phase 3 swaps BrowserManager, validates, then restores+closes."""
        from lamia.interpreter.commands import WebActionType

        fail_result = Mock(typed_result=None, result_text="no match")
        success_result = Mock(typed_result={"ok": True}, result_text=None)
        results = [fail_result, Mock(), success_result]
        lamia = Mock()
        lamia.run = Mock(side_effect=results)

        original_browser_manager = Mock()
        tab_browser_manager = Mock()
        tab_browser_manager.close = AsyncMock()
        browser_manager = Mock()
        browser_manager.open_new_tab = AsyncMock(return_value=tab_browser_manager)
        web_manager = Mock()
        web_manager.browser_manager = original_browser_manager
        web_manager.recent_actions = []

        mock_time.time = Mock(side_effect=[0, 125])
        mock_time.sleep = Mock()

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            with patch('lamia.adapters.web.session_context._get_web_manager', return_value=web_manager):
                validate_login_completion(lamia, "https://example.com/feed/", "HTML", timeout=120, poll_interval=10)

        browser_manager.open_new_tab.assert_awaited_once()
        tab_browser_manager.close.assert_awaited_once()
        assert web_manager.browser_manager == original_browser_manager

        navigate_calls = [
            c for c in lamia.run.call_args_list
            if c[0][0].action == WebActionType.NAVIGATE
        ]
        assert len(navigate_calls) == 1
        assert navigate_calls[0][0][0].url == "https://example.com/feed/"
        get_page_source_calls = [
            c for c in lamia.run.call_args_list
            if c[0][0].action == WebActionType.GET_PAGE_SOURCE
        ]
        assert len(get_page_source_calls) == 2
        assert get_page_source_calls[-1][1]["return_type"] == "HTML"

    @patch('lamia.adapters.web.session_context.time')
    def test_probe_failure_restores_manager_and_returns(self, mock_time):
        """Test Phase 3 failure still restores original manager, closes tab, and returns (no raise)."""
        from lamia.interpreter.commands import WebActionType

        fail_result = Mock(typed_result=None, result_text="no match")
        lamia = Mock()
        lamia.run = Mock(side_effect=[fail_result, Mock(), fail_result])

        original_browser_manager = Mock()
        tab_browser_manager = Mock()
        tab_browser_manager.close = AsyncMock()
        browser_manager = Mock()
        browser_manager.open_new_tab = AsyncMock(return_value=tab_browser_manager)
        web_manager = Mock()
        web_manager.browser_manager = original_browser_manager
        web_manager.recent_actions = []

        mock_time.time = Mock(side_effect=[0, 125])
        mock_time.sleep = Mock()

        # Should NOT raise -- returns so __exit__ can save cookies
        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            with patch('lamia.adapters.web.session_context._get_web_manager', return_value=web_manager):
                validate_login_completion(lamia, "https://example.com/feed/", "HTML", timeout=120, poll_interval=10)

        tab_browser_manager.close.assert_awaited_once()
        assert web_manager.browser_manager == original_browser_manager
        navigate_calls = [
            c for c in lamia.run.call_args_list
            if c[0][0].action == WebActionType.NAVIGATE
        ]
        assert len(navigate_calls) == 1


class TestPreValidateSession:
    """Test pre_validate_session URL and model checks."""

    def test_skips_when_url_matches_probe_url(self):
        """Test that SessionSkipException is raised when current URL matches probe_url."""
        lamia = Mock()
        browser_manager = Mock()
        browser_manager.get_current_url = AsyncMock(return_value="https://example.com/feed/?trk=onboarding")

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            with pytest.raises(SessionSkipException, match="Already on target URL"):
                pre_validate_session(lamia, "https://example.com/feed/", "HTML")

    def test_skips_when_model_validates(self):
        """Test that SessionSkipException is raised when model validation succeeds."""
        result = Mock(typed_result={"page": "ok"})
        lamia = Mock()
        lamia.run = Mock(return_value=result)

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None):
            with pytest.raises(SessionSkipException, match="already in desired state"):
                pre_validate_session(lamia, None, "HTML")

    def test_continues_when_url_differs_and_model_fails(self):
        """Test that function returns normally when neither check passes."""
        result = Mock(typed_result=None, result_text="no match")
        lamia = Mock()
        lamia.run = Mock(return_value=result)
        browser_manager = Mock()
        browser_manager.get_current_url = AsyncMock(return_value="https://example.com/login")

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            # Should NOT raise
            pre_validate_session(lamia, "https://example.com/feed/", "HTML")

    def test_continues_when_no_probe_url_and_model_fails(self):
        """Test that function returns normally when no probe_url and model fails."""
        result = Mock(typed_result=None, result_text="no match")
        lamia = Mock()
        lamia.run = Mock(return_value=result)

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=None):
            # Should NOT raise
            pre_validate_session(lamia, None, "HTML")

    def test_url_check_takes_priority_over_model(self):
        """Test that URL match skips without even running model validation."""
        lamia = Mock()
        browser_manager = Mock()
        browser_manager.get_current_url = AsyncMock(return_value="https://example.com/feed/")

        with patch('lamia.adapters.web.session_context._get_browser_manager', return_value=browser_manager):
            with pytest.raises(SessionSkipException):
                pre_validate_session(lamia, "https://example.com/feed/", "HTML")

        # lamia.run should NOT have been called -- URL match is enough
        lamia.run.assert_not_called()