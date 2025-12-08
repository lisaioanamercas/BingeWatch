"""
Delete command implementation.
Handles removing series from the database.
"""

from .base import Command
from ..utils.validators import (
    validate_imdb_link,
    ValidationError
)


class DeleteCommand(Command):
    """Command to delete a series from tracking."""
    
    def execute(self, args):
        """
        Delete a series from the database.
        
        Args:
            args: List containing [imdb_id_or_link]
            
        Returns:
            str: Success or failure message
        """
        try:
            # Validate argument count
            if len(args) < 1:
                return "✗ Usage: delete <imdb_id_or_link>"
            
            # Parse and validate IMDB ID
            imdb_link = args[0]
            validated_imdb_id = validate_imdb_link(imdb_link)
            
            # Get series info before deleting (for confirmation message)
            series = self.db_manager.get_series(validated_imdb_id)
            if not series:
                return f"✗ Series with IMDB ID {validated_imdb_id} not found"
            
            # Delete from database
            deleted = self.db_manager.delete_series(validated_imdb_id)
            
            if deleted:
                return (
                    f"✓ Successfully deleted series:\n"
                    f"  Name: {series.name}\n"
                    f"  IMDB ID: {validated_imdb_id}"
                )
            else:
                return f"✗ Failed to delete series {validated_imdb_id}"
        
        except ValidationError as e:
            error_msg = f"Validation error: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
        
        except Exception as e:
            error_msg = f"Failed to delete series: {e}"
            self.logger.error(error_msg)
            return f"✗ {error_msg}"
    
    def get_help(self):
        """Return help text for delete command."""
        return """
Delete a series from tracking.

Usage: delete <imdb_id_or_link>

Arguments:
  imdb_id_or_link   IMDB ID (e.g., tt0903747) or full IMDB URL

Examples:
  delete tt0903747
  delete https://www.imdb.com/title/tt0306414/
        """