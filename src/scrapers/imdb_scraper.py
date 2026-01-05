"""
IMDB Scraper Implementation - The Heart of Episode Detection.

This module is responsible for:
1. Fetching episode pages from IMDB
2. Parsing the HTML to extract episode information
3. Comparing episodes against user's last watched to find new ones

TECHNICAL ARCHITECTURE:
=======================
The scraper uses a STATE MACHINE pattern for HTML parsing. Here's why:

IMDB's HTML is complex and nested. A simple regex approach would be fragile:
    BAD:  re.search(r'S(\d+).E(\d+)', html)  # Matches too much!
    
Instead, we track WHERE we are in the document structure:
    "I'm inside an episode container → I'm inside the title → This text is the episode code"

STATE MACHINE STATES:
    IDLE → IN_EPISODE → IN_TITLE → (capture data) → back to IDLE

This makes the parser resilient to minor HTML changes while staying accurate.

IMDB URL PATTERNS:
==================
Episode list URL: https://www.imdb.com/title/tt0903747/episodes?season=1
                                              ↑ IMDB ID        ↑ Season

The scraper iterates through seasons (1, 2, 3...) until no episodes are found.

WHY HTMLParser OVER BEAUTIFUL SOUP?
===================================
BeautifulSoup is more ergonomic, but:
1. Project requirement: stdlib only
2. HTMLParser is surprisingly capable
3. Forces us to understand HTML structure deeply (better for maintenance)
"""

import re
from html.parser import HTMLParser
from typing import List, Optional, Tuple
from dataclasses import dataclass

from .base_scraper import BaseScraper
from .http_client import HTTPClient, FetchError
from ..database.models import Episode
from ..config.settings import IMDB_SEASON_URL


