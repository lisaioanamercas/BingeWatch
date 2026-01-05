"""
YouTube Scraper - Finding Trailers & Clips for Episodes.

This module implements Phase 4's core functionality: discovering YouTube
videos related to specific TV series episodes.

THE CHALLENGE:
==============
YouTube doesn't have a simple episode-specific API. We need to:
1. Build smart search queries
2. Scrape YouTube search results HTML
3. Extract video information from complex JavaScript-heavy pages

TECHNICAL APPROACH:
===================

1. SEARCH QUERY STRATEGY:
   For "Breaking Bad S01E04", we search:
   - "Breaking Bad Season 1 Episode 4 trailer"
   - "Breaking Bad S01E04 clip"
   - "Breaking Bad Cancer Man" (episode title if known)
   
   Multiple queries increase chance of finding relevant content.

2. HTML PARSING CHALLENGE:
   YouTube search results are heavily JavaScript-dependent.
   The initial HTML contains JSON data with video info embedded.
   We extract this JSON rather than parsing rendered HTML.

3. DATA EXTRACTION:
   From the embedded JSON/HTML, we extract:
   - Video ID (for URL construction)
   - Video title
   - Channel name (useful for filtering official content)
   - View count (optional, for relevance)

IMPORTANT LIMITATIONS:
======================
- YouTube may rate-limit or block frequent requests
- HTML structure changes frequently
- Some content is region-locked
- Results may include non-related videos (fan content, etc.)

USAGE:
======
    scraper = YouTubeScraper()
    
    # Search for episode trailers
    results = scraper.search_episode_videos("Breaking Bad", "S01E04", "Cancer Man")
    
    for video in results:
        print(f"{video.title}: {video.url}")
"""

import re
import json
from html.parser import HTMLParser
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote_plus

from .base_scraper import BaseScraper
from .http_client import HTTPClient, FetchError
from ..config.settings import USER_AGENT


# YouTube base URL for search
YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query={query}"
YOUTUBE_VIDEO_URL = "https://www.youtube.com/watch?v={video_id}"


@dataclass
class VideoResult:
    """
    Represents a YouTube video from search results.
    
    WHY THIS CLASS?
    ===============
    Encapsulates all video metadata we care about:
    - Enough info to display to user
    - URL for direct access
    - Channel info for filtering (official vs fan content)
    
    Attributes:
        video_id: YouTube video ID (the 'v' parameter)
        title: Video title
        channel_name: Name of the channel that uploaded
        url: Full YouTube watch URL
        thumbnail_url: URL to video thumbnail (optional)
        duration: Video duration string if available
    """
    video_id: str
    title: str
    channel_name: str = "Unknown"
    url: str = ""
    thumbnail_url: Optional[str] = None
    duration: Optional[str] = None
    
    def __post_init__(self):
        """Generate URL from video_id if not provided."""
        if not self.url and self.video_id:
            self.url = YOUTUBE_VIDEO_URL.format(video_id=self.video_id)
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.title} ({self.channel_name})\n  {self.url}"
    
    def short_str(self) -> str:
        """Compact representation for lists."""
        # Truncate long titles
        title = self.title if len(self.title) <= 50 else self.title[:47] + "..."
        return f"{title} - {self.url}"


