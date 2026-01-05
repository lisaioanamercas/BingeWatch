"""
Web scrapers for fetching episode data.
"""

from .base_scraper import BaseScraper
from .imdb_scraper import IMDBScraper
from .http_client import HTTPClient, FetchError

__all__ = ['BaseScraper', 'IMDBScraper', 'HTTPClient', 'FetchError']