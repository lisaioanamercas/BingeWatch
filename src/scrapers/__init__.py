"""
Web scrapers for fetching episode and video data.
"""

from .base_scraper import BaseScraper
from .imdb_scraper import IMDBScraper, SearchResult
from .http_client import HTTPClient, FetchError
from .youtube_scraper import YouTubeScraper, VideoResult

__all__ = ['BaseScraper', 'IMDBScraper', 'SearchResult', 'HTTPClient', 'FetchError', 'YouTubeScraper', 'VideoResult']