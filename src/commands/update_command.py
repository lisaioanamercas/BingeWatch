"""
Update command implementation.
Handles updating series properties (score, snooze, last episode).

Phase 6 Enhancement: Detailed operation logging.
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
        with self.log_op("Update series", args=args) as op:
            try:
                # Validate minimum argument count
                if len(args) < 2:
                    return (
                        self.error_msg("Missing required arguments") + "\n\n"
                        "Usage: update <action> <imdb_id_or_link> [value]\n\n"
                        "Actions:\n"
                        "  score <id> <1-10>     Update rating\n"
                        "  snooze <id>           Pause notifications\n"
                        "  unsnooze <id>         Resume notifications\n"
                        "  episode <id> <S01E01> Mark episode as watched"
                    )
                
                action = args[0].lower()
                imdb_link = args[1]
                
                # Validate IMDB ID
                validated_imdb_id = validate_imdb_link(imdb_link)
                
                op.debug(f"Action: {action}, IMDB: {validated_imdb_id}")
                
                # Check if series exists
                series = self.db_manager.get_series(validated_imdb_id)
                if not series:
                    return (
                        self.error_msg(f"Series with IMDB ID '{validated_imdb_id}' not found") + "\n\n"
                        "Use 'list' to see your tracked series\n"
                        "Use 'add' to add a new series first"
                    )
                
                # Route to appropriate action handler
                if action == "score":
                    return self._update_score(series, args, op)
                elif action == "snooze":
                    return self._snooze_series(series, op)
                elif action == "unsnooze":
                    return self._unsnooze_series(series, op)
                elif action == "episode":
                    return self._update_episode(series, args, op)
                else:
                    return (
                        self.error_msg(f"Unknown action: {action}") + "\n\n"
                        "Valid actions: score, snooze, unsnooze, episode"
                    )
            
            except ValidationError as e:
                op.error(str(e))
                return self.error_msg(f"Validation error: {e}")
            
            except ValueError as e:
                op.error(str(e))
                return self.error_msg(str(e))
            
            except Exception as e:
                op.error(str(e))
                return self.error_msg(f"Failed to update series: {e}")
    
    def _update_score(self, series, args, op):
        """Update series score."""
        if len(args) < 3:
            return (
                self.error_msg("Missing score value") + "\n\n"
                "Usage: update score <imdb_id> <1-10>"
            )
        
        new_score = validate_score(args[2])
        old_score = series.score
        updated = self.db_manager.update_score(series.imdb_id, new_score)
        
        if updated:
            op.success(f"Updated score: {old_score} → {new_score}")
            return (
                self.success_msg(f"Updated score for '{series.name}':") + "\n"
                f"  {old_score}/10  →  {new_score}/10"
            )
        op.error("Database update failed")
        return self.error_msg(f"Failed to update score for {series.imdb_id}")
    
    def _snooze_series(self, series, op):
        """Snooze a series."""
        if series.snoozed:
            return self.warning_msg(f"Series '{series.name}' is already snoozed")
        
        updated = self.db_manager.update_snooze(series.imdb_id, True)
        
        if updated:
            op.success(f"Snoozed '{series.name}'")
            return (
                self.success_msg(f"Snoozed: {series.name}") + "\n\n"
                "ℹ This series will be excluded from 'episodes' and 'check' commands.\n"
                "  Use 'update unsnooze' to resume notifications."
            )
        op.error("Database update failed")
        return self.error_msg(f"Failed to snooze series {series.imdb_id}")
    
    def _unsnooze_series(self, series, op):
        """Unsnooze a series."""
        if not series.snoozed:
            return self.warning_msg(f"Series '{series.name}' is not snoozed")
        
        updated = self.db_manager.update_snooze(series.imdb_id, False)
        
        if updated:
            op.success(f"Unsnoozed '{series.name}'")
            return (
                self.success_msg(f"Unsnoozed: {series.name}") + "\n\n"
                "ℹ This series will now appear in 'episodes' and 'check' commands."
            )
        op.error("Database update failed")
        return self.error_msg(f"Failed to unsnooze series {series.imdb_id}")
    
    def _update_episode(self, series, args, op):
        """Update last watched episode."""
        if len(args) < 3:
            return (
                self.error_msg("Missing episode code") + "\n\n"
                "Usage: update episode <imdb_id> <episode>\n\n"
                "Formats accepted: S01E05, 1x5, s1e5"
            )
        
        episode_str = args[2]
        season, episode = validate_episode_format(episode_str)
        episode_code = f"S{season:02d}E{episode:02d}"
        old_episode = series.last_episode
        
        updated = self.db_manager.update_last_episode(series.imdb_id, episode_code)
        
        if updated:
            op.success(f"Updated episode: {old_episode} → {episode_code}")
            return (
                self.success_msg(f"Updated last episode for '{series.name}':") + "\n"
                f"  {old_episode}  →  {episode_code}\n\n"
                "ℹ Episodes after this will now appear in 'episodes' command."
            )
        op.error("Database update failed")
        return self.error_msg(f"Failed to update episode for {series.imdb_id}")
    
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