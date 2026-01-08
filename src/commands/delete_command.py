"""
Delete command implementation.
Handles removing series from the database.

Phase 6 Enhancement: Detailed operation logging.
Phase 7 Enhancement: Name-based series lookup.
"""

from .base import Command


class DeleteCommand(Command):
    """Command to delete a series from tracking."""
    
    def execute(self, args):
        """
        Delete a series from the database.
        
        Args:
            args: List containing [name_or_imdb_id]
            
        Returns:
            str: Success or failure message
        """
        with self.log_op("Delete series", args=args) as op:
            try:
                # Validate argument count
                if len(args) < 1:
                    return (
                        self.error_msg("Missing series identifier") + "\n\n"
                        "Usage: delete <name_or_imdb_id>\n\n"
                        "Examples:\n"
                        '  delete "Breaking Bad"\n'
                        "  delete tt0903747"
                    )
                
                # Resolve series by name or IMDB ID
                identifier = args[0]
                series, error = self.resolve_series(identifier)
                if error:
                    return self.error_msg(error)
                
                op.debug(f"Deleting: {series.name} ({series.imdb_id})")
                
                # Delete from database
                deleted = self.db_manager.delete_series(series.imdb_id)
                
                if deleted:
                    op.success(f"Deleted '{series.name}'")
                    return (
                        self.success_msg("Successfully deleted series:") + "\n"
                        f"  Name:     {series.name}\n"
                        f"  IMDB ID:  {series.imdb_id}\n\n"
                        "ℹ The series has been removed from your tracking list."
                    )
                else:
                    op.error(f"Database error for {series.imdb_id}")
                    return self.error_msg(f"Failed to delete series {series.imdb_id}")
            
            except Exception as e:
                op.error(str(e))
                return self.error_msg(f"Failed to delete series: {e}")
    
    def get_help(self):
        """Return help text for delete command."""
        return '''
Delete a series from tracking.

Usage: delete <series>

Arguments:
  series    Series name (in quotes) or IMDB ID

Examples:
  delete "Breaking Bad"
  delete tt0903747
  delete "Game of Thrones"
        '''