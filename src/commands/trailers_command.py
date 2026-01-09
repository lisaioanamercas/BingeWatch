"""
Trailers Command - Find YouTube Videos for Episodes.

This command allows users to discover trailers, clips, and other
YouTube content related to specific episodes or series.

USE CASES:
==========
1. "I'm about to watch Breaking Bad S01E04, show me trailers"
2. "What clips are available for Game of Thrones?"
3. "Find trailer for the next episode I should watch"

COMMAND VARIATIONS:
===================
- trailers <imdb_id> <episode_code>  - Videos for specific episode
- trailers <imdb_id>                  - General series trailers
- trailers --next                     - Trailers for next prioritized episode

TECHNICAL NOTE:
===============
YouTube may rate-limit requests. If you get errors:
- Wait a few minutes before trying again
- Results are cached where possible
"""

from typing import Optional
from .base import Command
from ..scrapers.youtube_scraper import YouTubeScraper, VideoResult
from ..services.episode_ranker import EpisodeRanker


class TrailersCommand(Command):
    """
    Command to search for YouTube trailers and clips.
    
    This command integrates with the YouTubeScraper to find
    episode-specific content on YouTube.
    """
    
    def __init__(self, db_manager):
        """Initialize with database manager and scrapers."""
        super().__init__(db_manager)
        self.youtube_scraper = YouTubeScraper()
        self.ranker = EpisodeRanker(db_manager)
    
    def execute(self, args):
        """
        Execute the trailers command.
        
        Parses arguments and searches YouTube for relevant videos.
        
        Args:
            args: Command arguments
                - [imdb_id] [episode_code]: Specific episode
                - [imdb_id]: General series trailers
                - --next: Next prioritized episode
                - --count N: Number of results (default 5)
        
        Returns:
            str: Formatted video results
        """
        try:
            # Parse arguments
            count = self._parse_int_arg(args, '--count', '-c') or 5
            show_next = '--next' in args or '-n' in args
            
            # Filter out flags to get positional args
            positional = [
                a for a in args 
                if not a.startswith('-') and a not in ['--next', '--count']
            ]
            
            # Remove the number after --count from positional
            if '--count' in args or '-c' in args:
                try:
                    idx = args.index('--count') if '--count' in args else args.index('-c')
                    if idx + 1 < len(args):
                        positional = [a for a in positional if a != args[idx + 1]]
                except (ValueError, IndexError):
                    pass
            
            # Handle --next flag
            if show_next:
                return self._search_for_next_episode(count)
            
            # Handle specific episode or series
            if len(positional) >= 2:
                # Episode-specific: trailers "Breaking Bad" S01E04 or trailers tt0903747 S01E04
                identifier = positional[0]
                episode_code = positional[1]
                
                # Resolve series by name or IMDB ID
                series, error = self.resolve_series(identifier)
                if error:
                    return self.error_msg(error)
                
                return self._search_for_episode(series, episode_code, count)
            
            elif len(positional) == 1:
                # Series-general: trailers "Breaking Bad" or trailers tt0903747
                identifier = positional[0]
                
                # Resolve series by name or IMDB ID
                series, error = self.resolve_series(identifier)
                if error:
                    return self.error_msg(error)
                
                return self._search_for_series(series, count)
            
            else:
                # No arguments - show help
                return self.get_help()
        
        except Exception as e:
            error_msg = f"Failed to search trailers: {e}"
            self.logger.error(error_msg)
            return f"[ERROR] {error_msg}"
    
    def _parse_int_arg(self, args, long_flag, short_flag) -> Optional[int]:
        """Parse an integer argument from command args."""
        for flag in [long_flag, short_flag]:
            if flag in args:
                try:
                    idx = args.index(flag)
                    if idx + 1 < len(args):
                        return int(args[idx + 1])
                except (ValueError, IndexError):
                    pass
        return None
    
    def _search_for_episode(self, series, episode_code: str, count: int) -> str:
        """
        Search for videos related to a specific episode.
        
        Args:
            series: Series object
            episode_code: Episode code (e.g., S01E04)
            count: Number of results
            
        Returns:
            Formatted results string
        """
        
        lines = [
            "═" * 60,
            f"TRAILERS: {series.name} {episode_code}",
            "═" * 60,
            ""
        ]
        
        # Search YouTube
        videos = self.youtube_scraper.search_episode_videos(
            series_name=series.name,
            episode_code=episode_code,
            max_results=count
        )
        
        if not videos:
            lines.append("No videos found for this episode.")
            lines.append("")
            lines.append("Try searching for general series trailers:")
            lines.append(f"  trailers {imdb_id}")
        else:
            lines.append(f"Found {len(videos)} video(s):\n")
            
            for i, video in enumerate(videos, 1):
                lines.append(f"{i}. {video.title}")
                if video.channel_name != "Unknown":
                    lines.append(f"   Channel: {video.channel_name}")
                if video.duration:
                    lines.append(f"   Duration: {video.duration}")
                lines.append(f"   🔗 {video.url}")
                lines.append("")
        
        lines.append("═" * 60)
        return "\n".join(lines)
    
    def _search_for_series(self, series, count: int) -> str:
        """
        Search for general series trailers.
        
        Args:
            series: Series object
            count: Number of results
            
        Returns:
            Formatted results string
        """
        
        lines = [
            "═" * 60,
            f"TRAILERS: {series.name}",
            "═" * 60,
            ""
        ]
        
        # Search YouTube for general trailers
        videos = self.youtube_scraper.search_series_trailers(
            series_name=series.name,
            max_results=count
        )
        
        if not videos:
            lines.append("No trailers found for this series.")
        else:
            lines.append(f"Found {len(videos)} video(s):\n")
            
            for i, video in enumerate(videos, 1):
                lines.append(f"{i}. {video.title}")
                if video.channel_name != "Unknown":
                    lines.append(f"   Channel: {video.channel_name}")
                if video.duration:
                    lines.append(f"   Duration: {video.duration}")
                lines.append(f"   🔗 {video.url}")
                lines.append("")
        
        lines.append("═" * 60)
        return "\n".join(lines)
    
    def _search_for_next_episode(self, count: int) -> str:
        """
        Search for trailers for the next prioritized episode.
        
        Uses the EpisodeRanker to find the next episode, then
        searches YouTube for its trailers.
        
        Args:
            count: Number of results
            
        Returns:
            Formatted results string
        """
        # Get next prioritized episode
        next_ep = self.ranker.get_next_episode()
        
        if not next_ep:
            return "[OK] All caught up! No episodes to find trailers for."
        
        lines = [
            "═" * 60,
            f"TRAILERS FOR YOUR NEXT EPISODE",
            "═" * 60,
            "",
            f"  Series: {next_ep.series_name}",
            f"  Episode: {next_ep.episode_code}: {next_ep.episode_title}",
            f"  Score: {next_ep.score}/10",
            "",
            "─" * 60,
            ""
        ]
        
        # Search YouTube
        videos = self.youtube_scraper.search_episode_videos(
            series_name=next_ep.series_name,
            episode_code=next_ep.episode_code,
            episode_title=next_ep.episode_title if next_ep.episode_title != "Unknown" else None,
            max_results=count
        )
        
        if not videos:
            lines.append("No trailers found for this episode.")
        else:
            lines.append(f"Found {len(videos)} video(s):\n")
            
            for i, video in enumerate(videos, 1):
                lines.append(f"{i}. {video.title}")
                if video.channel_name != "Unknown":
                    lines.append(f"   Channel: {video.channel_name}")
                lines.append(f"   🔗 {video.url}")
                lines.append("")
        
        lines.append("═" * 60)
        return "\n".join(lines)
    
    def get_help(self):
        """Return help text for trailers command."""
        return '''
Search YouTube for trailers and clips related to your series.

Usage: trailers [options] <series> [episode_code]

Arguments:
  series         Series name (in quotes) or IMDB ID
  episode_code   Episode code (e.g., S01E04)

Options:
  --next, -n            Find trailers for your next prioritized episode
  --count N, -c N       Number of results (default: 5)

Examples:
  trailers "Breaking Bad" S01E04    Find trailers for specific episode
  trailers tt0903747 S01E04         Same, using IMDB ID
  trailers "Game of Thrones"        Find general series trailers
  trailers --next                   Trailers for next episode to watch

Output includes video title, channel, and YouTube URL.
        '''
