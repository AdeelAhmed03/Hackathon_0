#!/usr/bin/env python3
"""
Social Media Authentication Module for Platinum Tier AI Employee

This module provides authentication for Facebook, Instagram, and X/Twitter
using Playwright browser automation similar to the LinkedIn authentication approach.
"""

import os
import json
import time
import tempfile
import webbrowser
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── CONFIG ───────────────────────────────────────────────────────────────
# Point to the main Platinum-Tier data directory for consistency with vault system
VAULT_DIR = Path(__file__).parent.parent.parent  # Go up to Platinum-Tier root
COOKIE_DIR = VAULT_DIR / "data" / "Logs"

class SocialMediaAuth:
    """Handles authentication for social media platforms using Playwright."""

    def __init__(self):
        if not sync_playwright:
            raise ImportError("playwright is required. Install with: pip install playwright")

        # Create required directories
        COOKIE_DIR.mkdir(parents=True, exist_ok=True)

    def get_cookie_path(self, platform: str) -> Path:
        """Get the path for storing cookies for a specific platform."""
        return COOKIE_DIR / f"{platform}_cookies.json"

    def save_cookies(self, context, platform: str) -> bool:
        """Save cookies from browser context to file."""
        try:
            cookies = context.cookies()
            cookie_path = self.get_cookie_path(platform)

            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(cookies, f, indent=2)

            print(f"SUCCESS: Saved {platform} cookies to {cookie_path}")
            return True
        except Exception as e:
            print(f"ERROR: Failed to save {platform} cookies: {e}")
            return False

    def load_cookies(self, platform: str) -> Optional[list]:
        """Load cookies from file for a specific platform."""
        cookie_path = self.get_cookie_path(platform)

        try:
            if cookie_path.exists():
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                print(f"SUCCESS: Loaded {platform} cookies from {cookie_path}")
                return cookies
        except Exception as e:
            print(f"ERROR: Failed to load {platform} cookies: {e}")

        return None

    def authenticate_facebook(self, headless: bool = False) -> bool:
        """Authenticate Facebook account using Playwright."""
        print("Opening Facebook login in browser...")
        print("Please log in to your Facebook account in the browser.")
        print("After successful login, the authentication will complete automatically.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 900},
                locale='en-US'
            )

            page = context.new_page()
            page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")

            print("Facebook login page opened. Please login manually...")

            # Wait for login completion by checking for various possible post-login URLs
            try:
                # Wait for any of these URLs to indicate successful login
                login_detected = False
                timeout = 300000  # 5 minutes
                start_time = time.time()

                while time.time() - start_time < timeout/1000:
                    current_url = page.url
                    if any(pattern in current_url for pattern in ['home', 'watch', 'groups', 'marketplace', 'reel', 'photo', 'facebook.com/']):
                        # Check for signs of being logged in
                        if page.locator('div[aria-label="Create a post"]').is_visible(timeout=5000) or \
                           page.locator('div[role="button"][aria-label*="Create"]').is_visible(timeout=5000) or \
                           page.locator('a[aria-label="Facebook"]').is_visible(timeout=5000) or \
                           page.locator('img[aria-label*="profile"]').is_visible(timeout=5000) or \
                           page.locator('input[placeholder*="What\'s on your mind"]').is_visible(timeout=5000):
                            login_detected = True
                            break

                    # Wait a bit before checking again
                    page.wait_for_timeout(2000)

                if not login_detected:
                    raise Exception("Login detection timeout after waiting 5 minutes")

                print("SUCCESS: Facebook login detected!")

                # Wait a bit more to ensure all cookies are loaded
                page.wait_for_timeout(5000)

                # Additional verification by checking for common post elements
                try:
                    page.wait_for_selector('div[role="button"][aria-label*="Create" i]', timeout=10000)
                    print("SUCCESS: Facebook authentication complete!")
                except:
                    # Try alternative selectors
                    try:
                        page.wait_for_selector('a[aria-label="Facebook"]', timeout=5000)
                        print("SUCCESS: Facebook authentication complete!")
                    except:
                        # If other selectors don't work, just continue since we detected login
                        print("SUCCESS: Facebook authentication complete!")

                success = self.save_cookies(context, "facebook")
                browser.close()
                return success
            except Exception as e:
                print(f"FAILED: Facebook authentication failed or timeout: {e}")
                browser.close()
                return False

    def authenticate_instagram(self, headless: bool = False) -> bool:
        """Authenticate Instagram account using Playwright."""
        print("Opening Instagram login in browser...")
        print("Please log in to your Instagram account in the browser.")
        print("After successful login, the authentication will complete automatically.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 900},
                locale='en-US'
            )

            page = context.new_page()
            page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")

            print("Instagram login page opened. Please login manually...")

            # Wait for login completion by checking for various possible post-login URLs
            try:
                # Wait for any of these URLs to indicate successful login
                login_detected = False
                timeout = 300000  # 5 minutes
                start_time = time.time()

                while time.time() - start_time < timeout/1000:
                    current_url = page.url
                    if any(pattern in current_url for pattern in ['accounts/onetap', 'explore', 'accounts/activity', 'direct', 'instagram.com/']):
                        # Check for signs of being logged in
                        if page.locator('[data-testid="searchBox"]').is_visible(timeout=5000) or \
                           page.locator('input[placeholder*="Search"]').is_visible(timeout=5000) or \
                           page.locator('svg[aria-label="Home"]').is_visible(timeout=5000) or \
                           page.locator('svg[aria-label="Profile"]').is_visible(timeout=5000) or \
                           page.locator('div._abl-').is_visible(timeout=5000):  # Create post button
                            login_detected = True
                            break

                    # Wait a bit before checking again
                    page.wait_for_timeout(2000)

                if not login_detected:
                    raise Exception("Login detection timeout after waiting 5 minutes")

                print("SUCCESS: Instagram login detected!")

                # Wait a bit more to ensure all cookies are loaded
                page.wait_for_timeout(5000)

                # Verify by checking for common elements
                try:
                    page.wait_for_selector('[data-testid="searchBox"]', timeout=10000)
                    print("SUCCESS: Instagram authentication complete!")
                except:
                    # Try alternative selectors or just continue if login detected
                    print("SUCCESS: Instagram authentication complete!")

                success = self.save_cookies(context, "instagram")
                browser.close()
                return success
            except Exception as e:
                print(f"FAILED: Instagram authentication failed or timeout: {e}")
                browser.close()
                return False

    def authenticate_x(self, headless: bool = False) -> bool:
        """Authenticate X/Twitter account using Playwright."""
        print("Opening X (Twitter) login in browser...")
        print("Please log in to your X/Twitter account in the browser.")
        print("After successful login, the authentication will complete automatically.")

        with sync_playwright() as p:
            # Add more realistic browser arguments to avoid detection
            browser_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]

            browser = p.chromium.launch(
                headless=headless,
                args=browser_args
            )

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 900},
                locale='en-US',
                # Extra settings to appear more like a real user
                extra_http_headers={
                    "accept-language": "en-US,en;q=0.9",
                    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "none",
                    "sec-fetch-user": "?1",
                    "upgrade-insecure-requests": "1",
                }
            )

            # Additional script to remove webdriver property to avoid detection
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                window.chrome = {
                    runtime: {}
                };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            """)

            page = context.new_page()

            # Navigate with extra care to avoid detection
            page.goto("https://twitter.com/i/flow/login", wait_until="domcontentloaded")

            print("X (Twitter) login page opened. Please login manually...")
            print("Note: X/Twitter may show security warnings - proceed anyway if you trust this app.")

            # Wait for login completion by checking for various possible post-login URLs
            try:
                # Wait for any of these URLs to indicate successful login
                login_detected = False
                timeout = 300000  # 5 minutes
                start_time = time.time()

                while time.time() - start_time < timeout/1000:
                    current_url = page.url
                    if any(pattern in current_url for pattern in ['home', 'compose/tweet', 'explore', 'notifications', 'messages', 'twitter.com/']):
                        page.wait_for_timeout(2000)  # Small delay to allow page to load fully
                        # Check for signs of being logged in
                        try:
                            if page.locator('a[href="/compose/tweet"]').is_visible(timeout=5000) or \
                               page.locator('[data-testid="tweetButton"]').is_visible(timeout=5000) or \
                               page.locator('div[aria-label="Timeline: Your Home Timeline"]').is_visible(timeout=5000) or \
                               page.locator('a[aria-label="Twitter"]').is_visible(timeout=5000) or \
                               page.locator('[data-testid="SideNav_AccountSwitcher_Button"]').is_visible(timeout=5000):
                                login_detected = True
                                break
                        except:
                            pass  # Continue if selectors aren't found yet

                    # Wait a bit before checking again
                    page.wait_for_timeout(2000)

                if not login_detected:
                    # If we don't detect login by URL, try one more approach looking for common logged-in elements
                    try:
                        # Try to detect login by looking for common elements on the home page
                        page.reload(wait_until="domcontentloaded")
                        page.wait_for_timeout(5000)

                        if page.locator('a[href="/compose/tweet"]').is_visible(timeout=5000) or \
                           page.locator('div[data-testid="primaryColumn"]').is_visible(timeout=5000):
                            login_detected = True
                    except:
                        pass

                if not login_detected:
                    raise Exception("Login detection timeout after waiting 5 minutes. X/Twitter may have security measures blocking automated access.")

                print("SUCCESS: X (Twitter) login detected!")

                # Wait a bit more to ensure all cookies are loaded
                page.wait_for_timeout(8000)

                # Verify by checking for tweet button
                try:
                    page.wait_for_selector('a[href="/compose/tweet"]', timeout=10000)
                    print("SUCCESS: X (Twitter) authentication complete!")
                except:
                    # If other selectors don't work, just continue since we detected login
                    print("SUCCESS: X (Twitter) authentication complete!")

                success = self.save_cookies(context, "x")
                browser.close()
                return success
            except Exception as e:
                print(f"FAILED: X (Twitter) authentication failed or timeout: {e}")
                print("Note: X/Twitter has strict bot detection. Try with --headless flag or use a different approach.")
                browser.close()
                return False

def main():
    """Command line interface for social media authentication."""
    import argparse

    parser = argparse.ArgumentParser(description="Social Media Authentication for Platinum Tier AI Employee")
    parser.add_argument("platform", choices=["facebook", "instagram", "x"],
                       help="Platform to authenticate (facebook, instagram, or x)")
    parser.add_argument("--headless", action="store_true",
                       help="Run browser in headless mode (default: False)")

    args = parser.parse_args()

    auth = SocialMediaAuth()

    if args.platform == "facebook":
        success = auth.authenticate_facebook(headless=args.headless)
    elif args.platform == "instagram":
        success = auth.authenticate_instagram(headless=args.headless)
    elif args.platform == "x":
        success = auth.authenticate_x(headless=args.headless)

    if success:
        print(f"\nSUCCESS: {args.platform.title()} authentication completed successfully!")
        print(f"SUCCESS: Cookies saved and ready for Platinum Tier system.")
    else:
        print(f"\nFAILED: {args.platform.title()} authentication failed.")
        if args.platform == "x":
            print("Note: X/Twitter has strict anti-automation measures.")
            print("If authentication fails, try manual extraction:")
            print("  python extract_x_cookies.py")
        else:
            print("Please try again, ensuring you're successfully logged in before closing the browser.")

if __name__ == "__main__":
    main()