"""
HTTP Client Module for BingeWatch Web Scraping.

This module provides a robust HTTP client built entirely on Python's standard library.
It handles the complexities of web requests including:
- Proper header management to appear as a legitimate browser
- Timeout handling to prevent hanging on slow/dead servers
- Retry logic with exponential backoff for transient failures
- Comprehensive error handling with meaningful exceptions

DESIGN PHILOSOPHY:
==================
Why not just use `requests`? The project requirement specifies stdlib-only dependencies.
This forces us to use `urllib.request`, which is more verbose but equally capable.

The key insight is that web scraping is inherently unreliable:
- Servers go down temporarily
- Rate limiting kicks in intermittently  
- Network hiccups happen

Our solution: wrap all the ugly retry logic here so the scraper code stays clean.

USAGE EXAMPLE:
==============
    client = HTTPClient()
    try:
        html = client.fetch("https://www.imdb.com/title/tt0903747/episodes")
        # Process html...
    except FetchError as e:
        logger.error(f"Failed to fetch: {e}")
"""

import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from typing import Optional, Dict
from ..config.settings import USER_AGENT, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
from ..utils.logger import get_logger


class FetchError(Exception):
    """
    Custom exception for HTTP fetch failures.
    
    Why a custom exception?
    - Abstracts away the difference between URLError, HTTPError, TimeoutError
    - Allows callers to catch ONE exception type instead of many
    - Can carry additional context (status code, retry count, etc.)
    
    Attributes:
        message: Human-readable error description
        status_code: HTTP status code if applicable (None for network errors)
        original_error: The underlying exception that caused this error
    """
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 original_error: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.original_error = original_error
    
    def __str__(self):
        if self.status_code:
            return f"FetchError (HTTP {self.status_code}): {self.message}"
        return f"FetchError: {self.message}"


