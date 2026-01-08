"""
Delete command implementation.
Handles removing series from the database.

Phase 6 Enhancement: Detailed operation logging.
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
        with self.log_op("Delete series", args=args) as op:
            try:
                # Validate argument count
                if len(args) < 1:
                    return (
                        self.error_msg("Missing IMDB ID") + "\n\n"
                        "Usage: delete <imdb_id_or_link>\n\n"
                        "Example:\n"
                        "  delete tt0903747"
                    )
                
                # Parse and validate IMDB ID
                imdb_link = args[0]
                validated_imdb_id = validate_imdb_link(imdb_link)
                
                op.debug(f"Looking up series: {validated_imdb_id}")
                
                # Get series info before deleting (for confirmation message)
                series = self.db_manager.get_series(validated_imdb_id)
                if not series:
                    return (
                        self.error_msg(f"Series with IMDB ID '{validated_imdb_id}' not found") + "\n\n"
                        "Use 'list' to see your tracked series"
                    )
                
                op.debug(f"Deleting: {series.name}")
                
                # Delete from database
                deleted = self.db_manager.delete_series(validated_imdb_id)
                
                if deleted:
                    op.success(f"Deleted '{series.name}'")
                    return (
                        self.success_msg("Successfully deleted series:") + "\n"
                        f"  Name:     {series.name}\n"
                        f"  IMDB ID:  {validated_imdb_id}\n\n"
                        "ℹ The series has been removed from your tracking list."
                    )
                else:
                    op.error(f"Database error for {validated_imdb_id}")
                    return self.error_msg(f"Failed to delete series {validated_imdb_id}")
            
            except ValidationError as e:
                op.error(str(e))
                return (
                    self.error_msg(f"Invalid IMDB ID: {e}") + "\n\n"
                    "The IMDB ID should look like: tt0903747\n"
                    "You can also use the full URL: imdb.com/title/tt0903747/"
                )
            
            except Exception as e:
                op.error(str(e))
                return self.error_msg(f"Failed to delete series: {e}")
    
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