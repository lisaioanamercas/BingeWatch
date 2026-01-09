"""
Check Command - Scan for New Videos and Display Notifications.

This command runs the full notification workflow:
1. Scan all tracked series for new episodes
2. Search YouTube for related videos
3. Compare against previously found videos
4. Display notifications for NEW discoveries only

DIFFERENCE FROM 'trailers' COMMAND:
===================================
- 'trailers': Shows ALL videos found (cached or not)
- 'check': Shows only NEW videos since last check

'check' is for regular monitoring: "What's new since I last looked?"
'trailers' is for browsing: "Show me all trailers for this episode"

WORKFLOW:
=========
First time running 'check':
    → All found videos are cached
    → All are displayed as "new"

Subsequent runs:
    → Only videos NOT in cache are displayed
    → Cache is updated with new findings

COMMAND OPTIONS:
================
- check                Show new videos across all series
- check --series ID    Check specific series only
- check --stats        Show cache statistics
- check --clear        Clear the video cache
"""

from typing import Optional
from .base import Command
from ..services.notification_service import NotificationService


class CheckCommand(Command):
    """
    Command to check for new YouTube videos and display notifications.
    
    This command uses the NotificationService to:
    1. Check all series for new episodes
    2. Search YouTube for related content
    3. Compare against cache for NEW content
    4. Display consolidated notifications
    """
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        super().__init__(db_manager)
        self.notification_service = NotificationService(db_manager)
    
    def execute(self, args):
        """
        Execute the check command.
        
        Args:
            args: Command arguments
                - (none): Check all series
                - --series ID: Check specific series
                - --stats: Show cache statistics
                - --clear: Clear video cache
                - --min-score N: Only check series with score >= N
        
        Returns:
            str: Notification output
        """
        try:
            # Handle special flags
            if '--stats' in args:
                return self._show_stats()
            
            if '--clear' in args:
                return self._clear_cache(args)
            
            # Parse options
            series_id = self._parse_string_arg(args, '--series', '-s')
            min_score = self._parse_int_arg(args, '--min-score', '-m')
            
            # Run appropriate check
            if series_id:
                return self._check_series(series_id)
            else:
                return self._check_all(min_score)
        
        except Exception as e:
            error_msg = f"Failed to check for new videos: {e}"
            self.logger.error(error_msg)
            return f"[ERROR] {error_msg}"
    
    def _parse_string_arg(self, args, long_flag, short_flag) -> Optional[str]:
        """Parse a string argument from command args."""
        for flag in [long_flag, short_flag]:
            if flag in args:
                try:
                    idx = args.index(flag)
                    if idx + 1 < len(args):
                        return args[idx + 1]
                except (ValueError, IndexError):
                    pass
        return None
    
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
    
    def _check_all(self, min_score: Optional[int]) -> str:
        """
        Check all series for new videos.
        
        Args:
            min_score: Minimum series score to check
            
        Returns:
            Formatted notification output
        """
        lines = [
            "═" * 60,
            "CHECKING FOR NEW VIDEOS...",
            "═" * 60,
            ""
        ]
        
        # Run the check
        notifications = self.notification_service.check_all(
            min_score=min_score,
            max_episodes_per_series=3  # Limit to avoid rate limiting
        )
        
        if not notifications:
            lines.append("[OK] No new videos found since last check.")
            lines.append("")
            lines.append("Tip: Videos are cached after first discovery.")
            lines.append("     Run 'check --clear' to reset the cache.")
        else:
            # Count totals
            total_new = sum(n.count for n in notifications)
            lines.append(f"Found {total_new} new video(s)!\n")
            
            # Group by series for cleaner output
            current_series = None
            
            for notif in notifications:
                # Add series header if new series
                if notif.series_name != current_series:
                    if current_series is not None:
                        lines.append("")  # Blank between series
                    lines.append(f"[{notif.series_name}]")
                    lines.append("─" * 40)
                    current_series = notif.series_name
                
                # Show episode and its new videos
                if notif.episode_code != 'general':
                    lines.append(f"  {notif.episode_code}:")
                else:
                    lines.append("  General trailers:")
                
                for video in notif.new_videos:
                    # Truncate long titles
                    title = video.title
                    if len(title) > 45:
                        title = title[:42] + "..."
                    lines.append(f"    • {title}")
                    lines.append(f"      {video.url}")
        
        lines.append("")
        lines.append("═" * 60)
        
        # Add timestamp
        from datetime import datetime
        lines.append(f"Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(lines)
    
    def _check_series(self, imdb_id: str) -> str:
        """
        Check a specific series for new videos.
        
        Args:
            imdb_id: IMDB ID of the series
            
        Returns:
            Formatted notification output
        """
        # Get series info
        series = self.db_manager.get_series(imdb_id)
        if not series:
            return f"[ERROR] Series with IMDB ID '{imdb_id}' not found.\n  Use 'add' command first."
        
        lines = [
            "═" * 60,
            f"CHECKING: {series.name}",
            "═" * 60,
            ""
        ]
        
        notifications = self.notification_service.check_series(imdb_id)
        
        if not notifications:
            lines.append("[OK] No new videos found for this series.")
        else:
            total_new = sum(n.count for n in notifications)
            lines.append(f"Found {total_new} new video(s)!\n")
            
            for notif in notifications:
                if notif.episode_code != 'general':
                    lines.append(f"  {notif.episode_code}:")
                else:
                    lines.append("  General trailers:")
                
                for video in notif.new_videos:
                    lines.append(f"    • {video.title}")
                    lines.append(f"      {video.url}")
                lines.append("")
        
        lines.append("═" * 60)
        return "\n".join(lines)
    
    def _show_stats(self) -> str:
        """Show cache statistics."""
        stats = self.notification_service.get_cache_stats()
        
        lines = [
            "═" * 60,
            "VIDEO CACHE STATISTICS",
            "═" * 60,
            "",
            f"  Cache entries: {stats['total_entries']}",
            f"  Total videos tracked: {stats['total_videos']}",
            f"  Cache file: {stats['cache_path']}",
            "",
            "═" * 60
        ]
        
        return "\n".join(lines)
    
    def _clear_cache(self, args) -> str:
        """Clear the video cache."""
        # Check if clearing specific series
        series_id = self._parse_string_arg(args, '--series', '-s')
        
        if series_id:
            series = self.db_manager.get_series(series_id)
            if series:
                self.notification_service.clear_cache(series.name)
                return f"[OK] Cleared cache for {series.name}"
            return f"[ERROR] Series {series_id} not found"
        
        self.notification_service.clear_cache()
        return "[OK] Video cache cleared. Next check will treat all videos as new."
    
    def get_help(self):
        """Return help text for check command."""
        return """
Check for new YouTube videos across all tracked series.

Only shows videos that are NEW since your last check.
Previously found videos are cached and not repeated.

Usage: check [options]

Options:
  --series ID, -s ID    Check specific series only
  --min-score N, -m N   Only check series with score >= N
  --stats               Show cache statistics
  --clear               Clear the video cache

Examples:
  check                      Check all series for new videos
  check --series tt0903747   Check specific series
  check --min-score 8        Only check high-rated series
  check --stats              View cache info
  check --clear              Reset cache (all videos = "new")

How it works:
  1. First run: All found videos are treated as "new"
  2. Next runs: Only truly new videos are shown
  3. Use --clear to start fresh
        """
