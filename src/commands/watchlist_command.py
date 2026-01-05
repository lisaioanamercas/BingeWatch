"""
Watchlist Command - "What Should I Watch Next?"

This command is the user-facing interface for Phase 3's ranking functionality.
It displays ALL new episodes across ALL series, sorted by priority.

DIFFERENCE FROM 'list' COMMAND:
================================
- 'list' shows series one by one with their episodes beneath
- 'watchlist' shows a unified, ranked list of ALL new episodes

Example Output:
---------------
    📺 YOUR WATCHLIST (47 episodes to watch)
    ═══════════════════════════════════════════
    
    #1  [10/10] Game of Thrones - S01E02: The Kingsroad
    #2  [10/10] Game of Thrones - S01E03: Lord Snow
    #3  [9/10]  Breaking Bad - S03E01: No Más
    #4  [9/10]  Breaking Bad - S03E02: Caballo Sin Nombre
    #5  [7/10]  The Office - S02E05: Halloween
    ...

COMMAND OPTIONS:
================
- --top N: Show only top N episodes (default: show all)
- --min-score N: Only include series with score >= N
- --next: Show only the single next episode to watch

USAGE EXAMPLES:
===============
    watchlist              # Show full ranked watchlist
    watchlist --top 10     # Show top 10 priority episodes
    watchlist --min-score 8  # Only show episodes from 8+ scored series
    watchlist --next       # Just tell me what to watch next
"""

from .base import Command
from ..services.episode_ranker import EpisodeRanker


