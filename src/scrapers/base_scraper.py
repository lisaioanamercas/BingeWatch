"""
Base scraper interface.
Abstract base class for all web scrapers.
"""

from abc import ABC, abstractmethod
from typing import List
from ..database.models import Episode
from ..utils.logger import get_logger


class BaseScraper(ABC):
    """
    Abstract base class for scrapers.
    Defines interface for episode scrapers.
    """
    
    def __init__(self):
        """Initialize scraper."""
        self.logger = get_logger()
    
    @abstractmethod
    def get_latest_episodes(self, imdb_id: str) -> List[Episode]:
        """
        Get latest episodes for a series.
        
        Args:
            imdb_id: IMDB ID of series
            
        Returns:
            List of Episode objects
        """
        pass
    
    @abstractmethod
    def check_new_episodes(self, imdb_id: str, last_episode: str) -> List[str]:
        """
        Check for new episodes since last watched.
        
        Args:
            imdb_id: IMDB ID of series
            last_episode: Last watched episode code (e.g., S01E05)
            
        Returns:
            List of new episode codes
        """
        pass