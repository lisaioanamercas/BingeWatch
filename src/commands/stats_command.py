"""
Stats Command - Dashboard Statistics Display.

Shows a quick overview of your BingeWatch data.

DESIGN PATTERNS USED:
=====================
1. Command Pattern - Inherits from Command base class, encapsulating
   the stats operation as an object with execute() method.
2. Facade Pattern - Provides a simplified interface to multiple
   subsystems (database, cache, notifications).

FEATURES:
=========
- Series count (active vs snoozed)
- Video cache statistics
- Top-rated series
- Last activity timestamps
"""

from datetime import datetime
from typing import Optional

from .base import Command
from ..services.video_cache import VideoCache


class StatsCommand(Command):
    """
    Command to display dashboard statistics.
    
    Aggregates data from multiple sources to provide
    a quick overview of tracking status.
    """
    
    def __init__(self, db_manager):
        """Initialize with database manager and cache."""
        super().__init__(db_manager)
        self.video_cache = VideoCache()
    
    def execute(self, args):
        """
        Display statistics dashboard.
        
        Args:
            args: Optional arguments
                --cache: Show detailed cache info
                --series: Show series breakdown
                
        Returns:
            str: Formatted statistics output
        """
        show_cache = '--cache' in args or '-c' in args
        show_series = '--series' in args or '-s' in args
        
        lines = [
            self.header("BingeWatch Statistics"),
            ""
        ]
        
        # Series Statistics
        all_series = self.db_manager.get_all_series(include_snoozed=True)
        active_series = [s for s in all_series if not s.snoozed]
        snoozed_series = [s for s in all_series if s.snoozed]
        
        lines.append("SERIES")
        lines.append(self.divider(40))
        lines.append(f"  Total tracked:    {len(all_series)}")
        lines.append(f"  Active:           {len(active_series)}")
        lines.append(f"  Snoozed:          {len(snoozed_series)}")
        lines.append("")
        
        # Score Distribution
        if all_series:
            avg_score = sum(s.score for s in all_series) / len(all_series)
            top_rated = sorted(all_series, key=lambda s: s.score, reverse=True)[:3]
            
            lines.append(f"  Average score:    {avg_score:.1f}/10")
            lines.append("")
            lines.append("  Top Rated:")
            for i, series in enumerate(top_rated, 1):
                snoozed = " [SNOOZED]" if series.snoozed else ""
                lines.append(f"     {i}. {series.name} ({series.score}/10){snoozed}")
            lines.append("")
        
        # Cache Statistics
        cache_stats = self.video_cache.get_stats()
        
        lines.append("VIDEO CACHE")
        lines.append(self.divider(40))
        lines.append(f"  Entries tracked:  {cache_stats['total_entries']}")
        lines.append(f"  Videos found:     {cache_stats['total_videos']}")
        
        # Get cache freshness info
        cache_entries = self.video_cache.get_all_entries()
        if cache_entries:
            # Find most recent check
            last_checks = []
            for key, entry in cache_entries.items():
                if 'last_checked' in entry:
                    try:
                        last_checks.append(datetime.fromisoformat(entry['last_checked']))
                    except (ValueError, TypeError):
                        pass
            
            if last_checks:
                most_recent = max(last_checks)
                age = self._format_time_ago(most_recent)
                lines.append(f"  Last check:       {age}")
                
                # Count stale entries (older than 7 days)
                stale_count = self.video_cache.count_stale_entries(days=7)
                if stale_count > 0:
                    lines.append(f"  Stale entries:    {stale_count} (>7 days old)")
        
        lines.append("")
        
        # Detailed cache info if requested
        if show_cache and cache_entries:
            lines.append("  Cache Breakdown:")
            for key, entry in sorted(cache_entries.items())[:10]:
                video_count = len(entry.get('video_ids', []))
                last_check = entry.get('last_checked', 'unknown')
                if last_check != 'unknown':
                    try:
                        dt = datetime.fromisoformat(last_check)
                        last_check = self._format_time_ago(dt)
                    except (ValueError, TypeError):
                        pass
                lines.append(f"     • {key}: {video_count} videos ({last_check})")
            
            if len(cache_entries) > 10:
                lines.append(f"     ... and {len(cache_entries) - 10} more")
            lines.append("")
        
        # Series breakdown if requested
        if show_series and all_series:
            lines.append("ALL SERIES")
            lines.append(self.divider(40))
            for series in sorted(all_series, key=lambda s: s.score, reverse=True):
                status = "[Z]" if series.snoozed else "[*]"
                lines.append(f"  {status} {series.name}")
                lines.append(f"     Score: {series.score}/10 | Last: {series.last_episode}")
            lines.append("")
        
        # Quick tips
        lines.append("QUICK ACTIONS")
        lines.append(self.divider(40))
        lines.append("  • Run 'check' to scan for new trailers")
        lines.append("  • Run 'episodes' to see what's new")
        lines.append("  • Run 'stats --cache' for cache details")
        
        return "\n".join(lines)
    
    def _format_time_ago(self, dt: datetime) -> str:
        """Format a datetime as a human-readable 'time ago' string."""
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    
    def get_help(self):
        """Return help text for stats command."""
        return """
Display BingeWatch statistics and dashboard.

Usage:
  stats              Show general statistics
  stats --cache      Include detailed cache breakdown  
  stats --series     Include full series list

Shows:
  • Series count (active/snoozed)
  • Average score and top-rated series
  • Video cache status and freshness
  • Quick action suggestions

Examples:
  stats
  stats --cache
  stats -c -s
        """
