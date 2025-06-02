import requests
from requests.exceptions import RequestException, Timeout, HTTPError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry # Import Retry

from src.logger_setup import setup_logging
from src.config_loader import get_config # For retry settings

logger = setup_logging()
config = get_config()

DEFAULT_TIMEOUT_SECONDS = 30  # Default timeout for requests
DEFAULT_USER_AGENT = "WebsiteMonitor/1.0 (+http://yourprojecturl.com/bot.html)" # Be a good internet citizen

def _get_retry_session(total_retries=None, backoff_factor=None, status_forcelist=None):
    """Creates a requests Session with retry capabilities."""
    session = requests.Session()
    
    # Get retry parameters from config, with defaults
    cfg_total_retries = config.get('fetch_retry_total', 3)
    cfg_backoff_factor = config.get('fetch_retry_backoff_factor', 0.3) # e.g., 0s, 0.6s, 1.2s
    cfg_status_forcelist = config.get('fetch_retry_status_forcelist', [500, 502, 503, 504])

    # Allow override by function parameters if provided
    total_retries = total_retries if total_retries is not None else cfg_total_retries
    backoff_factor = backoff_factor if backoff_factor is not None else cfg_backoff_factor
    status_forcelist = status_forcelist if status_forcelist is not None else cfg_status_forcelist

    retry_strategy = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=["HEAD", "GET", "OPTIONS"] # Retry only for idempotent methods
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_website_content(url: str, timeout: int = DEFAULT_TIMEOUT_SECONDS, user_agent: str = None):
    """
    Fetches the HTML content of a given URL, with retry logic.

    Args:
        url (str): The URL to fetch.
        timeout (int): Timeout in seconds for the request (per attempt).
        user_agent (str, optional): The User-Agent string to use. Defaults to DEFAULT_USER_AGENT.

    Returns:
        tuple: (status_code, content_type, html_content, error_message)
               html_content is the decoded text content if successful, None otherwise.
               error_message contains details if an error occurred.
    """
    headers = {
        "User-Agent": user_agent if user_agent else DEFAULT_USER_AGENT
    }
    
    logger.debug(f"Attempting to fetch URL: {url} with timeout: {timeout}s and retry logic.")
    session = _get_retry_session()

    try:
        # Use the session for the request
        response = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX) after retries

        html_content = response.text
        content_type = response.headers.get('Content-Type', '')
        
        logger.info(f"Successfully fetched URL: {url}. Status: {response.status_code}. Content-Type: {content_type}")
        return response.status_code, content_type, html_content, None

    except Timeout:
        # This timeout is per attempt. If all retries timeout, this might be the final exception.
        error_msg = f"Request timed out after {timeout} seconds (and potential retries) for URL: {url}"
        logger.error(error_msg)
        return None, None, None, error_msg
    except HTTPError as e:
        # This error is raised if retries are exhausted for statuses in status_forcelist, or for other 4xx/5xx errors not retried.
        error_msg = f"HTTP error occurred after retries: {e.response.status_code} {e.response.reason} for URL: {url}"
        logger.error(error_msg)
        return e.response.status_code, e.response.headers.get('Content-Type', ''), e.response.text, error_msg
    except RequestException as e:
        # Catches other general request exceptions (e.g., connection errors) that might occur after retries.
        error_msg = f"An error occurred during request (after retries) to {url}: {e}"
        logger.error(error_msg)
        return None, None, None, error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred while fetching {url}: {e}"
        logger.error(error_msg, exc_info=True)
        return None, None, None, error_msg

if __name__ == '__main__':
    # Example Usage
    test_urls = [
        "https://google.com",
        "https://example.com",
        "http://httpstat.us/404", # Known 404
        "http://httpstat.us/500", # Known 500
        "http://nonexistentdomainthatshouldfaildns.invalid/", # DNS failure
        "https://jigsaw.w3.org/HTTP/ChunkedScript" # Chunked encoding test (handled by requests)
        # "http://localhost:1234/timeout" # For local timeout test, run a simple server: python -m http.server 1234 and make a route that sleeps
    ]

    # To test encoding, you might need a specific site or local setup.
    # For example, a page served with `Content-Type: text/html; charset=Shift_JIS`
    # test_urls.append("URL_WITH_SPECIFIC_ENCODING") 

    for t_url in test_urls:
        print(f"\n--- Testing URL: {t_url} ---")
        status, c_type, content, error = fetch_website_content(t_url, timeout=10)
        
        if error:
            print(f"Error: {error}")
            if status: # If we have a status code even on error (like HTTPError)
                print(f"Status Code: {status}")
            if content: # Some error pages might have content
                print(f"Error Page Content (first 100 chars): {content[:100]}...")
        elif content:
            print(f"Status Code: {status}")
            print(f"Content-Type: {c_type}")
            print(f"Successfully fetched content (first 200 chars):\n{content[:200]}...")
        else:
            print("No content and no error message (should not happen if error is None).")

    # Example of a timeout test (requires a server that will delay response)
    # logger.info("\n--- Testing Timeout (expects error) ---")
    # You can set up a local server that sleeps for longer than the timeout.
    # E.g., using Flask: from flask import Flask, Response; import time; app = Flask(__name__); 
    # @app.route('/slow') def slow_response(): time.sleep(10); return Response("finally here", mimetype='text/plain');
    # if __name__ == '__main__': app.run(port=5001)
    # status, c_type, content, error = fetch_website_content("http://localhost:5001/slow", timeout=2)
    # if error and "timed out" in error:
    #     logger.info(f"Timeout test successful: {error}")
    # else:
    #     logger.error(f"Timeout test failed. Status: {status}, Error: {error}") 