class HTTPClient:
    """
    HTTP client for fetching web pages with retry logic.
    
    This class encapsulates all HTTP communication logic:
    
    1. REQUEST CONSTRUCTION
       - Sets User-Agent to mimic a real browser (some sites block "Python-urllib")
       - Sets Accept-Language to get English content
       - Can accept custom headers for special cases
    
    2. RETRY STRATEGY
       - Uses exponential backoff: wait 1s, then 2s, then 4s between retries
       - Only retries on transient errors (timeout, 5xx server errors)
       - Immediately fails on permanent errors (404, 403)
    
    3. ERROR TRANSFORMATION
       - Converts low-level exceptions into descriptive FetchError
       - Logs all errors for debugging
    
    Attributes:
        logger: Logger instance for this client
        default_headers: Headers sent with every request
    """
    
    def __init__(self):
        """
        Initialize HTTP client with default configuration.
        
        The default headers are crucial for successful scraping:
        - User-Agent: Identifies us as a browser, not a bot
        - Accept-Language: Ensures we get English pages from IMDB
        - Accept: Tells server we want HTML (not JSON/XML)
        - Connection: keep-alive allows TCP connection reuse
        """
        self.logger = get_logger()
        
        # These headers make our requests look like a legitimate browser
        # Without them, some sites (including IMDB) may block or redirect us
        self.default_headers: Dict[str, str] = {
            'User-Agent': USER_AGENT,
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Connection': 'keep-alive',
        }
    
    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """
        Fetch a URL and return its content as a string.
        
        This is the main public method. It handles:
        1. Building the request with proper headers
        2. Executing with retry logic
        3. Decoding the response to UTF-8 string
        
        Args:
            url: The URL to fetch
            headers: Optional additional headers (merged with defaults)
        
        Returns:
            str: The page content as a UTF-8 string
        
        Raises:
            FetchError: If the fetch fails after all retries
        
        Example:
            >>> client = HTTPClient()
            >>> html = client.fetch("https://www.imdb.com/title/tt0903747/episodes")
            >>> "Breaking Bad" in html
            True
        """
        # Merge default headers with any custom headers provided
        # Custom headers override defaults if there's a conflict
        request_headers = {**self.default_headers}
        if headers:
            request_headers.update(headers)
        
        # Create the Request object
        # urllib.request.Request is the object-oriented way to build HTTP requests
        request = Request(url, headers=request_headers)
        
        self.logger.debug(f"Fetching URL: {url}")
        
        # Attempt the fetch with retries
        return self._fetch_with_retry(request)
    
    def _fetch_with_retry(self, request: Request) -> str:
        """
        Execute HTTP request with exponential backoff retry logic.
        
        EXPONENTIAL BACKOFF EXPLAINED:
        ==============================
        If a server is overloaded, hammering it with rapid retries makes things worse.
        Instead, we wait progressively longer between attempts:
        
        Attempt 1: Immediate
        Attempt 2: Wait 1 second  (RETRY_DELAY * 2^0)
        Attempt 3: Wait 2 seconds (RETRY_DELAY * 2^1)
        Attempt 4: Wait 4 seconds (RETRY_DELAY * 2^2)
        ...and so on
        
        This gives transient problems time to resolve while being respectful to servers.
        
        WHICH ERRORS ARE RETRYABLE?
        ===========================
        - Timeout: Server might be temporarily slow
        - 5xx errors: Server-side problems that might resolve
        - URLError (network): Temporary network glitch
        
        NOT RETRYABLE (fail immediately):
        - 404: Page doesn't exist
        - 403: We're blocked (retrying won't help)
        - 4xx generally: Client error, our problem
        
        Args:
            request: The prepared Request object
            
        Returns:
            str: Page content
            
        Raises:
            FetchError: After all retries exhausted or on non-retryable error
        """
        last_error = None
        
        for attempt in range(MAX_RETRIES):
            try:
                # urlopen sends the request and returns a response object
                # timeout prevents hanging forever on unresponsive servers
                with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    # Read the raw bytes from the response
                    raw_content = response.read()
                    
                    # Decode to string using the charset from headers, or default to UTF-8
                    # IMDB uses UTF-8, but this handles other encodings gracefully
                    charset = response.headers.get_content_charset() or 'utf-8'
                    content = raw_content.decode(charset)
                    
                    self.logger.debug(f"Successfully fetched {len(content)} bytes")
                    return content
            
            except HTTPError as e:
                # HTTPError means we got a response, but it's an error status
                # HTTP status codes: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status
                
                last_error = e
                
                # 4xx errors are CLIENT errors - retrying won't help
                if 400 <= e.code < 500:
                    error_messages = {
                        403: "Access forbidden. IMDB may be blocking requests.",
                        404: "Page not found. Check if the IMDB ID is correct.",
                        429: "Too many requests. Rate limited by IMDB.",
                    }
                    message = error_messages.get(e.code, f"Client error: {e.reason}")
                    self.logger.error(f"HTTP {e.code} for {request.full_url}: {message}")
                    raise FetchError(message, status_code=e.code, original_error=e)
                
                # 5xx errors are SERVER errors - might be transient, worth retrying
                self.logger.warning(
                    f"Server error (HTTP {e.code}) on attempt {attempt + 1}/{MAX_RETRIES}"
                )
            
            except URLError as e:
                # URLError means we couldn't even connect to the server
                # Common causes: DNS failure, network down, server refusing connections
                last_error = e
                self.logger.warning(
                    f"Network error on attempt {attempt + 1}/{MAX_RETRIES}: {e.reason}"
                )
            
            except TimeoutError:
                # Request took too long - server might be overloaded
                last_error = TimeoutError("Request timed out")
                self.logger.warning(
                    f"Timeout on attempt {attempt + 1}/{MAX_RETRIES}"
                )
            
            except Exception as e:
                # Catch-all for unexpected errors (encoding issues, etc.)
                last_error = e
                self.logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            
            # If we get here, the attempt failed but might be retryable
            if attempt < MAX_RETRIES - 1:
                # Calculate wait time with exponential backoff
                # 2^0 = 1, 2^1 = 2, 2^2 = 4, etc.
                wait_time = RETRY_DELAY * (2 ** attempt)
                self.logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        # All retries exhausted - give up and raise
        self.logger.error(f"All {MAX_RETRIES} fetch attempts failed for {request.full_url}")
        raise FetchError(
            f"Failed to fetch after {MAX_RETRIES} attempts",
            original_error=last_error
        )