class YouTubeJSONExtractor:
    """
    Extracts video data from YouTube's embedded JSON.
    
    HOW YOUTUBE PAGES WORK:
    =======================
    YouTube search results pages contain JavaScript that initializes
    the page with JSON data. This JSON is embedded in a script tag:
    
    <script>var ytInitialData = {...huge JSON object...};</script>
    
    This JSON contains all the video information we need, more reliably
    than trying to parse the rendered HTML.
    
    EXTRACTION STRATEGY:
    ====================
    1. Find the ytInitialData JSON in the page
    2. Parse it as JSON
    3. Navigate the nested structure to find video renderers
    4. Extract video ID, title, channel from each renderer
    """
    
    def __init__(self):
        """Initialize extractor."""
        self.logger = None  # Will be set by YouTubeScraper
    
    def extract_videos(self, html: str) -> List[VideoResult]:
        """
        Extract video results from YouTube search page HTML.
        
        Args:
            html: Raw HTML from YouTube search results page
            
        Returns:
            List of VideoResult objects
        """
        videos = []
        
        # Strategy 1: Extract from ytInitialData JSON
        # This is the most reliable method
        json_videos = self._extract_from_initial_data(html)
        if json_videos:
            return json_videos
        
        # Strategy 2: Fallback to regex patterns
        # Less reliable but works if JSON extraction fails
        regex_videos = self._extract_from_regex(html)
        if regex_videos:
            return regex_videos
        
        return videos
    
    def _extract_from_initial_data(self, html: str) -> List[VideoResult]:
        """
        Extract videos from ytInitialData JSON blob.
        
        YouTube embeds search results as JSON in the page:
        var ytInitialData = {...};
        
        This JSON has a deep nested structure:
        contents.twoColumnSearchResultsRenderer.primaryContents
            .sectionListRenderer.contents[0].itemSectionRenderer
            .contents[].videoRenderer
        
        Each videoRenderer contains:
        - videoId: "dQw4w9WgXcQ"
        - title.runs[0].text: "Video Title"
        - ownerText.runs[0].text: "Channel Name"
        """
        videos = []
        
        # Find the ytInitialData JSON
        # Pattern: var ytInitialData = {...};
        pattern = r'var ytInitialData\s*=\s*(\{.+?\});'
        match = re.search(pattern, html, re.DOTALL)
        
        if not match:
            # Try alternative pattern (sometimes it's different)
            pattern = r'ytInitialData\s*=\s*(\{.+?\});'
            match = re.search(pattern, html, re.DOTALL)
        
        if not match:
            return videos
        
        try:
            # Parse the JSON
            json_str = match.group(1)
            data = json.loads(json_str)
            
            # Navigate to video results
            # The path varies, so we search recursively
            video_renderers = self._find_video_renderers(data)
            
            for renderer in video_renderers:
                video = self._parse_video_renderer(renderer)
                if video:
                    videos.append(video)
        
        except json.JSONDecodeError:
            # JSON parsing failed, return empty
            pass
        except Exception:
            # Any other error, return what we have
            pass
        
        return videos
    
    def _find_video_renderers(self, data: dict, max_depth: int = 15) -> List[dict]:
        """
        Recursively find all videoRenderer objects in the JSON.
        
        YouTube's JSON structure is deeply nested and changes over time.
        Instead of hardcoding the path, we search for videoRenderer keys.
        
        Args:
            data: JSON data (dict or list)
            max_depth: Maximum recursion depth to prevent infinite loops
            
        Returns:
            List of videoRenderer dictionaries
        """
        renderers = []
        
        if max_depth <= 0:
            return renderers
        
        if isinstance(data, dict):
            # Check if this is a video renderer
            if 'videoRenderer' in data:
                renderers.append(data['videoRenderer'])
            
            # Recurse into all values
            for value in data.values():
                renderers.extend(self._find_video_renderers(value, max_depth - 1))
        
        elif isinstance(data, list):
            # Recurse into list items
            for item in data:
                renderers.extend(self._find_video_renderers(item, max_depth - 1))
        
        return renderers
    
    def _parse_video_renderer(self, renderer: dict) -> Optional[VideoResult]:
        """
        Parse a videoRenderer object into a VideoResult.
        
        Example renderer structure:
        {
            "videoId": "dQw4w9WgXcQ",
            "title": {"runs": [{"text": "Video Title"}]},
            "ownerText": {"runs": [{"text": "Channel Name"}]},
            "lengthText": {"simpleText": "3:32"},
            "thumbnail": {"thumbnails": [{"url": "..."}]}
        }
        
        Args:
            renderer: videoRenderer dictionary
            
        Returns:
            VideoResult or None if parsing fails
        """
        try:
            # Extract video ID (required)
            video_id = renderer.get('videoId')
            if not video_id:
                return None
            
            # Extract title
            title = "Unknown Title"
            title_obj = renderer.get('title', {})
            if 'runs' in title_obj and title_obj['runs']:
                title = title_obj['runs'][0].get('text', title)
            elif 'simpleText' in title_obj:
                title = title_obj['simpleText']
            
            # Extract channel name
            channel = "Unknown"
            owner_obj = renderer.get('ownerText', {})
            if 'runs' in owner_obj and owner_obj['runs']:
                channel = owner_obj['runs'][0].get('text', channel)
            
            # Extract duration (optional)
            duration = None
            length_obj = renderer.get('lengthText', {})
            if 'simpleText' in length_obj:
                duration = length_obj['simpleText']
            
            # Extract thumbnail (optional)
            thumbnail = None
            thumb_obj = renderer.get('thumbnail', {})
            thumbnails = thumb_obj.get('thumbnails', [])
            if thumbnails:
                thumbnail = thumbnails[0].get('url')
            
            return VideoResult(
                video_id=video_id,
                title=title,
                channel_name=channel,
                duration=duration,
                thumbnail_url=thumbnail
            )
        
        except Exception:
            return None
    
    def _extract_from_regex(self, html: str) -> List[VideoResult]:
        """
        Fallback extraction using regex patterns.
        
        This is less reliable than JSON extraction but works
        when YouTube changes their JSON structure.
        
        We look for patterns like:
        - /watch?v=VIDEO_ID
        - "videoId":"VIDEO_ID"
        - title="Video Title"
        """
        videos = []
        seen_ids = set()
        
        # Pattern: "videoId":"XXXXXXXXXXX"
        video_id_pattern = r'"videoId"\s*:\s*"([a-zA-Z0-9_-]{11})"'
        
        for match in re.finditer(video_id_pattern, html):
            video_id = match.group(1)
            
            # Skip duplicates
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)
            
            # Try to find title near this video ID
            # Look for title in surrounding context
            start = max(0, match.start() - 500)
            end = min(len(html), match.end() + 500)
            context = html[start:end]
            
            title = "Unknown Title"
            title_match = re.search(r'"title"\s*:\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"([^"]+)"', context)
            if title_match:
                title = title_match.group(1)
            
            videos.append(VideoResult(
                video_id=video_id,
                title=title
            ))
            
            # Limit results
            if len(videos) >= 10:
                break
        
        return videos


