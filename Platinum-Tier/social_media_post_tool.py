import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add the vault directory to the Python path
VAULT_DIR = Path('.').resolve()
sys.path.insert(0, str(VAULT_DIR))

def social_media_post_tool(text: str, platform: str = "all", images: Optional[List[str]] = None) -> str:
    """
    Posts to multiple social media platforms.

    Args:
        text: The text content for the social media post
        platform: The platform to post to ('linkedin', 'facebook', 'instagram', 'x', or 'all')
        images: Optional list of image URLs to include in the post

    Returns:
        A string indicating the success or failure of the posts
    """
    results = []

    if platform in ["all", "linkedin"]:
        try:
            from linkedin_post_tool import linkedin_post_tool
            linkedin_result = linkedin_post_tool(text, images)
            results.append(f"LinkedIn: {linkedin_result}")
        except Exception as e:
            results.append(f"LinkedIn: Error importing tool - {str(e)}")

    if platform in ["all", "facebook"]:
        try:
            from facebook_instagram_post_tool import facebook_post_tool
            facebook_result = facebook_post_tool(text, images)
            results.append(f"Facebook: {facebook_result}")
        except Exception as e:
            results.append(f"Facebook: Error importing tool - {str(e)}")

    if platform in ["all", "instagram"]:
        try:
            from facebook_instagram_post_tool import instagram_post_tool
            instagram_result = instagram_post_tool(text, images)
            results.append(f"Instagram: {instagram_result}")
        except Exception as e:
            results.append(f"Instagram: Error importing tool - {str(e)}")

    if platform in ["all", "x"]:
        try:
            from x_post_tool import x_post_tool
            x_result = x_post_tool(text, images)
            # If the API version fails, try the web automation version as fallback
            if "CreditsDepleted" in x_result or "oauth1-permissions" in x_result:
                try:
                    from x_web_post_tool import x_web_post_tool_stub
                    x_web_result = x_web_post_tool_stub(text, images)
                    results.append(f"X (Web): {x_web_result}")
                except Exception as e:
                    results.append(f"X (API): {x_result}")
            else:
                results.append(f"X (API): {x_result}")
        except Exception as e:
            # Try the web version if API tool isn't available
            try:
                from x_web_post_tool import x_web_post_tool_stub
                x_web_result = x_web_post_tool_stub(text, images)
                results.append(f"X (Web): {x_web_result}")
            except Exception as web_e:
                results.append(f"X: Error importing tools - API: {str(e)}, Web: {str(web_e)}")

    return "\n".join(results)

def test_all_platforms():
    """Test posting to all platforms"""
    test_text = f"Test post from AI Employee Vault to all social platforms - {Path(__file__).stem}"
    result = social_media_post_tool(test_text, platform="all")
    print(result)

if __name__ == "__main__":
    test_all_platforms()