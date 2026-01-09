"""
Episode Ranking Service - The Brain Behind "What Should I Watch?"

This module implements Phase 3's core functionality: prioritizing episodes
across all tracked series based on user preferences.

THE PROBLEM:
============
You have 5 series with new episodes. Which do you watch first?

Without ranking:
    - Breaking Bad: S03E01 (score: 9)
    - The Office: S02E05 (score: 7)
    - Game of Thrones: S01E02 (score: 10)
    
You'd have to mentally sort these. With ranking:
    1. Game of Thrones S01E02 (score: 10) ← Watch this first!
    2. Breaking Bad S03E01 (score: 9)
    3. The Office S02E05 (score: 7)

DESIGN DECISIONS:
=================

1. WHY A SEPARATE SERVICE?
   - Separation of Concerns: Ranking logic is distinct from scraping and DB
   - Testability: Can unit test ranking without network/database
   - Reusability: Same ranking can be used by multiple commands

2. RANKING ALGORITHM:
   Primary sort: Series score (descending) - higher score = watch first
   Secondary sort: Episode code (ascending) - earlier episodes first
   
   This means for a score-10 series, you'll see S01E01 before S01E02.

3. DATA STRUCTURE:
   PrioritizedEpisode combines Episode data with Series metadata.
   This allows displaying "Game of Thrones S01E02 (Score: 10/10)"
   without needing to look up the series again.

USAGE:
======
    ranker = EpisodeRanker(db_manager, scraper)
    
    # Get prioritized watchlist
    watchlist = ranker.get_prioritized_watchlist()
    
    for item in watchlist:
        print(f"{item.series_name} {item.episode_code} (Score: {item.score})")
"""

from dataclasses import dataclass
from typing import List, Optional
from ..database.db_manager import DBManager
from ..database.models import Series, Episode
from ..scrapers.imdb_scraper import IMDBScraper
from ..utils.logger import get_logger


@dataclass
class PrioritizedEpisode:
    """
    An episode enriched with series information for ranking display.
    
    WHY THIS CLASS EXISTS:
    ======================
    The Episode class only knows about itself (season, episode, title).
    For ranking, we need to know about its SERIES (name, score).
    
    This class combines both, making it easy to:
    - Sort by series score
    - Display "Series Name - S01E05 (Score: 9/10)"
    - Filter by various criteria
    
    Attributes:
        series_name: Name of the series (e.g., "Breaking Bad")
        series_imdb_id: IMDB ID for reference
        score: User's rating of the series (1-10)
        season: Season number
        episode_number: Episode number within season
        episode_title: Title of the episode
        air_date: When the episode aired
        priority_rank: Calculated position in watchlist (set after sorting)
    """
    series_name: str
    series_imdb_id: str
    score: int
    season: int
    episode_number: int
    episode_title: str = "Unknown"
    air_date: Optional[str] = None
    priority_rank: int = 0
    
    @property
    def episode_code(self) -> str:
        """Format as standard episode code (e.g., 'S01E05')."""
        return f"S{self.season:02d}E{self.episode_number:02d}"
    
    def __str__(self) -> str:
        """Human-readable representation for display."""
        date_str = f" (aired: {self.air_date})" if self.air_date else ""
        return (
            f"[Score: {self.score}/10] {self.series_name} - "
            f"{self.episode_code}: {self.episode_title}{date_str}"
        )
    
    def short_str(self) -> str:
        """Compact representation for lists."""
        return f"{self.series_name} {self.episode_code}"