class YouTubeScraper(BaseScraper):
    """
    YouTube scraper for finding episode-related videos.
    
    This scraper searches YouTube for trailers, clips, and other content
    related to specific TV series episodes.
    
    SEARCH STRATEGY:
    ================
    For each episode, we perform multiple searches:
    1. "{series} Season {X} Episode {Y} trailer"
    2. "{series} S{XX}E{YY}"
    3. "{series} {episode_title}" (if title known)
    
    We combine and deduplicate results.
    
    RATE LIMITING:
    ==============
    YouTube may block or rate-limit frequent requests.
    - Add delays between searches
    - Cache results where possible
    - Use session cookies if available
    
    USAGE:
    ======
        scraper = YouTubeScraper()
        
        # Search for episode content
        videos = scraper.search_episode_videos(
            series_name="Breaking Bad",
            episode_code="S01E04",
            episode_title="Cancer Man"
        )
        
        for video in videos:
            print(video)
    """
    
    def __init__(self):
        """Initialize YouTube scraper."""
        super().__init__()
        self.http_client = HTTPClient()
        self.extractor = YouTubeJSONExtractor()
        self.extractor.logger = self.logger
    
    def search_episode_videos(
        self,
        series_name: str,
        episode_code: str,
        episode_title: Optional[str] = None,
        max_results: int = 5
    ) -> List[VideoResult]:
        """
        Search for videos related to a specific episode.
        
        This is the main public method. It:
        1. Builds search queries for the episode
        2. Fetches YouTube search results
        3. Parses and deduplicates videos
        4. Returns top results
        
        Args:
            series_name: Name of the TV series
            episode_code: Episode code (e.g., "S01E04")
            episode_title: Optional episode title for better searches
            max_results: Maximum videos to return
            
        Returns:
            List of VideoResult objects
        """
        self.logger.info(f"Searching YouTube for {series_name} {episode_code}")
        
        all_videos: List[VideoResult] = []
        seen_ids = set()
        
        # Build search queries
        queries = self._build_search_queries(series_name, episode_code, episode_title)
        
        for query in queries:
            try:
                videos = self._search_youtube(query)
                
                # Add new videos (deduplicate by ID)
                for video in videos:
                    if video.video_id not in seen_ids:
                        seen_ids.add(video.video_id)
                        all_videos.append(video)
                
                # Stop if we have enough
                if len(all_videos) >= max_results * 2:
                    break
            
            except FetchError as e:
                self.logger.warning(f"YouTube search failed for '{query}': {e}")
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error searching YouTube: {e}")
                continue
        
        # Filter for relevance (videos that mention the series)
        relevant_videos = self._filter_relevant(all_videos, series_name)
        
        # Return top results
        return relevant_videos[:max_results]
    
    def search_series_trailers(
        self,
        series_name: str,
        max_results: int = 5
    ) -> List[VideoResult]:
        """
        Search for general series trailers (not episode-specific).
        
        Useful for series overview or when no specific episode is targeted.
        
        Args:
            series_name: Name of the TV series
            max_results: Maximum videos to return
            
        Returns:
            List of VideoResult objects
        """
        self.logger.info(f"Searching for {series_name} trailers")
        
        queries = [
            f"{series_name} official trailer",
            f"{series_name} TV series trailer",
            f"{series_name} season trailer",
        ]
        
        all_videos: List[VideoResult] = []
        seen_ids = set()
        
        for query in queries:
            try:
                videos = self._search_youtube(query)
                for video in videos:
                    if video.video_id not in seen_ids:
                        seen_ids.add(video.video_id)
                        all_videos.append(video)
            except Exception as e:
                self.logger.warning(f"Search failed: {e}")
        
        return all_videos[:max_results]
    
    def _build_search_queries(
        self,
        series_name: str,
        episode_code: str,
        episode_title: Optional[str] = None
    ) -> List[str]:
        """
        Build effective search queries for an episode.
        
        QUERY STRATEGY:
        ===============
        Different query formats work better for different content:
        
        1. "Series S01E04 trailer" - Good for official trailers
        2. "Series Season 1 Episode 4" - Some videos use full format
        3. "Series Episode Title" - Works if title is distinctive
        4. "Series S01E04 clip" - For scene clips
        5. "Series S01E04 recap" - For recap videos
        
        Args:
            series_name: Series name
            episode_code: Episode code (e.g., "S01E04")
            episode_title: Optional episode title
            
        Returns:
            List of search query strings
        """
        queries = []
        
        # Parse episode code for expanded format
        match = re.match(r'S(\d+)E(\d+)', episode_code, re.IGNORECASE)
        season_num = match.group(1) if match else "1"
        episode_num = match.group(2) if match else "1"
        
        # Primary queries (most likely to find relevant content)
        queries.append(f"{series_name} {episode_code} trailer")
        queries.append(f"{series_name} Season {int(season_num)} Episode {int(episode_num)}")
        
        # If we have episode title, use it
        if episode_title and episode_title != "Unknown":
            queries.append(f"{series_name} {episode_title}")
        
        # Secondary queries (clips, scenes, recaps)
        queries.append(f"{series_name} {episode_code} scene")
        
        return queries
    
    def _search_youtube(self, query: str) -> List[VideoResult]:
        """
        Perform a YouTube search and extract video results.
        
        Args:
            query: Search query string
            
        Returns:
            List of VideoResult objects from search
        """
        # URL-encode the query
        encoded_query = quote_plus(query)
        url = YOUTUBE_SEARCH_URL.format(query=encoded_query)
        
        self.logger.debug(f"Fetching YouTube search: {url}")
        
        # Fetch search results page
        html = self.http_client.fetch(url)
        
        # Extract videos from HTML
        videos = self.extractor.extract_videos(html)
        
        self.logger.debug(f"Found {len(videos)} videos for query '{query}'")
        
        return videos
    
    def _filter_relevant(
        self,
        videos: List[VideoResult],
        series_name: str
    ) -> List[VideoResult]:
        """
        Filter videos to only those relevant to the series.
        
        RELEVANCE CRITERIA:
        ===================
        - Video title contains series name (case-insensitive)
        - Prioritize official channels (HBO, AMC, Netflix, etc.)
        - Deprioritize unrelated content
        
        Args:
            videos: All videos found
            series_name: Series name for matching
            
        Returns:
            Filtered and sorted list
        """
        # Simple relevance: title contains series name
        series_words = series_name.lower().split()
        
        relevant = []
        somewhat_relevant = []
        
        for video in videos:
            title_lower = video.title.lower()
            
            # Check if all words from series name are in title
            if all(word in title_lower for word in series_words):
                relevant.append(video)
            # Check if at least half the words match
            elif sum(1 for word in series_words if word in title_lower) >= len(series_words) / 2:
                somewhat_relevant.append(video)
        
        # Return relevant first, then somewhat relevant
        return relevant + somewhat_relevant
    
    def get_latest_episodes(self, imdb_id: str):
        """Not applicable for YouTube scraper - required by base class."""
        return []
    
    def check_new_episodes(self, imdb_id: str, last_episode: str):
        """Not applicable for YouTube scraper - required by base class."""
        return []
