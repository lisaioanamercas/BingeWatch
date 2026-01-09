"""
Episodes Command - Afiseaza toate episoadele noi.

DESIGN PATTERNS:
================
1. COMMAND PATTERN - Mosteneste din Command, implementeaza execute()
2. DECORATOR PATTERN - Flag-urile (--debug, --verbose) modifica comportamentul

RESPONSABILITATI:
=================
- Listeaza episoade noi de la toate seriile
- Grupeaza dupa serie pentru afisare curata
- Filtreaza dupa scor minim si status snooze
- Suporta mod debug pentru prezentari
"""


from typing import Optional, List
from datetime import datetime
from .base import Command
from ..services.episode_ranker import EpisodeRanker, PrioritizedEpisode
from ..utils.logger import log_operation, is_verbose


class EpisodesCommand(Command):
    """
    Command to list all new episodes across all tracked series.
    
    This is the main "show me what's new" command for Phase 6.
    It excludes snoozed series by default and sorts by score.
    """
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        super().__init__(db_manager)
        self.ranker = EpisodeRanker(db_manager)
    
    def execute(self, args: list) -> str:
        """
        Execute the episodes command.
        
        Args:
            args: Command arguments
                - --all, -a: Include snoozed series
                - --min-score N, -m N: Minimum series score
                - --top N, -t N: Limit results
                - --verbose, -v: Show detailed information
        
        Returns:
            str: Formatted list of new episodes
        """
        with log_operation("Listing episodes", args=args) as op:
            try:
                # Parse arguments
                include_snoozed = '--all' in args or '-a' in args
                verbose = '--verbose' in args or '-v' in args
                debug_mode = '--debug' in args or '-d' in args
                min_score = self._parse_int_arg(args, '--min-score', '-m')
                top_n = self._parse_int_arg(args, '--top', '-t')
                
                # Detecteaza filtru dupa nume serie (primul argument care nu e flag)
                series_filter = self._parse_series_filter(args)
                
                # Enable verbose logging if debug mode
                if debug_mode:
                    from ..utils.logger import set_verbose
                    set_verbose(True)
                
                # Get episodes from ranker
                op.debug("Fetching prioritized watchlist...")
                episodes = self.ranker.get_prioritized_watchlist(
                    include_snoozed=include_snoozed,
                    min_score=min_score,
                    max_results=None  # Aplica limita dupa filtrare
                )
                
                # Filtreaza dupa serie daca e specificat
                if series_filter:
                    episodes = [
                        ep for ep in episodes 
                        if series_filter.lower() in ep.series_name.lower()
                    ]
                    op.debug(f"Filtered to series matching '{series_filter}': {len(episodes)} episodes")
                
                # Aplica limita top_n dupa filtrare
                if top_n and episodes:
                    episodes = episodes[:top_n]
                
                if not episodes:
                    return self._format_no_episodes(include_snoozed, min_score, series_filter)
                
                # Format output
                result = self._format_episodes(
                    episodes, 
                    include_snoozed, 
                    min_score, 
                    top_n,
                    verbose,
                    series_filter
                )
                
                op.success(f"Found {len(episodes)} new episode(s)")
                return result
            
            except Exception as e:
                op.error(str(e))
                return f"[ERROR] Failed to list episodes: {e}"
    
    def _parse_int_arg(self, args: list, long_flag: str, short_flag: str) -> Optional[int]:
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
    
    def _parse_series_filter(self, args: list) -> Optional[str]:
        """Extrage numele seriei din argumente (primul arg care nu e flag)."""
        flags = ['--all', '-a', '--verbose', '-v', '--debug', '-d', 
                 '--min-score', '-m', '--top', '-t']
        skip_next = False
        
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg in ['--min-score', '-m', '--top', '-t']:
                skip_next = True
                continue
            if arg not in flags and not arg.startswith('-'):
                return arg
        return None
    
    def _format_no_episodes(self, include_snoozed: bool, min_score: Optional[int], series_filter: Optional[str] = None) -> str:
        """Format message when no episodes are found."""
        lines = [
            "═" * 60,
            "NEW EPISODES",
            "═" * 60,
            "",
            "[OK] You're all caught up! No new episodes found.",
            ""
        ]
        
        # Add helpful hints
        if not include_snoozed:
            snoozed_count = len([s for s in self.db_manager.get_all_series(True) if s.snoozed])
            if snoozed_count > 0:
                lines.append(f"[INFO] {snoozed_count} snoozed series hidden. Use '--all' to include them.")
        
        if min_score:
            lines.append(f"[INFO] Filtering for score >= {min_score}. Try a lower score or remove filter.")
        
        if series_filter:
            lines.append(f"[INFO] No episodes found for series matching '{series_filter}'.")
        
        lines.append("")
        lines.append("Tip: Use 'add' command to track more series.")
        lines.append("═" * 60)
        
        return "\n".join(lines)
    
    def _format_episodes(
        self,
        episodes: List[PrioritizedEpisode],
        include_snoozed: bool,
        min_score: Optional[int],
        top_n: Optional[int],
        verbose: bool,
        series_filter: Optional[str] = None
    ) -> str:
        """
        Format the list of episodes for display.
        
        Args:
            episodes: List of prioritized episodes
            include_snoozed: Whether snoozed series are included
            min_score: Minimum score filter applied
            top_n: Limit applied
            verbose: Whether to show detailed information
        
        Returns:
            Formatted episode list string
        """
        lines = [
            "═" * 60,
            "NEW EPISODES",
            "═" * 60,
            ""
        ]
        
        # Summary line
        total = len(episodes)
        series_set = {ep.series_name for ep in episodes}
        lines.append(f"Found {total} new episode(s) across {len(series_set)} series")
        
        # Show active filters
        filters = []
        if series_filter:
            filters.append(f"series: '{series_filter}'")
        if min_score:
            filters.append(f"score >= {min_score}")
        if top_n:
            filters.append(f"top {top_n}")
        if not include_snoozed:
            filters.append("excluding snoozed")
        
        if filters:
            lines.append(f"Filters: {', '.join(filters)}")
        
        lines.append("")
        lines.append("─" * 60)
        lines.append("")
        
        # Group episodes by series for cleaner output
        series_episodes = {}
        for ep in episodes:
            if ep.series_name not in series_episodes:
                series_episodes[ep.series_name] = {
                    'score': ep.score,
                    'imdb_id': ep.series_imdb_id,
                    'episodes': []
                }
            series_episodes[ep.series_name]['episodes'].append(ep)
        
        # Sort series by score (highest first)
        sorted_series = sorted(
            series_episodes.items(), 
            key=lambda x: -x[1]['score']
        )
        
        # Display each series
        episode_counter = 1
        for series_name, data in sorted_series:
            lines.append(f"[{series_name}] Score: {data['score']}/10")
            if verbose:
                lines.append(f"   IMDB: {data['imdb_id']}")
            
            for ep in data['episodes']:
                episode_line = f"   {episode_counter:3}. {ep.episode_code}"
                
                if ep.episode_title and ep.episode_title != "Unknown":
                    episode_line += f" - {ep.episode_title}"
                
                lines.append(episode_line)
                
                # Additional details in verbose mode
                if verbose and ep.air_date:
                    lines.append(f"        Aired: {ep.air_date}")
                
                episode_counter += 1
            
            lines.append("")  # Blank line between series
        
        lines.append("")
        lines.append("─" * 60)
        
        # Footer
        lines.append("")
        if not include_snoozed:
            snoozed_count = len([s for s in self.db_manager.get_all_series(True) if s.snoozed])
            if snoozed_count > 0:
                lines.append(f"[INFO] {snoozed_count} snoozed series hidden. Use '--all' to show all.")
        
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("═" * 60)
        
        return "\n".join(lines)
    
    def get_help(self) -> str:
        """Return help text for episodes command."""
        return \"\"\"
List new episodes across tracked series.

Usage: 
  episodes                    Show all new episodes
  episodes \"Dark\"             Show only Dark episodes
  episodes \"Game\" --top 5     First 5 Game of Thrones episodes

Arguments:
  series_name             Optional: Filter by series name (partial match)

Options:
  --all, -a               Include snoozed series
  --min-score N, -m N     Only series with score >= N
  --top N, -t N           Limit to top N episodes
  --verbose, -v           Show IMDB IDs and air dates
  --debug, -d             Show fetching progress

Examples:
  episodes                    All new episodes
  episodes \"Dark\"             Only Dark series
  episodes --min-score 8      Only 8+ rated series
  episodes \"Game\" --top 10    Top 10 GoT episodes

Related Commands:
  list      - Show all tracked series
  watchlist - Prioritized episode recommendations
  check     - Scan for new YouTube videos
        """