class EpisodeRanker:
    """
    Service for ranking and filtering new episodes across all series.
    
    This class orchestrates the full "what should I watch?" workflow:
    
    1. FETCH: Get all non-snoozed series from database
    2. SCRAPE: Check IMDB for new episodes for each series
    3. COMBINE: Merge episode data with series metadata
    4. FILTER: Exclude series based on snooze status (already done in step 1)
    5. RANK: Sort by score (high to low), then by episode (early to late)
    6. RETURN: Prioritized list ready for display
    
    PERFORMANCE CONSIDERATIONS:
    ===========================
    - This makes N network requests (one per series per season)
    - For 10 series with ~5 seasons each = ~50 HTTP requests
    - Could be slow; consider caching in future phases
    
    ERROR HANDLING:
    ===============
    - If one series fails to fetch, log error and continue with others
    - Never crash the whole ranking due to one series
    - Return partial results with error info
    
    Attributes:
        db_manager: Database access for series data
        scraper: IMDB scraper for episode data
        logger: Logger for this service
    """
    
    def __init__(self, db_manager: DBManager, scraper: Optional[IMDBScraper] = None):
        """
        Initialize ranker with database and scraper.
        
        Args:
            db_manager: Database manager instance
            scraper: Optional IMDB scraper (creates default if not provided)
        """
        self.db_manager = db_manager
        self.scraper = scraper or IMDBScraper()
        self.logger = get_logger()
    
    def get_prioritized_watchlist(
        self, 
        include_snoozed: bool = False,
        min_score: Optional[int] = None,
        max_results: Optional[int] = None
    ) -> List[PrioritizedEpisode]:
        """
        Get all new episodes ranked by priority.
        
        This is the main method for Phase 3. It:
        1. Fetches all active series
        2. Gets new episodes for each
        3. Ranks them by score and episode order
        
        RANKING LOGIC:
        ==============
        Primary: Score (descending)
            - Score 10 episodes come before score 9
            - This reflects "I care about this show more"
        
        Secondary: Season/Episode (ascending)
            - For same-score shows, earlier episodes first
            - This reflects "watch in order"
        
        Example Result:
            1. [10] Game of Thrones S01E02
            2. [10] Game of Thrones S01E03
            3. [9]  Breaking Bad S03E01
            4. [9]  Breaking Bad S03E02
            5. [7]  The Office S02E05
        
        Args:
            include_snoozed: Whether to include snoozed series (default: False)
            min_score: Minimum score to include (e.g., 7 = only 7+ series)
            max_results: Maximum episodes to return (for pagination)
        
        Returns:
            List of PrioritizedEpisode objects, sorted by priority
        """
        self.logger.debug("Building prioritized watchlist...")
        
        # Pas 1: Ia toate seriile din baza de date
        all_series = self.db_manager.get_all_series(include_snoozed=include_snoozed)
        
        if not all_series:
            self.logger.debug("No series in database")
            return []
        
        # Pas 2: Filtreaza dupa scor minim
        if min_score is not None:
            all_series = [s for s in all_series if s.score >= min_score]
        
        # Pas 3: Colecteaza episoadele noi de la fiecare serie
        all_prioritized: List[PrioritizedEpisode] = []
        
        for series in all_series:
            try:
                # Sari peste seriile snoozed
                if series.snoozed and not include_snoozed:
                    continue
                
                # Ia episoadele noi de pe IMDB
                new_episodes = self.scraper.get_new_episodes(
                    series.imdb_id,
                    series.last_episode
                )
                
                # Converteste la obiecte PrioritizedEpisode
                for ep in new_episodes:
                    prioritized = PrioritizedEpisode(
                        series_name=series.name,
                        series_imdb_id=series.imdb_id,
                        score=series.score,
                        season=ep.season,
                        episode_number=ep.episode,
                        episode_title=ep.title,
                        air_date=ep.air_date
                    )
                    all_prioritized.append(prioritized)
                self.logger.debug(f"Found {len(new_episodes)} episodes for {series.name}")
            
            except Exception as e:
                # Nu lasa o eroare sa opreasca tot procesul
                self.logger.error(f"Error fetching {series.name}: {e}")
                continue
        
        # Pas 4: Sorteaza dupa prioritate (scor descrescator, apoi episod crescator)
        all_prioritized.sort(
            key=lambda ep: (-ep.score, ep.season, ep.episode_number)
        )
        
        # Pas 5: Atribuie numere de rang
        for rank, ep in enumerate(all_prioritized, 1):
            ep.priority_rank = rank
        
        # Pas 6: Aplica limita daca e specificata
        if max_results is not None:
            all_prioritized = all_prioritized[:max_results]
        
        self.logger.debug(f"Watchlist complete: {len(all_prioritized)} episodes to watch")
        return all_prioritized
    
    def get_next_episode(self) -> Optional[PrioritizedEpisode]:
        """
        Get the single highest-priority episode to watch next.
        
        Convenience method for "I just want ONE recommendation".
        
        Returns:
            The #1 priority episode, or None if nothing to watch
        """
        watchlist = self.get_prioritized_watchlist(max_results=1)
        return watchlist[0] if watchlist else None
    
    def get_episodes_by_series(
        self, 
        imdb_id: str
    ) -> List[PrioritizedEpisode]:
        """
        Get new episodes for a specific series only.
        
        Useful when user wants to see all new episodes for one show.
        
        Args:
            imdb_id: IMDB ID of the series
            
        Returns:
            List of new episodes for that series
        """
        series = self.db_manager.get_series(imdb_id)
        if not series:
            self.logger.warning(f"Series {imdb_id} not found")
            return []
        
        new_episodes = self.scraper.get_new_episodes(
            series.imdb_id,
            series.last_episode
        )
        
        return [
            PrioritizedEpisode(
                series_name=series.name,
                series_imdb_id=series.imdb_id,
                score=series.score,
                season=ep.season,
                episode_number=ep.episode,
                episode_title=ep.title,
                air_date=ep.air_date
            )
            for ep in new_episodes
        ]
    
    def get_summary_stats(self) -> dict:
        """
        Get statistics about the current watchlist.
        
        Returns dict with:
            - total_episodes: Number of unwatched episodes
            - series_with_new: Number of series with new episodes
            - highest_priority_series: Name of top-scored series with new eps
        """
        watchlist = self.get_prioritized_watchlist()
        
        if not watchlist:
            return {
                'total_episodes': 0,
                'series_with_new': 0,
                'highest_priority_series': None
            }
        
        # Count unique series
        series_names = set(ep.series_name for ep in watchlist)
        
        return {
            'total_episodes': len(watchlist),
            'series_with_new': len(series_names),
            'highest_priority_series': watchlist[0].series_name if watchlist else None
        }
