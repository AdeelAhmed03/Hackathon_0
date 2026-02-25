import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Add the vault directory to the Python path
VAULT_DIR = Path('.').resolve()
sys.path.insert(0, str(VAULT_DIR))

def linkedin_post_tool(text: str, images: Optional[List[str]] = None) -> str:
    """
    Posts to LinkedIn profile using the LinkedIn UGC (User Generated Content) API.

    Args:
        text: The text content for the LinkedIn post
        images: Optional list of image URLs to include in the post

    Returns:
        A string indicating the success or failure of the post
    """
    # Get the access token from environment variables
    access_token = os.getenv('LINKEDIN_ACCESS_TOKEN')

    if not access_token or not access_token.startswith('AQ'):
        return "Error: LinkedIn access token not found or invalid. Please set LINKEDIN_ACCESS_TOKEN in your .env file."

    # Get the member ID directly from the environment variable
    person_urn = os.getenv('LINKEDIN_PERSON_URN', 'AaZ015NFNn')

    # If it already has the right format, use it; otherwise, construct it
    if person_urn.startswith('urn:li:'):
        author_urn = person_urn
    else:
        # Try both possible formats
        author_urn = f"urn:li:member:{person_urn}"

    # LinkedIn UGC API endpoint for creating posts
    url = "https://api.linkedin.com/v2/ugcPosts"

    # Set up the headers with the access token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    # Prepare the payload for the post using the correct UGC format with proper visibility
    payload = {
        "author": author_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {
                    "text": text
                },
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    # If images are provided, we need to handle them differently
    if images and len(images) > 0:
        # For now, we'll just mention that images were requested
        # Proper image handling requires multiple API calls to register and upload images
        payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareCommentary"]["text"] += f"\n\nNote: {len(images)} image(s) were requested but require additional API processing."

    try:
        # Make the API request to post to LinkedIn profile
        response = requests.post(url, headers=headers, json=payload)

        # Check if the request was successful
        if response.status_code in [200, 201, 202]:
            response_data = response.json()
            post_id = response_data.get("id", "unknown")
            return f"Success: LinkedIn post created successfully with ID {post_id}. Post: {text[:100]}..."
        else:
            # Try the alternative URN format if the first one fails
            if "member:" in author_urn:
                alternative_urn = author_urn.replace("member:", "person:")
            else:
                alternative_urn = f"urn:li:member:{person_urn.split(':')[-1] if ':' in person_urn else person_urn}"

            payload["author"] = alternative_urn
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code in [200, 201, 202]:
                response_data = response.json()
                post_id = response_data.get("id", "unknown")
                return f"Success: LinkedIn post created successfully with ID {post_id}. Post: {text[:100]}..."
            else:
                # Return the error message from the API
                return f"Error: Failed to create LinkedIn post with both URN formats. Status: {response.status_code}, Response: {response.text}"

    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        return f"Error: Failed to connect to LinkedIn API: {str(e)}"

# Example usage function for testing
def test_linkedin_post():
    # This function can be used to test the LinkedIn post tool
    test_text = f"Test LinkedIn profile post from MCP Server - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = linkedin_post_tool(test_text)
    print(result)

if __name__ == "__main__":
    test_linkedin_post()