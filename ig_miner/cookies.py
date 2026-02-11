"""Cookie management — extract from browser or load from file."""

import json
import logging
import platform
from pathlib import Path

log = logging.getLogger(__name__)


def load_cookies(cookie_file: str | Path) -> dict:
    """Load Instagram cookies from a JSON file.

    Args:
        cookie_file: Path to cookies JSON file.

    Returns:
        Dict of cookie name → value.

    Raises:
        SystemExit: If file missing or no sessionid.
    """
    path = Path(cookie_file)
    if not path.exists():
        log.error(f"Cookie file not found: {path}")
        log.error("Run: igminer --refresh-cookies")
        raise SystemExit(1)

    with open(path) as f:
        cookies = json.load(f)

    if not cookies.get("sessionid"):
        log.error("Cookies missing 'sessionid'! Run: igminer --refresh-cookies")
        raise SystemExit(1)

    log.info(f"Loaded cookies (sessionid: ...{cookies['sessionid'][-8:]})")
    return cookies


def refresh_cookies(cookie_file: str | Path) -> dict:
    """Extract fresh Instagram cookies from Chrome.

    Uses pycookiecheat on macOS/Linux, browser-cookie3 on Windows.
    Requires being logged into Instagram in Chrome.

    Args:
        cookie_file: Where to save the extracted cookies.

    Returns:
        Dict of cookie name → value.
    """
    system = platform.system()
    cookies = {}

    if system in ("Darwin", "Linux"):
        cookies = _extract_pycookiecheat()
    elif system == "Windows":
        cookies = _extract_browser_cookie3()
    else:
        log.error(f"Unsupported platform: {system}")
        raise SystemExit(1)

    if not cookies.get("sessionid"):
        log.error(
            "No sessionid found! Make sure you're logged into Instagram in Chrome."
        )
        raise SystemExit(1)

    path = Path(cookie_file)
    with open(path, "w") as f:
        json.dump(cookies, f)

    log.info(f"Saved {len(cookies)} cookies to {path.name}")
    log.info(f"sessionid: ...{cookies['sessionid'][-8:]}")
    return cookies


def _extract_pycookiecheat() -> dict:
    """Extract cookies using pycookiecheat (macOS/Linux)."""
    try:
        from pycookiecheat import chrome_cookies
    except ImportError:
        log.info("Installing pycookiecheat...")
        import subprocess
        subprocess.run(
            ["pip", "install", "pycookiecheat"],
            capture_output=True,
            check=True,
        )
        from pycookiecheat import chrome_cookies

    return chrome_cookies("https://www.instagram.com")


def _extract_browser_cookie3() -> dict:
    """Extract cookies using browser-cookie3 (Windows)."""
    try:
        import browser_cookie3
    except ImportError:
        log.info("Installing browser-cookie3...")
        import subprocess
        subprocess.run(
            ["pip", "install", "browser-cookie3"],
            capture_output=True,
            check=True,
        )
        import browser_cookie3

    cj = browser_cookie3.chrome(domain_name=".instagram.com")
    return {c.name: c.value for c in cj}
