"""
Base command interface using Command pattern.
All commands inherit from this abstract base class.

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
        return f"✓ {text}"
    
    @staticmethod
    def error_msg(text: str) -> str:
        """Format an error message with X mark."""
        return f"✗ {text}"
    
    @staticmethod
    def info_msg(text: str) -> str:
        """Format an info message with info symbol."""
        return f"ℹ {text}"
    
    @staticmethod
    def warning_msg(text: str) -> str:
        """Format a warning message."""
        return f"⚠ {text}"
    
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