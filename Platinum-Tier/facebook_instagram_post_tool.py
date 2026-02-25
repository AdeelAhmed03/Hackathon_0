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

def facebook_post_tool(text: str, images: Optional[List[str]] = None) -> str:
    """
    Posts to Facebook page using the Facebook Graph API.

    Args:
        text: The text content for the Facebook post
        images: Optional list of image URLs to include in the post

    Returns:
        A string indicating the success or failure of the post
    """
    # Get the access token and page ID from environment variables
    access_token = os.getenv('FB_ACCESS_TOKEN')
    page_id = os.getenv('FB_PAGE_ID')

    if not access_token:
        return "Error: Facebook access token not found. Please set FB_ACCESS_TOKEN in your .env file."

    if not page_id:
        return "Error: Facebook page ID not found. Please set FB_PAGE_ID in your .env file."

    # Facebook Graph API endpoint for posting to a page
    url = f"https://graph.facebook.com/v18.0/{page_id}/feed"

    # Set up the payload for the post
    payload = {
        'message': text,
        'access_token': access_token
    }

    # If images are provided, we'll handle them differently (FB requires separate image upload)
    if images and len(images) > 0:
        # For now, just add a note about images - proper image handling requires multiple API calls
        payload['message'] += f"\n\nNote: {len(images)} image(s) were requested but require additional processing."

    try:
        # Make the API request to post to Facebook page
        response = requests.post(url, data=payload)

        # Check if the request was successful
        if response.status_code in [200, 201]:
            response_data = response.json()
            post_id = response_data.get("id", "unknown")
            return f"Success: Facebook post created successfully with ID {post_id}. Post: {text[:100]}..."
        else:
            # Return the error message from the API
            error_message = response.text
            return f"Error: Failed to create Facebook post. Status Code: {response.status_code}, Response: {error_message}"

    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        return f"Error: Failed to connect to Facebook API: {str(e)}"

def instagram_post_tool(text: str, images: Optional[List[str]] = None) -> str:
    """
    Posts to Instagram business account using the Instagram Graph API.

    Args:
        text: The text content for the Instagram post
        images: Optional list of image URLs to include in the post

    Returns:
        A string indicating the success or failure of the post
    """
    # Get the access token and Instagram business account ID from environment variables
    access_token = os.getenv('FB_ACCESS_TOKEN')  # Using the same token as Facebook
    ig_account_id = os.getenv('IG_BUSINESS_ACCOUNT_ID')

    if not access_token:
        return "Error: Instagram access token not found. Please set FB_ACCESS_TOKEN in your .env file."

    if not ig_account_id:
        return "Error: Instagram business account ID not found. Please set IG_BUSINESS_ACCOUNT_ID in your .env file."

    # First, create the media container (for image posts, this would require additional steps)
    # For text-only posts, we can post directly
    url = f"https://graph.facebook.com/v18.0/{ig_account_id}/media"

    # Set up the payload for the post
    payload = {
        'caption': text,
        'access_token': access_token
    }

    # For now, we'll handle simple text posts
    # Note: For actual image posting, we'd need multiple API calls to upload and publish
    if images and len(images) > 0:
        # For now, just add a note about images
        payload['caption'] += f"\n\nNote: {len(images)} image(s) were requested but require additional processing."

    try:
        # Create the media container
        response = requests.post(url, data=payload)

        if response.status_code in [200, 201]:
            response_data = response.json()
            container_id = response_data.get("id")

            # Now publish the media container
            publish_url = f"https://graph.facebook.com/v18.0/{ig_account_id}/media_publish"
            publish_payload = {
                'creation_id': container_id,
                'access_token': access_token
            }

            publish_response = requests.post(publish_url, data=publish_payload)

            if publish_response.status_code in [200, 201]:
                publish_data = publish_response.json()
                post_id = publish_data.get("id", "unknown")
                return f"Success: Instagram post created successfully with ID {post_id}. Post: {text[:100]}..."
            else:
                publish_error = publish_response.text
                return f"Error: Failed to publish Instagram post. Status: {publish_response.status_code}, Response: {publish_error}"
        else:
            # Return the error message from the API
            error_message = response.text
            return f"Error: Failed to create Instagram media container. Status Code: {response.status_code}, Response: {error_message}"

    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        return f"Error: Failed to connect to Instagram API: {str(e)}"

# Example usage function for testing
def test_facebook_post():
    # This function can be used to test the Facebook post tool
    test_text = f"Test Facebook page post from AI Employee Vault - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = facebook_post_tool(test_text)
    print(result)

def test_instagram_post():
    # This function can be used to test the Instagram post tool
    test_text = f"Test Instagram business post from AI Employee Vault - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = instagram_post_tool(test_text)
    print(result)

if __name__ == "__main__":
    test_facebook_post()
    test_instagram_post()