"""
Update command implementation.
Handles updating series properties (score, snooze, last episode).
"""

from .base import Command
from ..utils.validators import (
    validate_imdb_link,
    validate_score,
    validate_episode_format,
    ValidationError
)


class UpdateCommand(Command):
    """Command to update series properties."""
    
    def execute(self, args):
        """
        Update series properties.
        
        Args:
            args: List containing [action, imdb_id_or_link, value (optional)]
            
        Returns:
            str: Success or failure message
        """
        try:
            # Validate minimum argument count
            if len(args) < 2:
                return "✗ Usage: update <action> <imdb_id_or_link> [value]"
            
            action = args[0].lower()
            imdb_link = args[1]
            
            # Validate IMDB ID
            validated_imdb_id = validate_imdb_link(imdb_link)
            
            # Check if series exists
            series = self.db_manager.get_series(validated_imdb_id)
            if not series:
                return f"✗ Series with IMDB ID {validated_imdb_id} not found"
            
            # Route to appropriate action handler
            if action == "score":
                return self._update_score(series, args)
            elif action == "snooze":
                return self._snooze_series(series)
            elif action == "unsnooze":
                return self._unsnooze_series(series)
            elif action == "episode":
                return self._update_episode(series, args)
            else:
                return f"✗ Unknown action: {action}. Use: score, snooze, unsnooze, or episode"
        
        except ValidationError as e:
            error_msg = f"Validation error: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
        
        except ValueError as e:
            error_msg = str(e)
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
        
        except Exception as e:
            error_msg = f"Failed to update series: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
    
    def _update_score(self, series, args):
        """Update series score."""
        if len(args) < 3:
            return "✗ Usage: update score <imdb_id_or_link> <new_score>"
        
        new_score = validate_score(args[2])
        updated = self.db_manager.update_score(series.imdb_id, new_score)
        
        if updated:
            return (
                f"✓ Successfully updated score for '{series.name}':\n"
                f"  Old score: {series.score}/10\n"
                f"  New score: {new_score}/10"
            )
        return f"✗ Failed to update score for {series.imdb_id}"
    
    def _snooze_series(self, series):
        """Snooze a series."""
        if series.snoozed:
            return f"⚠ Series '{series.name}' is already snoozed"
        
        updated = self.db_manager.update_snooze(series.imdb_id, True)
        
        if updated:
            return f"✓ Snoozed series: {series.name}"
        return f"✗ Failed to snooze series {series.imdb_id}"
    
    def _unsnooze_series(self, series):
        """Unsnooze a series."""
        if not series.snoozed:
            return f"⚠ Series '{series.name}' is not snoozed"
        
        updated = self.db_manager.update_snooze(series.imdb_id, False)
        
        if updated:
            return f"✓ Unsnoozed series: {series.name}"
        return f"✗ Failed to unsnooze series {series.imdb_id}"
    
    def _update_episode(self, series, args):
        """Update last watched episode."""
        if len(args) < 3:
            return "✗ Usage: update episode <imdb_id_or_link> <episode>"
        
        episode_str = args[2]
        season, episode = validate_episode_format(episode_str)
        episode_code = f"S{season:02d}E{episode:02d}"
        
        updated = self.db_manager.update_last_episode(series.imdb_id, episode_code)
        
        if updated:
            return (
                f"✓ Successfully updated last episode for '{series.name}':\n"
                f"  Old: {series.last_episode}\n"
                f"  New: {episode_code}"
            )
        return f"✗ Failed to update episode for {series.imdb_id}"
    
    def get_help(self):
        """Return help text for update command."""
        return """
Update series properties.

Usage: update <action> <imdb_id_or_link> [value]

Actions:
  score             Update user score (requires value 1-10)
  snooze            Mark series as snoozed (no new value needed)
  unsnooze          Remove snooze status (no new value needed)
  episode           Update last watched episode (requires episode code)

Examples:
  update score tt0903747 8
  update snooze tt0306414
  update unsnooze tt4574334
  update episode tt0903747 S03E07
  update episode tt0306414 2x5
        """