"""
Base command interface using Command pattern.
All commands inherit from this abstract base class.
"""

from abc import ABC, abstractmethod
from ..database.db_manager import DBManager
from ..utils.logger import get_logger


class Command(ABC):
    """
    Abstract base class for all commands.
    Implements Command pattern for CLI operations.
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