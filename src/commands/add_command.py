"""
Add command implementation.
Handles adding new series to the database.

Phase 6 Enhancement: Detailed operation logging.
"""

from datetime import datetime

from .base import Command
from ..database.models import Series
from ..utils.validators import (
    validate_series_name,
    validate_imdb_link,
    validate_score,
    ValidationError
)


class AddCommand(Command):
    """Command to add a new series to tracking."""
    
    def execute(self, args):
        """
        Add a new series to the database.
        
        Args:
            args: List containing [name, imdb_id_or_link, score (optional)]
            
        Returns:
            str: Success or failure message
        """
        with self.log_op("Add series", args=args) as op:
            try:
                # Validate argument count
                if len(args) < 2:
                    return (
                        self.error_msg("Missing required arguments") + "\n\n"
                        "Usage: add <name> <imdb_id_or_link> [score]\n\n"
                        "Examples:\n"
                        "  add \"Breaking Bad\" tt0903747 9\n"
                        "  add \"The Wire\" tt0306414"
                    )
                
                # Parse arguments
                name = args[0]
                imdb_link = args[1]
                score = 5  # Default score
                
                if len(args) >= 3:
                    score = args[2]
                
                op.debug(f"Validating inputs: name='{name}', imdb='{imdb_link}', score={score}")
                
                # Validate inputs
                validated_name = validate_series_name(name)
                validated_imdb_id = validate_imdb_link(imdb_link)
                validated_score = validate_score(score)
                
                # Create series object
                series = Series(
                    name=validated_name,
                    imdb_id=validated_imdb_id,
                    score=validated_score,
                    last_episode="S00E00",
                    last_watch_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    snoozed=0
                )
                
                op.debug(f"Adding to database...")
                
                # Add to database
                series_id = self.db_manager.add_series(series)
                
                op.success(f"Added '{validated_name}' (ID: {series_id})")
                
                return (
                    self.success_msg("Successfully added series:") + "\n"
                    f"  Name:     {validated_name}\n"
                    f"  IMDB ID:  {validated_imdb_id}\n"
                    f"  Score:    {validated_score}/10\n\n"
                    "Next steps:\n"
                    f"  • Use 'episodes' to see new episodes\n"
                    f"  • Use 'update episode {validated_imdb_id} S01E01' to mark watched"
                )
            
            except ValidationError as e:
                op.error(f"Validation: {e}")
                if "IMDB" in str(e):
                    return (
                        self.error_msg(f"Invalid IMDB ID: {e}") + "\n\n"
                        "The IMDB ID should look like: tt0903747\n"
                        "You can find it in the URL: imdb.com/title/tt0903747/"
                    )
                return self.error_msg(f"Validation error: {e}")
            
            except ValueError as e:
                op.error(str(e))
                if "already exists" in str(e).lower():
                    return (
                        self.error_msg("Series already exists in database") + "\n\n"
                        "Use 'list' to see your tracked series\n"
                        "Use 'delete <imdb_id>' to remove and re-add"
                    )
                return self.error_msg(str(e))
            
            except Exception as e:
                op.error(str(e))
                return self.error_msg(f"Failed to add series: {e}")
    
    def get_help(self):
        """Return help text for add command."""
        return """
Add a new series to track.

Usage: add <name> <imdb_id_or_link> [score]

Arguments:
  name              Series name (use quotes if it contains spaces)
  imdb_id_or_link   IMDB ID (e.g., tt0903747) or full IMDB URL
  score             Optional: Your rating (1-10, default: 5)

Examples:
  add "Breaking Bad" tt0903747 9
  add "The Wire" https://www.imdb.com/title/tt0306414/ 10
  add "Stranger Things" tt4574334
        """