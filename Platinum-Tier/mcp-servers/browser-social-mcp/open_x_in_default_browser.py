#!/usr/bin/env python3
"""
Open X/Twitter in Default System Browser

This script opens the X/Twitter login page in your default system browser
to avoid any Playwright-related blocking or security issues.
"""

import webbrowser
import time
import subprocess
import sys
from pathlib import Path

def open_x_in_default_browser():
    """Open X/Twitter login in the system's default browser."""
    print("X/Twitter Default Browser Opener")
    print("="*50)
    print("Opening X/Twitter login in your default browser...")
    print("This avoids Playwright-related security blocks.")
    print("="*50)

    # X/Twitter login URL
    login_url = "https://twitter.com/i/flow/login"

    print(f"Opening URL: {login_url}")
    print("\nYour default browser will now open with the X/Twitter login page.")
    print("Please log in manually in your browser.")

    # Open the URL in the default browser
    webbrowser.open(login_url)

    print("\nBrowser opened successfully!")
    print("\nAfter you log in successfully, please run the cookie extraction tool:")
    print("  python extract_x_cookies.py")
    print("\nThis will capture your logged-in session and save it for the Platinum Tier system.")

if __name__ == "__main__":
    open_x_in_default_browser()