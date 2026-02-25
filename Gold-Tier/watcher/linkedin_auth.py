#!/usr/bin/env python3
"""
LinkedIn Cookie-Based Authentication Helper (Silver Tier)

Opens a Playwright browser so you can log into LinkedIn manually.
After login, captures session cookies and saves them to
data/Logs/linkedin_cookies.json for the LinkedIn watcher to use.

No LinkedIn App or OAuth client needed — just your email and password.

Usage:
  python watcher/linkedin_auth.py            # opens browser, you log in
  python watcher/linkedin_auth.py --check    # verify saved cookies are valid

Requires: pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VAULT_DIR = Path(__file__).parent.parent.resolve()
COOKIES_FILE = VAULT_DIR / "data" / "Logs" / "linkedin_cookies.json"
LOGS_DIR = VAULT_DIR / "data" / "Logs"


def authenticate() -> None:
    """Open browser for LinkedIn login, capture cookies after success."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run:")
        print("  pip install playwright")
        print("  python -m playwright install chromium")
        sys.exit(1)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("LinkedIn Authentication")
    print("=" * 60)
    print()
    print("A browser window will open to LinkedIn.")
    print("Log in with your email and password.")
    print("Once you see your LinkedIn feed, the cookies will be")
    print("captured automatically and saved for the watcher.")
    print()

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1280, "height": 900},
        locale="en-US",
    )
    page = context.new_page()

    print("Opening LinkedIn login page...")
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60_000)

    # Wait for user to log in — detected by navigation to feed or main page
    print()
    print("Waiting for you to log in...")
    print("(This will auto-detect when login is complete)")
    print()

    try:
        # Wait until the URL changes away from /login or /checkpoint
        # The feed URL is linkedin.com/feed/ or linkedin.com/in/ etc.
        page.wait_for_url(
            "**/feed**",
            timeout=300_000,  # 5 minutes to log in
        )
    except Exception:
        # Fallback: check if we're on any authenticated page
        current_url = page.url
        if "/login" in current_url or "/checkpoint" in current_url:
            print("Login doesn't seem complete yet.")
            print("Waiting 30 more seconds for you to finish...")
            try:
                page.wait_for_url("**/feed**", timeout=30_000)
            except Exception:
                pass

    current_url = page.url
    if "/login" in current_url:
        print("Login failed or timed out. Please try again.")
        browser.close()
        pw.stop()
        sys.exit(1)

    print(f"Logged in! Current page: {current_url}")
    print("Capturing cookies...")

    # Get all cookies
    cookies = context.cookies()

    # Filter to LinkedIn cookies only
    li_cookies = [c for c in cookies if "linkedin.com" in c.get("domain", "")]

    if not li_cookies:
        print("Warning: No LinkedIn cookies found. Authentication may have failed.")
        browser.close()
        pw.stop()
        sys.exit(1)

    # Save cookies
    COOKIES_FILE.write_text(json.dumps(li_cookies, indent=2), encoding="utf-8")

    # Extract key info
    li_at = next((c["value"] for c in li_cookies if c["name"] == "li_at"), None)
    jsessionid = next((c["value"] for c in li_cookies if c["name"] == "JSESSIONID"), None)

    browser.close()
    pw.stop()

    print()
    print("=" * 60)
    print("LinkedIn authentication complete!")
    print("=" * 60)
    print(f"  Cookies saved to: {COOKIES_FILE}")
    print(f"  Total cookies: {len(li_cookies)}")
    print(f"  Session cookie (li_at): {'found' if li_at else 'NOT FOUND'}")
    print(f"  CSRF token (JSESSIONID): {'found' if jsessionid else 'NOT FOUND'}")
    print()
    print("The LinkedIn watcher will use these cookies automatically.")
    print("You can now start all watchers with: pm2 start ecosystem.config.js")


def check_cookies() -> None:
    """Verify that saved cookies exist and are usable."""
    if not COOKIES_FILE.exists():
        print("No saved cookies found.")
        print("Run: python watcher/linkedin_auth.py")
        sys.exit(1)

    try:
        cookies = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"Cookie file corrupt: {exc}")
        sys.exit(1)

    li_at = next((c for c in cookies if c["name"] == "li_at"), None)
    jsessionid = next((c for c in cookies if c["name"] == "JSESSIONID"), None)

    print(f"Cookie file: {COOKIES_FILE}")
    print(f"Total cookies: {len(cookies)}")
    print(f"Session cookie (li_at): {'PRESENT' if li_at else 'MISSING'}")
    print(f"CSRF token (JSESSIONID): {'PRESENT' if jsessionid else 'MISSING'}")

    if not li_at:
        print("\nSession cookie missing — re-authenticate:")
        print("  python watcher/linkedin_auth.py")
        sys.exit(1)

    # Quick validation — try fetching profile
    import requests
    session = requests.Session()
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

    csrf = jsessionid["value"].strip('"') if jsessionid else ""
    session.headers.update({
        "csrf-token": csrf,
        "X-Restli-Protocol-Version": "2.0.0",
    })

    try:
        resp = session.get(
            "https://api.linkedin.com/v2/me",
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            name = f"{data.get('localizedFirstName', '')} {data.get('localizedLastName', '')}".strip()
            print(f"\nAuthenticated as: {name}")
            print("Cookies are valid!")
        elif resp.status_code == 401:
            print("\nCookies expired or invalid. Re-authenticate:")
            print("  python watcher/linkedin_auth.py")
            sys.exit(1)
        else:
            print(f"\nAPI returned status {resp.status_code} — cookies may still work")
    except Exception as exc:
        print(f"\nCould not verify cookies: {exc}")
        print("Cookies may still work — try starting the watcher.")


def main():
    parser = argparse.ArgumentParser(
        description="LinkedIn authentication — log in via browser, cookies saved for watcher"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if saved cookies are valid (don't open browser)",
    )
    args = parser.parse_args()

    if args.check:
        check_cookies()
    else:
        authenticate()


if __name__ == "__main__":
    main()
