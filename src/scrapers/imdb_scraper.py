"""
IMDB scraper implementation.
Scrapes episode data from IMDB.
"""

import re
from typing import List

from .base_scraper import BaseScraper
from ..database.models import Episode
from ..config.settings import USER_AGENT


class IMDBScraper(BaseScraper):
    """Scraper for IMDB episode data."""
    
    def get_latest_episodes(self, imdb_id: str) -> List[Episode]:
        """
        Get latest episodes for a series from IMDB.
        
        Args:
            imdb_id: IMDB ID of series
            
        Returns:
            List of Episode objects
        """
        # Placeholder implementation
        # In a real implementation, you would scrape IMDB here
        self.logger.warning("IMDB scraping not fully implemented yet")
        return []
    
    def check_new_episodes(self, imdb_id: str, last_episode: str) -> List[str]:
        """
        Check for new episodes since last watched.
        
        Args:
            imdb_id: IMDB ID of series
            last_episode: Last watched episode (e.g., S01E05)
            
        Returns:
            List of new episode codes
        """
        # Placeholder implementation
        # Parse last episode
        match = re.match(r'S(\d+)E(\d+)', last_episode)
        if not match:
            return []
        
        # In a real implementation, scrape IMDB and compare
        self.logger.info(f"Checking episodes for {imdb_id} after {last_episode}")
        return []  # Return empty for now