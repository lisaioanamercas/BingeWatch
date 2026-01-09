"""
Base command interface using Command pattern.
All commands inherit from this abstract base class.

DESIGN PATTERNS USED:
=====================
1. Command Pattern - Encapsulates a request as an object (execute method).
   Each command (AddCommand, DeleteCommand, etc.) is a concrete implementation.
   Benefits: decouples sender from receiver, supports undo, logging, queuing.

2. Template Method Pattern - The Command class defines the algorithm skeleton:
   - execute() is the abstract template method
   - Helper methods (success_msg, error_msg, log_op) are the steps
   Subclasses override execute() but reuse the helpers.

3. Strategy Pattern (for output formatting) - success_msg, error_msg, etc.
   could be swapped for different output strategies (JSON, plain text, etc.)

Phase 6 Enhancement: Added output formatting helpers and operation logging.
"""

from abc import ABC, abstractmethod
from ..database.db_manager import DBManager
from ..utils.logger import get_logger, log_operation, is_verbose



class Command(ABC):
    """
    Abstract base class for all commands.
    Implements Command pattern for CLI operations.
    
    Provides helper methods for:
    - Consistent output formatting (success, error, info messages)
    - Operation logging with context
    - Verbose mode awareness
    """
    
    def __init__(self, db_manager: DBManager):
        """
        Initialize command with database manager.
        
        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.logger = get_logger()
    
    @abstractmethod
    def execute(self, args: list) -> str:
        """
        Execute the command with given arguments.
        
        Args:
            args: List of command arguments
            
        Returns:
            str: Result message
        """
        pass
    
    @abstractmethod
    def get_help(self) -> str:
        """
        Get help text for this command.
        
        Returns:
            str: Help text
        """
        pass
    
    # ==========================================================================
    # Output Formatting Helpers
    # ==========================================================================
    
    @staticmethod
    def success_msg(text: str) -> str:
        """Format a success message with checkmark."""
        return f"[OK] {text}"
    
    @staticmethod
    def error_msg(text: str) -> str:
        """Format an error message with X mark."""
        return f"[ERROR] {text}"
    
    @staticmethod
    def info_msg(text: str) -> str:
        """Format an info message with info symbol."""
        return f"[INFO] {text}"
    
    @staticmethod
    def warning_msg(text: str) -> str:
        """Format a warning message."""
        return f"[WARN] {text}"
    
    @staticmethod
    def header(text: str, width: int = 60) -> str:
        """Create a formatted header line."""
        return f"{'═' * width}\n{text}\n{'═' * width}"
    
    @staticmethod
    def divider(width: int = 60) -> str:
        """Create a divider line."""
        return "─" * width
    
    # ==========================================================================
    # Operation Logging
    # ==========================================================================
    
    def log_op(self, operation_name: str, **context):
        """
        Create an operation logger for this command.
        
        Usage:
            with self.log_op("Adding series", name=series_name) as op:
                # ... do work ...
                op.success("Series added!")
        """
        return log_operation(operation_name, **context)
    
    @property
    def verbose(self) -> bool:
        """Check if verbose mode is enabled."""
        return is_verbose()
    
    def debug(self, message: str):
        """Log a debug message (only visible in verbose mode)."""
        self.logger.debug(f"  → {message}")
    
    # ==========================================================================
    # Series Resolution (Name or IMDB ID)
    # ==========================================================================
    
    def resolve_series(self, identifier: str):
        """
        Resolve a series by name or IMDB ID.
        
        This helper enables commands to accept either:
        - IMDB ID: "tt0903747" → direct database lookup
        - Series name: "Breaking Bad" → search database by name
        
        Args:
            identifier: Series name or IMDB ID
            
        Returns:
            tuple: (series, error_message)
                - If exactly one match: (Series, None)
                - If no matches: (None, error_string)
                - If multiple matches: (None, formatted_options_string)
        """
        # Check if it looks like an IMDB ID
        if identifier.lower().startswith('tt') or 'imdb.com' in identifier.lower():
            # Direct IMDB ID lookup
            from ..utils.validators import validate_imdb_link, ValidationError
            try:
                imdb_id = validate_imdb_link(identifier)
                series = self.db_manager.get_series(imdb_id)
                if series:
                    return (series, None)
                else:
                    return (None, f"Series with IMDB ID '{imdb_id}' not found.\nUse 'list' to see your tracked series.")
            except ValidationError as e:
                return (None, f"Invalid IMDB ID: {e}")
        
        # Search by name in the database
        all_series = self.db_manager.get_all_series()
        
        # First try exact match (case-insensitive)
        exact_matches = [s for s in all_series if s.name.lower() == identifier.lower()]
        if len(exact_matches) == 1:
            return (exact_matches[0], None)
        
        # Then try partial match (name contains the search term)
        partial_matches = [s for s in all_series if identifier.lower() in s.name.lower()]
        
        if len(partial_matches) == 0:
            return (None, f"No series found matching '{identifier}'.\nUse 'list' to see your tracked series.")
        
        if len(partial_matches) == 1:
            return (partial_matches[0], None)
        
        # Multiple matches - show options
        lines = [
            f"Found {len(partial_matches)} series matching '{identifier}':",
            "",
            "Please specify the IMDB ID:",
            ""
        ]
        for i, s in enumerate(partial_matches, 1):
            snoozed = " [SNOOZED]" if s.snoozed else ""
            lines.append(f"  {i}. {s.name} ({s.imdb_id}) - Score: {s.score}/10{snoozed}")
        
        return (None, "\n".join(lines))