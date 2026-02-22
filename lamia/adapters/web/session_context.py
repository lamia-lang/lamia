"""Clean session context manager for browser profile management."""

import logging
import os
import platform
import time
from pathlib import Path
from typing import Optional, Any

from lamia.async_bridge import EventLoopManager
from urllib.parse import urlparse

from lamia.interpreter.commands import WebCommand, WebActionType
from lamia.interpreter.command_types import CommandType
from lamia.engine.managers.web.browser_manager import BrowserManager

logger = logging.getLogger(__name__)


class SessionSkipException(Exception):
    """Exception raised when session should be skipped due to valid existing state."""
    pass


class SessionLoginFailedError(Exception):
    """Exception raised when login validation fails after the session body completes."""
    pass


def _detect_chrome_user_data_dir() -> Optional[str]:
    """Auto-detect the default Chrome user-data-dir for the current OS.

    Returns the path if it exists on disk, otherwise None.
    """
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        candidate = home / "Library" / "Application Support" / "Google" / "Chrome"
    elif system == "Linux":
        candidate = home / ".config" / "google-chrome"
    elif system == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            candidate = Path(local_app) / "Google" / "Chrome" / "User Data"
        else:
            candidate = home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    else:
        return None

    if candidate.is_dir():
        return str(candidate)
    return None


def _chrome_is_running() -> bool:
    """Best-effort check whether Chrome is currently running."""
    system = platform.system()
    if system == "Darwin":
        # SingletonLock is held while Chrome runs on macOS / Linux
        chrome_dir = _detect_chrome_user_data_dir()
        if chrome_dir:
            return Path(chrome_dir, "SingletonLock").exists()
    elif system == "Linux":
        chrome_dir = _detect_chrome_user_data_dir()
        if chrome_dir:
            return Path(chrome_dir, "SingletonLock").exists()
    # On Windows the lock mechanism is different; skip for now
    return False


