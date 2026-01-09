"""
Video Cache - Stocare persistenta pentru videoclipurile gasite.

DESIGN PATTERNS:
================
1. REPOSITORY PATTERN - Abstractizeaza stocarea/regasirea datelor
2. DATA TRANSFER OBJECT (DTO) - CachedVideo transfera date intre straturi
3. LAZY INITIALIZATION - Cache-ul se incarca la primul acces
4. SINGLETON BEHAVIOR - O singura instanta per cache file

RESPONSABILITATI:
=================
- Stocheaza ID-urile videoclipurilor gasite anterior
- Compara rezultatele noi cu cache-ul existent
- Returneaza doar videoclipuri NOI
- Gestioneaza TTL si curatarea automata

STRUCTURA CACHE:
================
{
    "Breaking Bad|S01E04": {
        "video_ids": ["abc123", "def456"],
        "last_checked": "2024-01-15T10:30:00",
        "videos": [...]
    }
}

Cheia: "{nume_serie}|{cod_episod}" sau "{nume_serie}|general"

SMART CACHING:
==============
- TTL (Time-To-Live): Intrarile mai vechi de CACHE_TTL_DAYS sunt stale
- Auto-pruning: Curatare automata a intrarilor vechi
- Age tracking: Urmareste cand au fost verificate intrarile
"""


import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, asdict

from ..config.settings import DB_DIR, CACHE_TTL_DAYS, CACHE_AUTO_PRUNE, CACHE_PRUNE_THRESHOLD
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
    
    # ==========================================================================
    # Smart Cache Methods (TTL, Pruning, Age Tracking)
    # ==========================================================================
    
    def is_entry_stale(self, key: str, ttl_days: Optional[int] = None) -> bool:
        """
        Check if a cache entry is stale (older than TTL).
        
        Args:
            key: Cache key to check
            ttl_days: Days before entry is stale (default from settings)
            
        Returns:
            True if entry is stale or doesn't exist
        """
        ttl = ttl_days if ttl_days is not None else CACHE_TTL_DAYS
        entry = self._cache.get(key)
        
        if not entry:
            return True
        
        last_checked = entry.get('last_checked')
        if not last_checked:
            return True
        
        try:
            check_time = datetime.fromisoformat(last_checked)
            cutoff = datetime.now() - timedelta(days=ttl)
            return check_time < cutoff
        except (ValueError, TypeError):
            return True
    
    def get_entry_age(self, key: str) -> Optional[timedelta]:
        """
        Get age of a cache entry.
        
        Args:
            key: Cache key
            
        Returns:
            timedelta since last check, or None if not found
        """
        entry = self._cache.get(key)
        if not entry or 'last_checked' not in entry:
            return None
        
        try:
            check_time = datetime.fromisoformat(entry['last_checked'])
            return datetime.now() - check_time
        except (ValueError, TypeError):
            return None
    
    def count_stale_entries(self, days: Optional[int] = None) -> int:
        """
        Count how many cache entries are stale.
        
        Args:
            days: Days before entry is stale (default from settings)
            
        Returns:
            Number of stale entries
        """
        ttl = days if days is not None else CACHE_TTL_DAYS
        return sum(1 for key in self._cache if self.is_entry_stale(key, ttl))
    
    def prune_old_entries(self, days: Optional[int] = None) -> int:
        """
        Remove cache entries older than specified days.
        
        Args:
            days: Remove entries older than this (default from settings)
            
        Returns:
            Number of entries removed
        """
        ttl = days if days is not None else CACHE_TTL_DAYS
        keys_to_remove = [
            key for key in self._cache
            if self.is_entry_stale(key, ttl)
        ]
        
        for key in keys_to_remove:
            del self._cache[key]
        
        if keys_to_remove:
            self._save_cache()
            self.logger.info(f"Pruned {len(keys_to_remove)} stale cache entries")
        
        return len(keys_to_remove)
    
    def auto_prune_if_needed(self) -> int:
        """
        Automatically prune if cache is large and has stale entries.
        
        Only prunes if:
        1. CACHE_AUTO_PRUNE is enabled
        2. Cache has more than CACHE_PRUNE_THRESHOLD entries
        
        Returns:
            Number of entries pruned (0 if pruning not triggered)
        """
        if not CACHE_AUTO_PRUNE:
            return 0
        
        if len(self._cache) < CACHE_PRUNE_THRESHOLD:
            return 0
        
        stale_count = self.count_stale_entries()
        if stale_count > 0:
            self.logger.debug(f"Auto-pruning {stale_count} stale entries...")
            return self.prune_old_entries()
        
        return 0
    
    def get_freshness_summary(self) -> dict:
        """
        Get a summary of cache freshness.
        
        Returns:
            Dict with freshness stats
        """
        if not self._cache:
            return {
                'total': 0,
                'fresh': 0,
                'stale': 0,
                'oldest_days': None,
                'newest_days': None
            }
        
        ages = []
        for key in self._cache:
            age = self.get_entry_age(key)
            if age:
                ages.append(age.total_seconds() / 86400)  # Convert to days
        
        stale_count = self.count_stale_entries()
        
        return {
            'total': len(self._cache),
            'fresh': len(self._cache) - stale_count,
            'stale': stale_count,
            'oldest_days': max(ages) if ages else None,
            'newest_days': min(ages) if ages else None
        }
