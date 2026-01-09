"""
List command implementation.
Displays series and their new episodes.
"""

from .base import Command
from ..scrapers.imdb_scraper import IMDBScraper


class ListCommand(Command):
    """Command to list series and check for new episodes."""
    
    def __init__(self, db_manager):
        """Initialize with database manager and scraper."""
        super().__init__(db_manager)
        self.scraper = IMDBScraper()
    
    def execute(self, args):
        """
        List all series or check for new episodes.
        
        Args:
            args: List containing optional flags ['--check-episodes', '--all']
            
        Returns:
            str: Formatted list of series
        """
        try:
            # Parse flags
            check_episodes = '--check-episodes' in args or '-e' in args
            include_snoozed = '--all' in args or '-a' in args
            
            # Get series from database
            series_list = self.db_manager.get_all_series(include_snoozed=include_snoozed)
            
            if not series_list:
                return "No series found in database. Use 'add' command to add series."
            
            # Build output
            output_lines = []
            output_lines.append("=" * 70)
            output_lines.append(f"YOUR TV SERIES ({len(series_list)} total)")
            output_lines.append("=" * 70)
            
            for idx, series in enumerate(series_list, 1):
                output_lines.append(f"\n{idx}. {series.name}")
                output_lines.append(f"   IMDB: {series.imdb_id} | Score: {series.score}/10")
                output_lines.append(f"   Last watched: {series.last_episode}")
                
                if series.snoozed:
                    output_lines.append("   Status: [SNOOZED]")
                
                # Check for new episodes if requested
                if check_episodes and not series.snoozed:
                    output_lines.append("   Checking for new episodes...")
                    try:
                        new_episodes = self.scraper.get_new_episodes(
                            series.imdb_id,
                            series.last_episode
                        )
                        
                        if new_episodes:
                            output_lines.append(f"   [+] {len(new_episodes)} new episode(s) available!")
                            # Show first 3 new episodes
                            for ep in new_episodes[:3]:
                                output_lines.append(f"      • {ep}")
                            if len(new_episodes) > 3:
                                output_lines.append(f"      ... and {len(new_episodes) - 3} more")
                        else:
                            output_lines.append("   [*] No new episodes")
                    
                    except Exception as e:
                        output_lines.append(f"   [ERROR] Error checking episodes: {e}")
                        self.logger.error(f"Error checking {series.imdb_id}: {e}")
            
            output_lines.append("\n" + "=" * 70)
            
            if not check_episodes:
                output_lines.append("Tip: Use '--check-episodes' or '-e' to check for new episodes")
            
            if not include_snoozed:
                snoozed_count = len([s for s in self.db_manager.get_all_series(True) if s.snoozed])
                if snoozed_count > 0:
                    output_lines.append(f"Note: {snoozed_count} snoozed series hidden. Use '--all' or '-a' to show all")
            
            return "\n".join(output_lines)
        
        except Exception as e:
            error_msg = f"Failed to list series: {e}"
            self.logger.error(error_msg)
            return f"[ERROR] {error_msg}"
    
    def get_help(self):
        """Return help text for list command."""
        return """
List all tracked series and optionally check for new episodes.

Usage: list [options]

Options:
  --check-episodes, -e    Check IMDB for new episodes
  --all, -a               Include snoozed series

Examples:
  list                    Show all active series
  list -e                 Show series and check for new episodes
  list --all              Show all series including snoozed
  list -e -a              Check episodes for all series
        """