class WatchlistCommand(Command):
    """
    Command to display prioritized watchlist of new episodes.
    
    This command leverages the EpisodeRanker service to:
    1. Fetch new episodes from all non-snoozed series
    2. Rank them by series score (descending)
    3. Display in a clean, prioritized format
    
    The output helps users answer: "What should I watch next?"
    """
    
    def __init__(self, db_manager):
        """
        Initialize with database manager.
        
        The EpisodeRanker is created fresh for each command execution
        to ensure it has the latest database state.
        """
        super().__init__(db_manager)
        self.ranker = EpisodeRanker(db_manager)
    
    def execute(self, args):
        """
        Execute the watchlist command.
        
        Parses arguments and displays prioritized episode list.
        
        Args:
            args: Command arguments (--top, --min-score, --next)
            
        Returns:
            str: Formatted watchlist output
        """
        try:
            # Parse arguments
            top_n = self._parse_int_arg(args, '--top', '-t')
            min_score = self._parse_int_arg(args, '--min-score', '-s')
            show_next_only = '--next' in args or '-n' in args
            
            # Handle --next flag (show single episode)
            if show_next_only:
                return self._format_next_episode()
            
            # Get full prioritized watchlist
            watchlist = self.ranker.get_prioritized_watchlist(
                min_score=min_score,
                max_results=top_n
            )
            
            return self._format_watchlist(watchlist, top_n, min_score)
        
        except Exception as e:
            error_msg = f"Failed to generate watchlist: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
    
    def _parse_int_arg(self, args, long_flag, short_flag):
        """
        Parse an integer argument from command args.
        
        Handles both formats:
            --top 10
            -t 10
            
        Args:
            args: List of command arguments
            long_flag: Long form (e.g., '--top')
            short_flag: Short form (e.g., '-t')
            
        Returns:
            int value or None if not found
        """
        for flag in [long_flag, short_flag]:
            if flag in args:
                try:
                    idx = args.index(flag)
                    if idx + 1 < len(args):
                        return int(args[idx + 1])
                except (ValueError, IndexError):
                    pass
        return None
    
    def _format_next_episode(self) -> str:
        """
        Format output for --next flag (single episode recommendation).
        
        Returns:
            Formatted string with next episode to watch
        """
        next_ep = self.ranker.get_next_episode()
        
        if not next_ep:
            return "✓ All caught up! No new episodes to watch."
        
        lines = [
            "═" * 60,
            "📺 NEXT UP",
            "═" * 60,
            "",
            f"  {next_ep.series_name}",
            f"  {next_ep.episode_code}: {next_ep.episode_title}",
            f"  Score: {next_ep.score}/10",
        ]
        
        if next_ep.air_date:
            lines.append(f"  Aired: {next_ep.air_date}")
        
        lines.extend([
            "",
            "═" * 60,
            "Tip: Use 'update episode <imdb_id> <episode>' after watching"
        ])
        
        return "\n".join(lines)
    
    def _format_watchlist(self, watchlist, top_n, min_score) -> str:
        """
        Format the complete prioritized watchlist.
        
        Creates a visually appealing ranked list showing:
        - Rank number
        - Series score
        - Series name
        - Episode code and title
        - Air date (if available)
        
        Args:
            watchlist: List of PrioritizedEpisode objects
            top_n: Max results limit (for display message)
            min_score: Minimum score filter (for display message)
            
        Returns:
            Formatted watchlist string
        """
        if not watchlist:
            # Provide helpful message when empty
            if min_score:
                return f"No new episodes from series with score >= {min_score}."
            return "✓ All caught up! No new episodes to watch."
        
        lines = []
        
        # Header
        lines.append("═" * 70)
        lines.append(f"📺 YOUR WATCHLIST ({len(watchlist)} episodes to watch)")
        
        # Show active filters
        filters = []
        if top_n:
            filters.append(f"top {top_n}")
        if min_score:
            filters.append(f"score >= {min_score}")
        if filters:
            lines.append(f"   Filters: {', '.join(filters)}")
        
        lines.append("═" * 70)
        lines.append("")
        
        # Group by score for visual clarity
        current_score = None
        
        for ep in watchlist:
            # Add score separator when score changes
            if ep.score != current_score:
                if current_score is not None:
                    lines.append("")  # Blank line between score groups
                lines.append(f"── Score: {ep.score}/10 ──")
                current_score = ep.score
            
            # Format episode line
            # Rank is right-padded, series name is also padded for alignment
            rank_str = f"#{ep.priority_rank:>3}"
            
            # Build episode info
            ep_info = f"{ep.series_name} - {ep.episode_code}"
            if ep.episode_title and ep.episode_title != "Unknown":
                ep_info += f": {ep.episode_title}"
            
            lines.append(f"{rank_str}  {ep_info}")
            
            # Show air date on separate line for longer entries
            if ep.air_date:
                lines.append(f"        Aired: {ep.air_date}")
        
        # Footer
        lines.append("")
        lines.append("═" * 70)
        
        # Summary stats
        series_names = set(ep.series_name for ep in watchlist)
        lines.append(f"📊 {len(watchlist)} episodes across {len(series_names)} series")
        
        # Tips
        lines.append("")
        lines.append("Tips:")
        lines.append("  • Use 'watchlist --top 10' to see only top 10")
        lines.append("  • Use 'watchlist --next' for single recommendation")
        lines.append("  • Use 'update episode <imdb_id> <code>' after watching")
        
        return "\n".join(lines)
    
    def get_help(self):
        """Return help text for watchlist command."""
        return """
Display prioritized watchlist of new episodes across all series.

Episodes are ranked by:
  1. Series score (higher scores first)
  2. Episode order (earlier episodes first)

Usage: watchlist [options]

Options:
  --top N, -t N         Show only top N episodes
  --min-score N, -s N   Only include series with score >= N
  --next, -n            Show only the next episode to watch

Examples:
  watchlist                  Show full ranked watchlist
  watchlist --top 10         Show top 10 priority episodes
  watchlist -s 8             Only show 8+ scored series
  watchlist --next           What should I watch next?
  watchlist -t 5 -s 7        Top 5 from series scored 7+

Output shows episodes ranked by priority:
  #1  [10/10] Game of Thrones - S01E02: The Kingsroad
  #2  [9/10]  Breaking Bad - S03E01: No Más
  ...
        """
