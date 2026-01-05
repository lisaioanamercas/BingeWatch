"""
Notification Service - Change Detection and User Alerts.

This module implements the notification workflow for Phase 5:
1. Check for new YouTube videos across all tracked series
2. Compare against previously found videos (via VideoCache)
3. Generate user-friendly notifications for NEW discoveries
4. Log all findings with timestamps

THE WORKFLOW:
=============
User runs 'check' command:
    → For each series with new episodes
        → Search YouTube for trailers
        → Compare against cache
        → Collect NEW videos only
    → Display consolidated notification
    → Update cache

NOTIFICATION PHILOSOPHY:
========================
The goal is to avoid "notification fatigue":
- Only notify about NEW content, not repeated findings
- Aggregate notifications (one summary, not one per video)
- Allow silent check (cache update without output)

LOGGING:
========
All discoveries are logged to the standard log file:
- Timestamp of check
- Which series/episodes were checked
- How many new videos found
- Video IDs for debugging

This creates an audit trail for troubleshooting.
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from ..database.db_manager import DBManager
from ..scrapers.youtube_scraper import YouTubeScraper, VideoResult
from ..scrapers.imdb_scraper import IMDBScraper
from ..services.video_cache import VideoCache
from ..utils.logger import get_logger


@dataclass
class Notification:
    """
    Represents a notification about new video discoveries.
    
    Attributes:
        series_name: Name of the series
        episode_code: Episode code (or 'general')
        new_videos: List of newly discovered videos
        timestamp: When the discovery was made
    """
    series_name: str
    episode_code: str
    new_videos: List[VideoResult]
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    @property
    def count(self) -> int:
        """Number of new videos."""
        return len(self.new_videos)
    
    def __str__(self) -> str:
        """Human-readable notification."""
        if self.episode_code == 'general':
            return f"🔔 {self.series_name}: {self.count} new video(s) found"
        return f"🔔 {self.series_name} {self.episode_code}: {self.count} new video(s) found"


class NotificationService:
    """
    Service for checking and generating video notifications.
    
    This service orchestrates the full notification workflow:
    1. Get list of series to check
    2. For each series, get new episodes from IMDB
    3. For each episode, search YouTube for videos
    4. Compare against cache to find NEW videos
    5. Aggregate and return notifications
    
    USAGE:
    ======
        service = NotificationService(db_manager)
        
        # Check all series for new videos
        notifications = service.check_all()
        
        for notif in notifications:
            print(notif)
            for video in notif.new_videos:
                print(f"  - {video.title}")
    
    RATE LIMITING:
    ==============
    This can make many YouTube requests (one per episode).
    Consider:
    - Limiting to top N priority episodes
    - Adding delays between requests
    - Caching IMDB results too
    """
    
    def __init__(
        self,
        db_manager: DBManager,
        youtube_scraper: Optional[YouTubeScraper] = None,
        imdb_scraper: Optional[IMDBScraper] = None,
        video_cache: Optional[VideoCache] = None
    ):
        """
        Initialize notification service.
        
        Args:
            db_manager: Database manager for series data
            youtube_scraper: Optional YouTube scraper instance
            imdb_scraper: Optional IMDB scraper instance
            video_cache: Optional video cache instance
        """
        self.db_manager = db_manager
        self.youtube = youtube_scraper or YouTubeScraper()
        self.imdb = imdb_scraper or IMDBScraper()
        self.cache = video_cache or VideoCache()
        self.logger = get_logger()
    
    def check_all(
        self,
        include_snoozed: bool = False,
        max_episodes_per_series: int = 3,
        min_score: Optional[int] = None
    ) -> List[Notification]:
        """
        Check all series for new YouTube videos.
        
        This is the main entry point for the notification workflow.
        
        Args:
            include_snoozed: Whether to check snoozed series
            max_episodes_per_series: Max episodes to check per series
            min_score: Minimum series score to check
            
        Returns:
            List of Notification objects for series with new videos
        """
        self.logger.info("Starting notification check for all series...")
        
        notifications: List[Notification] = []
        
        # Get all series
        series_list = self.db_manager.get_all_series(include_snoozed=include_snoozed)
        
        if min_score:
            series_list = [s for s in series_list if s.score >= min_score]
        
        self.logger.info(f"Checking {len(series_list)} series for new videos")
        
        for series in series_list:
            try:
                # Get new episodes for this series
                new_episodes = self.imdb.get_new_episodes(
                    series.imdb_id,
                    series.last_episode
                )
                
                # Limit episodes to check
                episodes_to_check = new_episodes[:max_episodes_per_series]
                
                if not episodes_to_check:
                    continue
                
                # Check each episode for new videos
                for episode in episodes_to_check:
                    notif = self._check_episode(
                        series.name,
                        episode.episode_code,
                        episode.title
                    )
                    if notif and notif.count > 0:
                        notifications.append(notif)
                
                # Also check for general series trailers
                general_notif = self._check_series_general(series.name)
                if general_notif and general_notif.count > 0:
                    notifications.append(general_notif)
            
            except Exception as e:
                self.logger.error(f"Error checking {series.name}: {e}")
                continue
        
        # Log summary
        total_new = sum(n.count for n in notifications)
        self.logger.info(
            f"Notification check complete: {total_new} new videos "
            f"across {len(notifications)} items"
        )
        
        return notifications
    
    def check_series(
        self,
        imdb_id: str,
        max_episodes: int = 5
    ) -> List[Notification]:
        """
        Check a specific series for new videos.
        
        Args:
            imdb_id: IMDB ID of the series
            max_episodes: Maximum episodes to check
            
        Returns:
            List of Notifications for this series
        """
        series = self.db_manager.get_series(imdb_id)
        if not series:
            self.logger.warning(f"Series {imdb_id} not found")
            return []
        
        notifications: List[Notification] = []
        
        # Get new episodes
        new_episodes = self.imdb.get_new_episodes(
            series.imdb_id,
            series.last_episode
        )
        
        for episode in new_episodes[:max_episodes]:
            notif = self._check_episode(
                series.name,
                episode.episode_code,
                episode.title
            )
            if notif and notif.count > 0:
                notifications.append(notif)
        
        return notifications
    
    def _check_episode(
        self,
        series_name: str,
        episode_code: str,
        episode_title: Optional[str] = None
    ) -> Optional[Notification]:
        """
        Check for new YouTube videos for a specific episode.
        
        Args:
            series_name: Name of the series
            episode_code: Episode code (e.g., S01E04)
            episode_title: Optional episode title
            
        Returns:
            Notification if new videos found, None otherwise
        """
        self.logger.debug(f"Checking YouTube for {series_name} {episode_code}")
        
        try:
            # Search YouTube
            all_videos = self.youtube.search_episode_videos(
                series_name=series_name,
                episode_code=episode_code,
                episode_title=episode_title,
                max_results=10  # Get more to compare against cache
            )
            
            if not all_videos:
                return None
            
            # Compare against cache
            new_videos = self.cache.get_new_videos(
                series_name=series_name,
                episode_code=episode_code,
                current_videos=all_videos
            )
            
            if new_videos:
                self.logger.info(
                    f"Found {len(new_videos)} new videos for "
                    f"{series_name} {episode_code}"
                )
                return Notification(
                    series_name=series_name,
                    episode_code=episode_code,
                    new_videos=new_videos
                )
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error checking {series_name} {episode_code}: {e}")
            return None
    
    def _check_series_general(self, series_name: str) -> Optional[Notification]:
        """
        Check for new general series trailers.
        
        Args:
            series_name: Name of the series
            
        Returns:
            Notification if new videos found
        """
        try:
            all_videos = self.youtube.search_series_trailers(
                series_name=series_name,
                max_results=5
            )
            
            if not all_videos:
                return None
            
            new_videos = self.cache.get_new_videos(
                series_name=series_name,
                episode_code=None,  # General means no specific episode
                current_videos=all_videos
            )
            
            if new_videos:
                return Notification(
                    series_name=series_name,
                    episode_code='general',
                    new_videos=new_videos
                )
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error checking general trailers for {series_name}: {e}")
            return None
    
    def get_cache_stats(self) -> dict:
        """Get statistics about the video cache."""
        return self.cache.get_stats()
    
    def clear_cache(self, series_name: Optional[str] = None):
        """
        Clear notification cache.
        
        Args:
            series_name: Specific series to clear, or None for all
        """
        if series_name:
            # Clear all keys for this series
            for key in list(self.cache.get_all_entries().keys()):
                if key.startswith(f"{series_name}|"):
                    self.cache.clear_cache(key)
        else:
            self.cache.clear_cache()
