#!/usr/bin/env python3
"""
Social Media Authentication Wrapper for Platinum Tier AI Employee

This wrapper allows the orchestrator to trigger social media authentication
similar to how other MCP services are integrated.
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

# Add the main Platinum Tier directory to the path
VAULT_DIR = Path(__file__).parent
sys.path.insert(0, str(VAULT_DIR))

from social_auth import SocialMediaAuth


class SocialAuthWrapper:
    """Wrapper for social media authentication to integrate with Platinum Tier system."""

    def __init__(self):
        self.auth = SocialMediaAuth()

    def authenticate_platform(self, platform: str, headless: bool = False) -> Dict:
        """
        Authenticate a social media platform.

        Args:
            platform: "facebook", "instagram", or "x"
            headless: Whether to run browser in headless mode

        Returns:
            Dictionary with authentication result
        """
        try:
            if platform == "facebook":
                success = self.auth.authenticate_facebook(headless=headless)
            elif platform == "instagram":
                success = self.auth.authenticate_instagram(headless=headless)
            elif platform == "x":
                success = self.auth.authenticate_x(headless=headless)
            else:
                return {
                    "success": False,
                    "error": f"Unknown platform: {platform}. Use facebook, instagram, or x"
                }

            if success:
                return {
                    "success": True,
                    "message": f"{platform.title()} authentication completed",
                    "timestamp": datetime.now().isoformat(),
                    "platform": platform
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to authenticate {platform}",
                    "timestamp": datetime.now().isoformat()
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def check_authentication(self, platform: str) -> Dict:
        """
        Check if a platform is already authenticated (cookies exist).

        Args:
            platform: "facebook", "instagram", or "x"

        Returns:
            Dictionary with authentication status
        """
        try:
            cookies = self.auth.load_cookies(platform)
            if cookies:
                return {
                    "success": True,
                    "authenticated": True,
                    "cookie_count": len(cookies),
                    "platform": platform,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": True,
                    "authenticated": False,
                    "platform": platform,
                    "timestamp": datetime.now().isoformat()
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def list_authenticated_platforms(self) -> Dict:
        """List all platforms that are currently authenticated."""
        platforms = ["facebook", "instagram", "x"]
        result = {
            "authenticated_platforms": [],
            "platform_status": {},
            "timestamp": datetime.now().isoformat()
        }

        for platform in platforms:
            status = self.check_authentication(platform)
            result["platform_status"][platform] = status
            if status.get("authenticated", False):
                result["authenticated_platforms"].append(platform)

        return result


def main():
    """Command line interface for the social auth wrapper."""
    import argparse

    parser = argparse.ArgumentParser(description="Social Media Auth Wrapper for Platinum Tier")
    parser.add_argument("action", choices=["auth", "check", "list"],
                       help="Action to perform: auth (authenticate), check (check status), list (list all)")
    parser.add_argument("--platform", choices=["facebook", "instagram", "x"],
                       help="Platform for auth/check actions")
    parser.add_argument("--headless", action="store_true",
                       help="Run browser in headless mode for authentication")

    args = parser.parse_args()

    wrapper = SocialAuthWrapper()

    if args.action == "auth":
        if not args.platform:
            print("Error: --platform is required for auth action")
            sys.exit(1)

        result = wrapper.authenticate_platform(args.platform, headless=args.headless)
        print(json.dumps(result, indent=2))

    elif args.action == "check":
        if not args.platform:
            print("Error: --platform is required for check action")
            sys.exit(1)

        result = wrapper.check_authentication(args.platform)
        print(json.dumps(result, indent=2))

    elif args.action == "list":
        result = wrapper.list_authenticated_platforms()
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()