class SessionContext:
    """Simple session context manager with profile name only.
    Works with the "with session() -> Type: ... " statement to handle session management.
    """

    def __init__(self, name: Optional[str], web_manager: Optional[Any] = None,
                 probe_url: Optional[str] = None,
                 user_dir: Optional[str] = None):
        """Initialize session context.

        Args:
            name: Browser profile name (e.g. "linkedin_login").
                  None means "use Chrome user-data-dir instead of lamia sessions".
            web_manager: WebManager instance for validation
            probe_url: Optional URL (kept for compatibility)
            user_dir: Explicit Chrome user-data-dir path.  When *name* is None
                      and *user_dir* is also None we auto-detect the system path.
        """
        self.name: Optional[str] = name
        self.web_manager = web_manager
        self.probe_url: Optional[str] = probe_url
        self.should_skip: bool = False
        self.chrome_profile_mode: bool = name is None
        self.user_dir: Optional[str] = user_dir

    def __enter__(self):
        """Enter session context - load cookies and session state for the profile."""
        if self.chrome_profile_mode:
            return self._enter_chrome_profile_mode()
        return self._enter_lamia_session_mode()

    def _enter_chrome_profile_mode(self):
        """Launch Chrome bound to the real user profile directory."""
        resolved_dir = self.user_dir or _detect_chrome_user_data_dir()
        if not resolved_dir:
            raise RuntimeError(
                "Cannot auto-detect Chrome user-data-dir for this OS. "
                "Pass the path explicitly: session(user_dir='/path/to/chrome/profile')"
            )

        if _chrome_is_running():
            logger.warning(
                "Chrome appears to be running. Please close all Chrome windows "
                "before using session() in Chrome-profile mode -- two Chrome "
                "instances cannot share the same user-data-dir."
            )

        logger.info(f"Chrome-profile mode: using user-data-dir {resolved_dir}")

        if self.web_manager:
            browser_manager: BrowserManager = self.web_manager.browser_manager
            browser_manager.set_chrome_user_data_dir(resolved_dir)

        return self

    def _enter_lamia_session_mode(self):
        """Standard lamia session: load cookies/storage via SessionManager."""
        name: str = self.name  # type: ignore[assignment]  # guaranteed non-None in this path
        logger.info(f"Starting session context for profile '{name}'")

        if self.web_manager:
            try:
                browser_manager: BrowserManager = self.web_manager.browser_manager
                try:
                    browser_manager.set_active_profile(name)
                except Exception:
                    pass

                try:
                    EventLoopManager.run_coroutine(browser_manager.load_session_cookies(name))
                except Exception as e:
                    logger.debug(f"Session state loading failed for '{name}': {e}")

            except Exception as e:
                logger.debug(f"Cookie validation failed for '{name}': {e}")

        logger.info(f"Starting session execution for profile '{name}'")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit session context - save session if successful."""
        if self.chrome_profile_mode:
            # Chrome profile mode: cookies live inside the profile dir, nothing
            # to persist on our side.  Just clear the flag on the manager.
            if self.web_manager:
                try:
                    self.web_manager.browser_manager.set_chrome_user_data_dir(None)
                except Exception:
                    pass
            return False

        name: str = self.name  # type: ignore[assignment]  # guaranteed non-None here
        if self.should_skip:
            logger.debug(f"Session '{name}' was skipped, no cleanup needed")
        elif exc_type is None and self.web_manager:
            logger.info(f"Session '{name}' completed successfully, saving cookies")
            try:
                browser_manager: BrowserManager = self.web_manager.browser_manager
                try:
                    EventLoopManager.run_coroutine(browser_manager.save_session_cookies(name))
                except Exception as e:
                    logger.warning(f"Failed to save cookies for profile '{name}': {e}")
                try:
                    browser_manager.set_active_profile(None)
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Failed to save cookies for profile '{name}': {e}")
        else:
            logger.warning(f"Session '{name}' failed: {exc_val}")

        return False


def create_session_factory(web_manager: Optional[Any] = None):
    """Create session factory with web_manager injection.

    Args:
        web_manager: WebManager instance for session validation

    Returns:
        Session factory function
    """
    def session(name: Optional[str] = None, probe_url: Optional[str] = None,
                user_dir: Optional[str] = None) -> SessionContext:
        """Create session context.

        Args:
            name: Browser profile name.  When omitted (or None) the session
                  will use the real Chrome user-data-dir instead of lamia's
                  cookie management.
            probe_url: Optional URL to probe for logged-in state
            user_dir: Explicit Chrome user-data-dir path (only for
                      Chrome-profile mode when *name* is None).

        Returns:
            SessionContext manager
        """
        return SessionContext(name=name, web_manager=web_manager,
                             probe_url=probe_url, user_dir=user_dir)

    return session


def _urls_match_ignoring_params(url1: str, url2: str) -> bool:
    """Compare two URLs ignoring query parameters and trailing slashes."""
    p1 = urlparse(url1)
    p2 = urlparse(url2)
    return (p1.scheme == p2.scheme
            and p1.netloc == p2.netloc
            and p1.path.rstrip('/') == p2.path.rstrip('/'))


def _get_browser_manager(lamia_instance: Any) -> Optional[BrowserManager]:
    """Get BrowserManager from a Lamia instance (returns None on failure)."""
    try:
        return BrowserManager.get_browser_manager_from_lamia(lamia_instance)
    except Exception:
        return None


def _get_web_manager(lamia_instance: Any) -> Optional[Any]:
    """Get WebManager from a Lamia instance (returns None on failure)."""
    try:
        engine = lamia_instance._engine
        return engine.manager_factory.get_manager(CommandType.WEB)
    except Exception:
        return None


def _run_async(coro):
    """Run an async coroutine from synchronous code."""
    return EventLoopManager.run_coroutine(coro)


def pre_validate_session(lamia_instance: Any, probe_url: Optional[str],
                         return_type: Any) -> None:
    """Check whether the user is already logged in and skip the session if so.

    Called at the *beginning* of a ``with session(...)`` block.  Two checks
    are performed in order:

    1. **URL check** -- if ``probe_url`` is provided and the browser is
       already on that URL (ignoring query-params / trailing slashes), the
       user is clearly logged in → raise ``SessionSkipException``.
    2. **Model validation** -- run ``GET_PAGE_SOURCE`` through the standard
       pipeline with the given ``return_type``.  If the Pydantic model
       matches, the user is logged in → raise ``SessionSkipException``.

    If neither check passes, the function returns normally and the login
    actions in the session body execute.

    Raises:
        SessionSkipException: when the user is already logged in.
    """
    browser_manager = _get_browser_manager(lamia_instance)

    # --- URL check ---
    if probe_url and browser_manager:
        try:
            current_url = _run_async(browser_manager.get_current_url()) or ""
            if _urls_match_ignoring_params(current_url, probe_url):
                logger.info(
                    f"Already on target URL ({current_url}), skipping login"
                )
                raise SessionSkipException(
                    f"Already on target URL: {current_url}"
                )
        except SessionSkipException:
            raise
        except Exception:
            pass

    # --- Model validation check ---
    web_manager = _get_web_manager(lamia_instance)
    if web_manager:
        web_manager.recent_actions.clear()
    try:
        result = lamia_instance.run(
            WebCommand(action=WebActionType.GET_PAGE_SOURCE),
            return_type=return_type,
        )
        if result.typed_result is not None:
            logger.info("Pre-validation passed - page matches expected model")
            raise SessionSkipException(
                "Session validation passed - already in desired state"
            )
    except SessionSkipException:
        raise
    except Exception:
        pass


def validate_login_completion(lamia_instance: Any, probe_url: Optional[str], return_type: Any,
                              timeout: int = 300, poll_interval: int = 10) -> None:
    """Validate that login completed successfully by checking page state.

    Three-phase approach:
      1. Fast path -- if the browser already redirected to probe_url (URL match
         alone is sufficient — no model validation required).
      2. Polling -- check the current page periodically without navigating, so
         that intermediate verification pages (captcha, ID input) are never
         disrupted.
      3. Last resort -- run probe_url validation in a temporary tab-bound
         BrowserManager while preserving the original browser manager.

    If all phases exhaust, the function returns normally (does NOT raise) so
    that ``__exit__`` can still save cookies.

    Args:
        lamia_instance: The Lamia instance for running web commands
        probe_url: Target URL for the logged-in state (e.g. the homepage)
        return_type: Expected return type for validation (e.g. HTML[HomePageModel])
        timeout: Max seconds to wait for successful validation (default 300)
        poll_interval: Seconds between validation attempts
    """
    browser_manager = _get_browser_manager(lamia_instance)

    # Reset stuck detection -- the polling loop intentionally repeats GET_PAGE_SOURCE
    web_manager = _get_web_manager(lamia_instance)
    if web_manager:
        web_manager.recent_actions.clear()

    # --- Phase 1: fast-path URL check (URL match alone = success) ---
    if probe_url and browser_manager:
        try:
            current_url = _run_async(browser_manager.get_current_url()) or ""
            if _urls_match_ignoring_params(current_url, probe_url):
                logger.info(
                    f"Browser already on target URL ({current_url}), "
                    f"login confirmed (fast path)"
                )
                return
        except Exception as e:
            logger.debug(f"Fast-path URL check failed: {e}")

    # --- Phase 2: poll current page without navigating ---
    start = time.time()
    last_error = None

    while True:
        if web_manager:
            web_manager.recent_actions.clear()
        result = lamia_instance.run(
            WebCommand(action=WebActionType.GET_PAGE_SOURCE),
            return_type=return_type,
        )

        if result.typed_result is not None:
            logger.info("Post-login validation passed")
            return

        elapsed = time.time() - start
        last_error = result.result_text

        if elapsed >= timeout:
            break

        remaining = timeout - elapsed
        wait = min(poll_interval, remaining)
        logger.info(
            f"Login not yet confirmed (elapsed {elapsed:.0f}s / {timeout}s). "
            f"Waiting {wait:.0f}s for verification to complete..."
        )
        time.sleep(wait)

    # --- Phase 3: last-resort -- validate in temporary tab BrowserManager ---
    if probe_url and browser_manager and web_manager:
        tab_browser_manager = None
        original_browser_manager = web_manager.browser_manager
        try:
            logger.info(f"Opening probe tab for final login check: {probe_url}")
            tab_browser_manager = _run_async(browser_manager.open_new_tab())
            web_manager.browser_manager = tab_browser_manager

            if web_manager:
                web_manager.recent_actions.clear()
            lamia_instance.run(
                WebCommand(action=WebActionType.NAVIGATE, url=probe_url),
            )
            if web_manager:
                web_manager.recent_actions.clear()
            result = lamia_instance.run(
                WebCommand(action=WebActionType.GET_PAGE_SOURCE),
                return_type=return_type,
            )
            if result.typed_result is not None:
                logger.info("Post-login validation passed (probe tab)")
                return
            last_error = result.result_text
        except Exception as e:
            logger.warning(f"Probe tab validation failed: {e}")
        finally:
            web_manager.browser_manager = original_browser_manager
            if tab_browser_manager:
                try:
                    _run_async(tab_browser_manager.close())
                except Exception as e:
                    logger.warning(f"Failed to close probe tab manager: {e}")

    # Do NOT raise here -- the user may have completed login manually even if
    # validation doesn't match the expected page model.  Raising would cause
    # __exit__ to see an exception and skip saving cookies, which is worse
    # than a false-negative validation.
    logger.warning(
        f"Post-login validation could not confirm success after {timeout}s. "
        f"Last validation error: {last_error}. "
        f"Cookies will still be saved in case login actually succeeded."
    )