"""
Video Cache - Persistent Storage for Previously Found Videos.

This module handles storing and retrieving YouTube video findings
to enable change detection (Phase 5 requirement).

THE PROBLEM:
============
When you run 'trailers' twice for the same episode:
  - First run: finds videos A, B, C
  - Second run: finds videos B, C, D, E

We want to notify ONLY about the NEW videos (D, E), not repeat B, C.

SOLUTION:
=========
Store video IDs in a JSON cache file. On each search:
1. Load previously found video IDs
2. Compare new results against cache
3. Return only NEW videos
4. Update cache with all found videos

CACHE STRUCTURE:
================
{
    "Breaking Bad|S01E04": {
        "video_ids": ["abc123", "def456"],
        "last_checked": "2024-01-15T10:30:00",
        "videos": [
            {"video_id": "abc123", "title": "...", "found_at": "..."},
            ...
        ]
    },
    ...
}

The key is "{series_name}|{episode_code}" for episode-specific searches,
or "{series_name}|general" for series-wide searches.

STORAGE LOCATION:
=================
data/video_cache.json (alongside the SQLite database)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict

from ..config.settings import DB_DIR
from ..utils.logger import get_logger
from ..scrapers.youtube_scraper import VideoResult


# Cache file path
CACHE_FILE = DB_DIR / "video_cache.json"


@dataclass
class CachedVideo:
    """
    A video entry in the cache with metadata.
    
    Attributes:
        video_id: YouTube video ID
        title: Video title (for display)
        channel_name: Channel that uploaded
        url: Full YouTube URL
        found_at: ISO timestamp when first discovered
        notified: Whether user was notified about this video
    """
    video_id: str
    title: str
    channel_name: str = "Unknown"
    url: str = ""
    found_at: str = ""
    notified: bool = False
    
    def __post_init__(self):
        """Set default found_at if not provided."""
        if not self.found_at:
            self.found_at = datetime.now().isoformat()
    
    @classmethod
    def from_video_result(cls, video: VideoResult) -> 'CachedVideo':
        """Create CachedVideo from a VideoResult."""
        return cls(
            video_id=video.video_id,
            title=video.title,
            channel_name=video.channel_name,
            url=video.url
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CachedVideo':
        """Create from dictionary (JSON deserialization)."""
        return cls(**data)


class VideoCache:
    """
    Manages persistent storage of found YouTube videos.
    
    This class provides:
    1. STORAGE: Save video findings to JSON file
    2. LOOKUP: Check if a video was previously found
    3. COMPARISON: Identify new videos vs cached ones
    4. TIMESTAMPS: Track when videos were discovered
    
    THREAD SAFETY:
    ==============
    This implementation is NOT thread-safe. For single-user CLI,
    this is fine. Would need locking for multi-threaded use.
    
    CACHE KEYS:
    ===========
    Videos are cached by search context:
    - Episode-specific: "Breaking Bad|S01E04"
    - Series-general: "Breaking Bad|general"
    
    This allows tracking separately for different search types.
    
    USAGE:
    ======
        cache = VideoCache()
        
        # Check for new videos
        new_videos = cache.get_new_videos(
            key="Breaking Bad|S01E04",
            current_videos=search_results
        )
        
        # new_videos contains only videos not previously cached
    """
    
    def __init__(self, cache_path: Optional[Path] = None):
        """
        Initialize video cache.
        
        Args:
            cache_path: Optional custom path for cache file
        """
        self.cache_path = cache_path or CACHE_FILE
        self.logger = get_logger()
        self._cache: Dict[str, Dict] = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cache from JSON file."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                self.logger.debug(f"Loaded cache with {len(self._cache)} entries")
            except json.JSONDecodeError:
                self.logger.warning("Cache file corrupted, starting fresh")
                self._cache = {}
            except Exception as e:
                self.logger.error(f"Error loading cache: {e}")
                self._cache = {}
        else:
            self._cache = {}
    
    def _save_cache(self):
        """Save cache to JSON file."""
        try:
            # Ensure directory exists
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
            self.logger.debug("Cache saved successfully")
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")
    
    def _make_key(self, series_name: str, episode_code: Optional[str] = None) -> str:
        """
        Create cache key from series name and episode code.
        
        Args:
            series_name: Name of the series
            episode_code: Episode code or None for general
            
        Returns:
            Cache key string
        """
        if episode_code:
            return f"{series_name}|{episode_code}"
        return f"{series_name}|general"
    
    def get_cached_video_ids(self, key: str) -> Set[str]:
        """
        Get set of video IDs previously found for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Set of video IDs
        """
        entry = self._cache.get(key, {})
        return set(entry.get('video_ids', []))
    
    def get_new_videos(
        self,
        series_name: str,
        episode_code: Optional[str],
        current_videos: List[VideoResult]
    ) -> List[VideoResult]:
        """
        Compare current videos against cache and return only new ones.
        
        This is the main method for change detection:
        1. Look up previously cached video IDs
        2. Filter current videos to only those not in cache
        3. Update cache with all current videos
        4. Return only the new ones
        
        Args:
            series_name: Name of the series
            episode_code: Episode code or None for general
            current_videos: Videos from current search
            
        Returns:
            List of VideoResult objects that are NEW
        """
        key = self._make_key(series_name, episode_code)
        
        # Get previously cached IDs
        cached_ids = self.get_cached_video_ids(key)
        
        # Find new videos (not in cache)
        new_videos = [v for v in current_videos if v.video_id not in cached_ids]
        
        self.logger.debug(
            f"Key '{key}': {len(current_videos)} current, "
            f"{len(cached_ids)} cached, {len(new_videos)} new"
        )
        
        # Update cache with all current videos
        self._update_cache(key, current_videos, new_videos)
        
        return new_videos
    
    def _update_cache(
        self,
        key: str,
        all_videos: List[VideoResult],
        new_videos: List[VideoResult]
    ):
        """
        Update cache with video findings.
        
        Args:
            key: Cache key
            all_videos: All videos from current search
            new_videos: Videos that are newly discovered
        """
        # Get or create entry
        entry = self._cache.get(key, {
            'video_ids': [],
            'videos': [],
            'first_checked': datetime.now().isoformat()
        })
        
        # Update timestamp
        entry['last_checked'] = datetime.now().isoformat()
        
        # Add new video IDs
        existing_ids = set(entry.get('video_ids', []))
        new_ids = [v.video_id for v in new_videos]
        entry['video_ids'] = list(existing_ids | set(v.video_id for v in all_videos))
        
        # Add detailed info for new videos
        existing_videos = entry.get('videos', [])
        for video in new_videos:
            cached = CachedVideo.from_video_result(video)
            existing_videos.append(cached.to_dict())
        entry['videos'] = existing_videos
        
        # Track count of new discoveries
        entry['new_count'] = entry.get('new_count', 0) + len(new_videos)
        entry['total_found'] = len(entry['video_ids'])
        
        # Save
        self._cache[key] = entry
        self._save_cache()
    
    def mark_notified(self, key: str, video_ids: List[str]):
        """
        Mark videos as notified (user has been informed).
        
        Args:
            key: Cache key
            video_ids: List of video IDs that were notified
        """
        entry = self._cache.get(key)
        if not entry:
            return
        
        video_id_set = set(video_ids)
        for video in entry.get('videos', []):
            if video.get('video_id') in video_id_set:
                video['notified'] = True
        
        self._save_cache()
    
    def get_all_entries(self) -> Dict[str, Dict]:
        """Return all cache entries (for debugging/display)."""
        return self._cache.copy()
    
    def clear_cache(self, key: Optional[str] = None):
        """
        Clear cache entries.
        
        Args:
            key: Specific key to clear, or None to clear all
        """
        if key:
            if key in self._cache:
                del self._cache[key]
                self.logger.info(f"Cleared cache for key: {key}")
        else:
            self._cache = {}
            self.logger.info("Cleared entire video cache")
        
        self._save_cache()
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dict with stats about cached videos
        """
        total_keys = len(self._cache)
        total_videos = sum(
            len(entry.get('video_ids', []))
            for entry in self._cache.values()
        )
        
        return {
            'total_entries': total_keys,
            'total_videos': total_videos,
            'cache_path': str(self.cache_path)
        }
