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

def x_post_tool(text: str, images: Optional[List[str]] = None) -> str:
    """
    Posts to X (formerly Twitter) using the X API with Bearer Token for authentication.

    Args:
        text: The text content for the X post (tweet)
        images: Optional list of image URLs to include in the post

    Returns:
        A string indicating the success or failure of the post
    """
    # Get the access tokens from environment variables
    bearer_token = os.getenv('X_BEARER_TOKEN')

    if not bearer_token:
        return "Error: Missing X Bearer Token. Please set X_BEARER_TOKEN in your .env file."

    # X API endpoint for posting tweets
    url = "https://api.twitter.com/2/tweets"

    # Set up the headers with the bearer token for authentication
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }

    # Prepare the payload for the tweet
    payload = {
        "text": text
    }

    # If images are provided, we'll handle them differently
    if images and len(images) > 0:
        # For now, just add a note about images - proper image handling requires multiple API calls
        payload["text"] += f"\n\nNote: {len(images)} image(s) were requested but require additional processing."

    try:
        # Make the API request to post to X
        response = requests.post(url, headers=headers, json=payload)

        # Check if the request was successful
        if response.status_code in [200, 201]:
            response_data = response.json()
            tweet_id = response_data.get("data", {}).get("id", "unknown")
            return f"Success: X (Twitter) post created successfully with ID {tweet_id}. Post: {text[:100]}..."
        else:
            # Check if it's the authentication type error
            error_message = response.text

            # If it's the unsupported authentication error, the issue might be that this specific endpoint requires OAuth 1.0a
            if "Unsupported Authentication" in error_message or "oauth1" in error_message.lower():
                # Fallback to OAuth 1.0a with the credentials we have
                return x_post_tool_oauth1(text, images)
            else:
                return f"Error: Failed to create X (Twitter) post. Status Code: {response.status_code}, Response: {error_message}"

    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        return f"Error: Failed to connect to X API: {str(e)}"

def x_post_tool_oauth1(text: str, images: Optional[List[str]] = None) -> str:
    """
    Posts to X using OAuth 1.0a as fallback
    """
    # Get the access tokens from environment variables
    api_key = os.getenv('X_API_KEY')
    api_secret = os.getenv('X_API_SECRET')
    access_token = os.getenv('X_ACCESS_TOKEN')
    access_token_secret = os.getenv('X_ACCESS_SECRET')

    if not all([api_key, api_secret, access_token, access_token_secret]):
        return "Error: Missing X API OAuth 1.0a credentials. Please set X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, and X_ACCESS_SECRET in your .env file."

    # This is a simplified approach using requests-oauthlib concept manually
    import time
    import random
    import string
    import hmac
    import hashlib
    import base64
    from urllib.parse import quote

    # X API endpoint for posting tweets
    url = "https://api.twitter.com/2/tweets"

    # OAuth parameters
    oauth_params = {
        'oauth_consumer_key': api_key,
        'oauth_nonce': ''.join(random.choices(string.ascii_letters + string.digits, k=32)),
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str(int(time.time())),
        'oauth_token': access_token,
        'oauth_version': '1.0'
    }

    # Prepare the payload for the tweet
    tweet_payload = {
        "text": text
    }

    # If images are provided, we'll handle them differently
    if images and len(images) > 0:
        # For now, just add a note about images - proper image handling requires multiple API calls
        tweet_payload["text"] += f"\n\nNote: {len(images)} image(s) were requested but require additional processing."

    # Create signature base string - includes all parameters (including the tweet content)
    all_params = {**oauth_params}
    # For POST body parameters, they need to be included in the signature in certain cases
    base_parts = [
        "POST",
        quote(url, safe='~'),
        quote('&'.join([f'{quote(k, safe="~")}={quote(str(v), safe="~")}' for k, v in sorted(all_params.items())]), safe='~')
    ]
    base_string = '&'.join(base_parts)

    # Create signature key
    signature_key = f"{quote(api_secret, safe='~')}&{quote(access_token_secret, safe='~')}"

    # Create signature
    signature = base64.b64encode(hmac.new(
        signature_key.encode('utf-8'),
        base_string.encode('utf-8'),
        hashlib.sha1
    ).digest()).decode('utf-8')

    # Add signature to OAuth params
    oauth_params['oauth_signature'] = signature

    # Create Authorization header
    auth_header = 'OAuth ' + ', '.join([
        f'{k}="{quote(str(v), safe="~")}"' for k, v in sorted(oauth_params.items())
    ])

    # Set up the headers
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/json"
    }

    try:
        # Make the API request to post to X
        response = requests.post(url, headers=headers, json=tweet_payload)

        # Check if the request was successful
        if response.status_code in [200, 201]:
            response_data = response.json()
            tweet_id = response_data.get("data", {}).get("id", "unknown")
            return f"Success: X (Twitter) post created successfully with ID {tweet_id}. Post: {text[:100]}..."
        else:
            # Return the error message from the API
            error_message = response.text
            return f"Error: Failed to create X (Twitter) post with OAuth 1.0a. Status Code: {response.status_code}, Response: {error_message}"

    except requests.exceptions.RequestException as e:
        # Handle any request exceptions
        return f"Error: Failed to connect to X API: {str(e)}"

# Example usage function for testing
def test_x_post():
    # This function can be used to test the X post tool
    test_text = f"Test X (Twitter) post from AI Employee Vault - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    result = x_post_tool(test_text)
    print(result)

if __name__ == "__main__":
    test_x_post()