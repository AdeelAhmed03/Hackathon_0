#!/usr/bin/env python3
"""
Manual X/Twitter Cookie Extraction Tool

Due to X/Twitter's strict anti-automation measures, this script helps you
manually log in to X/Twitter and then extract the necessary cookies.

Steps:
1. Run this script
2. Log in to X/Twitter manually in the opened browser
3. Once logged in, navigate to https://twitter.com/
4. Come back to this terminal and press Enter
5. The script will extract and save your cookies
"""

import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

def extract_x_cookies():
    """Manually extract X cookies after user logs in."""
    print("X/Twitter Cookie Extraction Tool")
    print("="*50)
    print("Due to X/Twitter's security measures, we need to extract cookies manually.")
    print("\nSteps:")
    print("1. A browser will open - please log in to your X/Twitter account manually")
    print("2. After logging in, navigate to https://twitter.com/ (the main timeline)")
    print("3. Return to this terminal and press Enter")
    print("4. The script will extract your cookies and save them")
    print("\nIMPORTANT: Don't close the browser until the process is complete!")
    print("="*50)

    input("\nPress Enter to open the browser for X/Twitter login...")

    with sync_playwright() as p:
        print("Opening browser...")
        browser = p.chromium.launch(headless=False, args=[
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled'
        ])

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 900},
            locale='en-US'
        )

        # Add script to hide automation
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        page = context.new_page()
        print("Browser opened. Please log in to X/Twitter manually.")
        print("Navigate to https://twitter.com/ once you're logged in.")

        input("\nAfter you have logged in and are on https://twitter.com/, press Enter here...")

        print("Extracting cookies...")

        # Go to twitter.com to make sure we're on the right page
        try:
            page.goto("https://twitter.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(3000)  # Wait for page to load
        except:
            print("Note: Page load had issues, but continuing with cookie extraction...")

        # Get all cookies
        cookies = context.cookies()

        if not cookies:
            print("❌ No cookies found! Please make sure you are logged in.")
            browser.close()
            return False

        # Find X/Twitter specific cookies
        x_cookies = []
        essential_cookie_names = [
            'auth_token', 'ct0', 'personalization_id', 'guest_id',
            'kdt', 'dnt', 'att', '_twitter_sess'
        ]

        for cookie in cookies:
            if any(essential_name in cookie['name'].lower() for essential_name in essential_cookie_names) or \
               'twitter' in cookie['domain'] or \
               '.twitter.com' in cookie['domain']:
                x_cookies.append(cookie)

        if not x_cookies:
            print("❌ Could not find X/Twitter specific cookies!")
            print("Available cookies:", [c['name'] for c in cookies])
            browser.close()
            return False

        # Also save all cookies in case we missed some
        x_cookies = cookies  # Save all for completeness

        print(f"✓ Found {len(x_cookies)} cookies")

        # Point to main Platinum-Tier data directory (same as other auths)
        vault_dir = Path(__file__).parent.parent.parent  # Go to Platinum-Tier root
        cookie_dir = vault_dir / "data" / "Logs"
        cookie_dir.mkdir(parents=True, exist_ok=True)

        cookie_file = cookie_dir / "x_cookies.json"

        # Save cookies
        with open(cookie_file, 'w', encoding='utf-8') as f:
            json.dump(x_cookies, f, indent=2)

        print(f"✓ Cookies saved to: {cookie_file}")
        print("✓ X/Twitter authentication completed successfully!")

        browser.close()
        return True

if __name__ == "__main__":
    success = extract_x_cookies()
    if success:
        print("\n🎉 X/Twitter authentication completed!")
        print("You can now use the Platinum Tier system with X/Twitter access.")
    else:
        print("\n❌ X/Twitter authentication failed!")
        print("Please try again, ensuring you are properly logged in first.")