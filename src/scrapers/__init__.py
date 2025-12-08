"""
Web scrapers for fetching episode data.
"""

from .base_scraper import BaseScraper
from .imdb_scraper import IMDBScraper

__all__ = ['BaseScraper', 'IMDBScraper']