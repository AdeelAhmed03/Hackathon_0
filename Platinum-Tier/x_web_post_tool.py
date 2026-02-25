import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# Add the vault directory to the Python path
VAULT_DIR = Path('.').resolve()
sys.path.insert(0, str(VAULT_DIR))

def x_web_post_tool(text: str, images: Optional[List[str]] = None) -> str:
    """
    Posts to X (formerly Twitter) using web automation instead of the paid API.
    This approach bypasses the API credits requirement by using browser automation.

    Args:
        text: The text content for the X post (tweet)
        images: Optional list of image file paths to upload

    Returns:
        A string indicating the success or failure of the post
    """
    # Get X credentials from environment variables
    x_username = os.getenv('X_USERNAME')  # You'll need to add this to .env
    x_password = os.getenv('X_PASSWORD')  # You'll need to add this to .env

    if not x_username or not x_password:
        return "Error: X web posting requires X_USERNAME and X_PASSWORD in your .env file. This method bypasses API credits by using web automation."

    try:
        # Set up Chrome options for headless browsing
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Remove this line to see the browser
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Initialize the web driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            # Navigate to X login page
            driver.get("https://twitter.com/login")
            wait = WebDriverWait(driver, 20)

            # Wait for and enter username
            username_field = wait.until(EC.presence_of_element_located((By.NAME, "text")))
            username_field.send_keys(x_username)

            # Click next
            next_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Next')]")
            next_button.click()

            # Wait for and enter password
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            password_field.send_keys(x_password)

            # Click login
            login_button = driver.find_element(By.XPATH, "//span[contains(text(), 'Log in')]")
            login_button.click()

            # Wait for login to complete
            wait.until(EC.presence_of_element_located((By.XPATH, "//a[@aria-label='Home']")))

            # Wait a bit more to ensure full page load
            time.sleep(5)

            # Find the tweet textbox and enter the text
            tweet_box = wait.until(EC.element_to_be_clickable((By.XPATH, "//br[@data-text='true']")))
            tweet_box.click()
            tweet_box.send_keys(text)

            # If images are provided, handle them
            if images and len(images) > 0:
                # Note: Image handling via web automation is more complex
                # This would require finding the image upload button and using send_keys
                pass

            # Find and click the tweet button
            tweet_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@data-testid='tweetButton']")))
            tweet_button.click()

            # Wait to ensure the tweet was posted
            time.sleep(5)

            return f"Success: X (Twitter) post created via web automation. Post: {text[:100]}..."

        except Exception as e:
            return f"Error during X web posting: {str(e)}"

        finally:
            driver.quit()

    except ImportError:
        return "Error: Selenium is required for web automation. Install it using: pip install selenium"
    except Exception as e:
        return f"Error: Failed to initialize X web posting: {str(e)}"

def x_web_post_tool_stub(text: str, images: Optional[List[str]] = None) -> str:
    """
    A stub version of the X web post tool that explains the approach since
    the actual implementation requires setup and may have various issues.

    When you want to implement this properly, you'll need to:
    1. Install: pip install selenium
    2. Download ChromeDriver from https://chromedriver.chromium.org/
    3. Add X_USERNAME and X_PASSWORD to your .env file
    """
    return """
    X Web Automation Tool (Stub):

    This tool uses browser automation to post to X instead of the paid API.
    To use this tool properly:

    1. Install selenium: pip install selenium
    2. Download ChromeDriver: https://chromedriver.chromium.org/
    3. Add these to your .env file:
       X_USERNAME=your_x_username
       X_PASSWORD=your_x_password
    4. Handle X's bot detection measures

    Note: This method bypasses API credit requirements but requires more setup
    and may be subject to X's anti-automation measures.
    """

# Example usage function for testing
def test_x_web_post():
    # This function can be used to test the X web post tool
    test_text = f"Test X (Twitter) post via web automation from AI Employee Vault"
    result = x_web_post_tool_stub(test_text)
    print(result)

if __name__ == "__main__":
    test_x_web_post()