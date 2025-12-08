"""
Add command implementation.
Handles adding new series to the database.
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
        try:
            # Validate argument count
            if len(args) < 2:
                return "✗ Usage: add <name> <imdb_id_or_link> [score]"
            
            # Parse arguments
            name = args[0]
            imdb_link = args[1]
            score = 5  # Default score
            
            if len(args) >= 3:
                score = args[2]
            
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
            
            # Add to database
            series_id = self.db_manager.add_series(series)
            
            return (
                f"✓ Successfully added series:\n"
                f"  Name: {validated_name}\n"
                f"  IMDB ID: {validated_imdb_id}\n"
                f"  Score: {validated_score}/10\n"
                f"  Database ID: {series_id}"
            )
        
        except ValidationError as e:
            error_msg = f"Validation error: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
        
        except ValueError as e:
            error_msg = str(e)
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
        
        except Exception as e:
            error_msg = f"Failed to add series: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
    
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