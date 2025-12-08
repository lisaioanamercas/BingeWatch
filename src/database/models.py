"""
Data models for BingeWatch.
Defines the structure of series data.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Series:
    """
    Represents a TV series in the database.
    
    Attributes:
        name: Series name
        imdb_id: IMDB identifier (e.g., 'tt1234567')
        last_episode: Last watched episode (e.g., 'S01E05')
        last_watch_date: Date of last watch
        score: User rating (1-10)
        snoozed: Whether series is snoozed (0 or 1)
        id: Database primary key (auto-generated)
    """
    name: str
    imdb_id: str
    last_episode: str = "S00E00"
    last_watch_date: Optional[str] = None
    score: int = 5
    snoozed: int = 0
    id: Optional[int] = None
    
    def __post_init__(self):
        """Set default last_watch_date if not provided."""
        if self.last_watch_date is None:
            self.last_watch_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self):
        """Convert series to dictionary for database operations."""
        return asdict(self)
    
    @classmethod
    def from_db_row(cls, row):
        """
        Create Series instance from database row.
        
        Args:
            row: sqlite3.Row object
            
        Returns:
            Series: New Series instance
        """
        return cls(
            id=row['id'],
            name=row['name'],
            imdb_id=row['imdb_id'],
            last_episode=row['last_episode'],
            last_watch_date=row['last_watch_date'],
            score=row['score'],
            snoozed=row['snoozed']
        )
    
    def __str__(self):
        """String representation for display."""
        status = "[SNOOZED]" if self.snoozed else ""
        return (
            f"{self.name} {status}\n"
            f"  IMDB: {self.imdb_id} | Score: {self.score}/10\n"
            f"  Last watched: {self.last_episode} on {self.last_watch_date}"
        )


@dataclass
class Episode:
    """
    Represents a TV episode.
    
    Attributes:
        series_imdb_id: IMDB ID of the series
        season: Season number
        episode: Episode number
        title: Episode title
        air_date: Air date (YYYY-MM-DD format)
        episode_code: Formatted episode code (e.g., 'S01E05')
    """
    series_imdb_id: str
    season: int
    episode: int
    title: str = "Unknown"
    air_date: Optional[str] = None
    
    @property
    def episode_code(self):
        """Return formatted episode code (e.g., 'S01E05')."""
        return f"S{self.season:02d}E{self.episode:02d}"
    
    def __str__(self):
        """String representation for display."""
        date_str = f" (aired: {self.air_date})" if self.air_date else ""
        return f"{self.episode_code}: {self.title}{date_str}"
    
    def __lt__(self, other):
        """Enable sorting by season and episode number."""
        if self.season != other.season:
            return self.season < other.season
        return self.episode < other.episode