@dataclass
class ParsedEpisode:
    """
    Intermediate representation of an episode during parsing.
    
    This is separate from the Episode model because:
    1. Parsing may produce incomplete data (missing fields)
    2. We need to validate before creating Episode objects
    3. Keeps parsing logic decoupled from database models
    
    Attributes:
        season: Season number (e.g., 1)
        episode: Episode number (e.g., 5)
        title: Episode title (e.g., "Pilot")
        air_date: Air date string (e.g., "Jan 20, 2008")
    """
    season: Optional[int] = None
    episode: Optional[int] = None
    title: Optional[str] = None
    air_date: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if we have minimum required data."""
        return self.season is not None and self.episode is not None
    
    @property
    def episode_code(self) -> str:
        """Format as standard episode code (e.g., 'S01E05')."""
        if self.season is not None and self.episode is not None:
            return f"S{self.season:02d}E{self.episode:02d}"
        return "S00E00"


class IMDBEpisodeParser(HTMLParser):
    """
    HTML Parser for IMDB Episode Pages using State Machine Pattern.
    
    HOW HTMLParser WORKS:
    =====================
    HTMLParser is an event-driven parser. As it reads HTML, it calls methods:
    
    <div class="episode">      → handle_starttag('div', [('class', 'episode')])
        Episode Title          → handle_data('Episode Title')
    </div>                     → handle_endtag('div')
    
    We override these methods to extract the data we need.
    
    STATE MACHINE:
    ==============
    ```
    ┌──────────────────────────────────────────────────────────────────┐
    │                                                                   │
    │  IDLE ──────► IN_EPISODE ──────► IN_TITLE ──────► (capture)      │
    │    ▲              │                  │                │          │
    │    │              │                  │                │          │
    │    └──────────────┴──────────────────┴────────────────┘          │
    │              (on container end, save episode)                     │
    └──────────────────────────────────────────────────────────────────┘
    ```
    
    IMDB HTML STRUCTURE (as of 2024):
    =================================
    Each episode is wrapped in an article:
    
    <article class="episode-item-wrapper">
        <div class="ipc-title">
            <a href="/title/tt1234567/">
                <h3 class="ipc-title__text">S1.E1 ∙ Pilot</h3>
            </a>
        </div>
        <span class="ipc-metadata-list-item__content">Sun, Jan 20, 2008</span>
    </article>
    
    However, IMDB has multiple page variants. We use flexible matching:
    - Look for patterns like "S1.E1" or "S01E01" in text
    - Look for date patterns in metadata spans
    
    Attributes:
        episodes: List of successfully parsed episodes
        current_episode: Episode currently being parsed
        in_episode_container: Whether we're inside an episode block
        in_title_element: Whether we're inside a title element
        capture_next_text: Flag to capture the next text content
        current_season: The season we're parsing (from URL)
    """
    
    def __init__(self, season: int):
        """
        Initialize parser for a specific season.
        
        Args:
            season: The season number being parsed
        """
        super().__init__()
        
        # Results storage
        self.episodes: List[ParsedEpisode] = []
        
        # Current parsing state
        self.current_episode: Optional[ParsedEpisode] = None
        self.current_season = season
        
        # State machine flags
        self.in_episode_container = False
        self.in_title_element = False
        self.in_date_element = False
        self.depth_in_container = 0  # Track nesting depth
        
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        """
        Called when the parser encounters an opening tag.
        
        This method identifies:
        1. Episode containers (article/div with episode-related classes)
        2. Title elements (h3, a with title classes)
        3. Date elements (span with date-related classes)
        
        Args:
            tag: The HTML tag name (e.g., 'div', 'article')
            attrs: List of (name, value) tuples for attributes
        """
        # Convert attrs to dict for easier access
        # [('class', 'foo bar'), ('id', 'test')] → {'class': 'foo bar', 'id': 'test'}
        attr_dict = dict(attrs)
        class_name = attr_dict.get('class', '')
        
        # Detection Strategy 1: Look for episode containers
        # IMDB uses various wrapper classes over time
        episode_container_indicators = [
            'episode-item',
            'list_item',
            'ipc-metadata-list-summary-item',
        ]
        
        if any(indicator in class_name for indicator in episode_container_indicators):
            self.in_episode_container = True
            self.depth_in_container = 1
            self.current_episode = ParsedEpisode(season=self.current_season)
            return
        
        # Track depth when inside container
        if self.in_episode_container:
            self.depth_in_container += 1
        
        # Detection Strategy 2: Title elements within container
        # Usually h3 or anchor tags with title classes
        if self.in_episode_container:
            if tag in ['h3', 'a'] and 'title' in class_name.lower():
                self.in_title_element = True
            
            # Detection Strategy 3: Date/metadata elements
            if tag == 'span' and any(x in class_name for x in ['metadata', 'date', 'airdate']):
                self.in_date_element = True
    
    def handle_endtag(self, tag: str):
        """
        Called when the parser encounters a closing tag.
        
        Key responsibility: Detect when we've exited an episode container
        and save the collected episode data.
        
        Args:
            tag: The HTML tag name being closed
        """
        # Reset element-specific flags
        if tag in ['h3', 'a']:
            self.in_title_element = False
        if tag == 'span':
            self.in_date_element = False
        
        # Track container depth
        if self.in_episode_container:
            self.depth_in_container -= 1
            
            # When depth returns to 0, we've exited the container
            if self.depth_in_container <= 0:
                self.in_episode_container = False
                
                # Save the episode if it has valid data
                if self.current_episode and self.current_episode.is_valid():
                    self.episodes.append(self.current_episode)
                
                self.current_episode = None
    
    def handle_data(self, data: str):
        """
        Called when the parser encounters text content.
        
        This is where we extract actual episode information:
        - Episode codes from title text (e.g., "S1.E5 ∙ Title Here")
        - Air dates from metadata spans
        
        Args:
            data: The text content
        """
        if not self.in_episode_container or not self.current_episode:
            return
        
        # Clean the text
        data = data.strip()
        if not data:
            return
        
        # Strategy 1: Extract episode code from title
        # Patterns: "S1.E5", "S01E05", "S1 E5", "1x05"
        if self.in_title_element or 'S' in data.upper():
            episode_match = self._extract_episode_code(data)
            if episode_match:
                season, episode = episode_match
                self.current_episode.season = season
                self.current_episode.episode = episode
                
                # Try to extract title (usually after separator)
                title = self._extract_title(data)
                if title:
                    self.current_episode.title = title
        
        # Strategy 2: Extract air date
        if self.in_date_element or self._looks_like_date(data):
            self.current_episode.air_date = data
    
    def _extract_episode_code(self, text: str) -> Optional[Tuple[int, int]]:
        """
        Extract season and episode numbers from text.
        
        Handles multiple formats:
        - "S01E05" → (1, 5)
        - "S1.E5" → (1, 5)  
        - "S1 E5" → (1, 5)
        - "1x05" → (1, 5)
        - "Season 1 Episode 5" → (1, 5)
        
        Args:
            text: Text potentially containing episode code
            
        Returns:
            Tuple of (season, episode) or None if not found
        """
        # Pattern 1: S##E## format (most common on IMDB)
        # (?:x) is non-capturing group, allows S1.E5, S1E5, S1 E5
        match = re.search(r'S(\d{1,2})[.\s]*E(\d{1,2})', text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        # Pattern 2: #x## format (alternative notation)
        match = re.search(r'(\d{1,2})x(\d{1,2})', text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        # Pattern 3: "Season # Episode #" format
        match = re.search(r'Season\s*(\d+)\s*Episode\s*(\d+)', text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        return None
    
    def _extract_title(self, text: str) -> Optional[str]:
        """
        Extract episode title from text.
        
        IMDB format is usually: "S1.E5 ∙ Episode Title Here"
        The separator can be: ∙, -, :, or just whitespace after the code
        
        Args:
            text: Full text containing code and title
            
        Returns:
            Episode title or None
        """
        # Look for separators: ∙ (bullet), -, :
        separators = ['∙', ' - ', ': ', '- ', ' : ']
        
        for sep in separators:
            if sep in text:
                parts = text.split(sep, 1)
                if len(parts) > 1:
                    title = parts[1].strip()
                    if title:
                        return title
        
        return None
    
    def _looks_like_date(self, text: str) -> bool:
        """
        Heuristic check if text looks like a date.
        
        Matches patterns like:
        - "Jan 20, 2008"
        - "January 20, 2008"
        - "2008-01-20"
        - "20 Jan 2008"
        
        Args:
            text: Text to check
            
        Returns:
            True if it looks like a date
        """
        # Month names (abbreviated or full)
        months = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 
                  'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        
        text_lower = text.lower()
        
        # Check for month name + year pattern
        has_month = any(month in text_lower for month in months)
        has_year = bool(re.search(r'\b(19|20)\d{2}\b', text))
        
        return has_month and has_year


class IMDBScraper(BaseScraper):
    """
    Complete IMDB Scraper for Episode Data.
    
    This class orchestrates the full scraping process:
    1. Builds URLs for each season
    2. Fetches HTML via HTTPClient
    3. Parses HTML via IMDBEpisodeParser
    4. Compares against last watched episode
    5. Returns new episodes only
    
    USAGE:
    ======
    scraper = IMDBScraper()
    
    # Get all episodes for a series
    episodes = scraper.get_latest_episodes("tt0903747")
    
    # Get only new episodes since user's last watch
    new_eps = scraper.get_new_episodes("tt0903747", "S02E05")
    # Returns: [S02E06, S02E07, S03E01, ...]
    
    ERROR HANDLING:
    ===============
    - Network errors are logged and an empty list is returned
    - Parsing errors for individual episodes are skipped (graceful degradation)
    - Complete failures raise FetchError for upstream handling
    """
    
    def __init__(self):
        """Initialize scraper with HTTP client."""
        super().__init__()
        self.http_client = HTTPClient()
    
    def get_latest_episodes(self, imdb_id: str) -> List[Episode]:
        """
        Get all episodes for a series from IMDB.
        
        This method iterates through all seasons until no more are found.
        It's the foundation for both "show all episodes" and "find new episodes".
        
        Implementation Strategy:
        ========================
        1. Start with season 1
        2. Fetch and parse that season's page
        3. If episodes found, increment season and repeat
        4. If no episodes found (empty page), we've reached the end
        
        This handles series with any number of seasons without needing
        to know the count in advance.
        
        Args:
            imdb_id: IMDB ID of the series (e.g., "tt0903747")
            
        Returns:
            List of Episode objects, sorted by season/episode
        """
        all_episodes: List[Episode] = []
        season = 1
        max_empty_seasons = 2  # Allow 1 gap season before stopping
        empty_seasons = 0
        
        self.logger.info(f"Fetching episodes for IMDB ID: {imdb_id}")
        
        while empty_seasons < max_empty_seasons:
            try:
                # Build URL for this season
                url = IMDB_SEASON_URL.format(imdb_id=imdb_id, season=season)
                self.logger.debug(f"Fetching season {season}: {url}")
                
                # Fetch HTML
                html = self.http_client.fetch(url)
                
                # Parse episodes from HTML
                parser = IMDBEpisodeParser(season=season)
                parser.feed(html)
                season_episodes = parser.episodes
                
                if season_episodes:
                    self.logger.info(f"Found {len(season_episodes)} episodes in season {season}")
                    
                    # Convert ParsedEpisodes to Episode model objects
                    for parsed_ep in season_episodes:
                        episode = Episode(
                            series_imdb_id=imdb_id,
                            season=parsed_ep.season or season,
                            episode=parsed_ep.episode or 0,
                            title=parsed_ep.title or "Unknown",
                            air_date=parsed_ep.air_date
                        )
                        all_episodes.append(episode)
                    
                    empty_seasons = 0  # Reset counter on success
                else:
                    empty_seasons += 1
                    self.logger.debug(f"No episodes found for season {season}")
                
                season += 1
                
            except FetchError as e:
                # Network/HTTP errors
                self.logger.error(f"Failed to fetch season {season}: {e}")
                
                # If we haven't found any episodes yet, this might be an invalid ID
                if not all_episodes and season == 1:
                    self.logger.error(f"Could not fetch any data for {imdb_id}")
                    return []
                
                # Otherwise, assume we've reached the end
                break
            
            except Exception as e:
                # Unexpected errors - log and continue
                self.logger.error(f"Unexpected error parsing season {season}: {e}")
                empty_seasons += 1
                season += 1
        
        # Sort episodes by season and episode number
        all_episodes.sort()
        
        self.logger.info(f"Total episodes found for {imdb_id}: {len(all_episodes)}")
        return all_episodes
    
    def check_new_episodes(self, imdb_id: str, last_episode: str) -> List[str]:
        """
        Check for new episodes since last watched.
        
        This is the key method for the user: "What haven't I seen yet?"
        
        Args:
            imdb_id: IMDB ID of the series
            last_episode: Last watched episode code (e.g., "S02E05")
            
        Returns:
            List of new episode codes (e.g., ["S02E06", "S02E07", "S03E01"])
        """
        new_episodes = self.get_new_episodes(imdb_id, last_episode)
        return [ep.episode_code for ep in new_episodes]
    
    def get_new_episodes(self, imdb_id: str, last_episode: str) -> List[Episode]:
        """
        Get Episode objects for all unwatched episodes.
        
        This method provides full Episode details (title, air date) for
        episodes newer than the user's last watched.
        
        EPISODE COMPARISON LOGIC:
        =========================
        Last watched: S02E05
        
        Episodes from IMDB:
          S01E01 → older (skip)
          S02E05 → exactly last watched (skip)
          S02E06 → newer (include!)
          S03E01 → newer (include!)
        
        Comparison is done by converting to tuples and comparing:
          (2, 5) < (2, 6) → True, so S02E06 is newer
          (2, 5) < (3, 1) → True, so S03E01 is newer
        
        Args:
            imdb_id: IMDB ID of the series
            last_episode: Last watched episode code (e.g., "S02E05")
            
        Returns:
            List of Episode objects for new episodes
        """
        # Parse last watched episode
        last_season, last_ep_num = self._parse_episode_code(last_episode)
        
        if last_season is None:
            self.logger.warning(f"Could not parse last episode code: {last_episode}")
            # Return all episodes if we can't parse
            return self.get_latest_episodes(imdb_id)
        
        # Get all episodes from IMDB
        all_episodes = self.get_latest_episodes(imdb_id)
        
        # Filter to only new episodes
        new_episodes = []
        for episode in all_episodes:
            # Compare (season, episode) tuples
            # (3, 1) > (2, 5) → True
            # (2, 6) > (2, 5) → True
            # (2, 5) > (2, 5) → False (exactly at last watched)
            if (episode.season, episode.episode) > (last_season, last_ep_num):
                new_episodes.append(episode)
        
        self.logger.info(
            f"Found {len(new_episodes)} new episodes after {last_episode}"
        )
        
        return new_episodes
    
    def _parse_episode_code(self, code: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Parse episode code string into season and episode numbers.
        
        Handles common formats:
        - "S01E05" → (1, 5)
        - "S1E5" → (1, 5)
        - "S00E00" → (0, 0) (special case: never watched)
        
        Args:
            code: Episode code string
            
        Returns:
            Tuple of (season, episode) or (None, None) if parsing fails
        """
        match = re.match(r'S(\d{1,2})E(\d{1,2})', code, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
        
        self.logger.warning(f"Could not parse episode code: {code}")
        return None, None