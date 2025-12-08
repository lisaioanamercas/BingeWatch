"""
Logging configuration using Singleton pattern.
Ensures consistent logging across the application.
"""

import logging
import sys
from ..config.settings import LOG_PATH, LOG_FORMAT, LOG_LEVEL


class Logger:
    """Singleton logger class for application-wide logging."""
    
    _instance = None
    _logger = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """Configure the logger with file and console handlers."""
        self._logger = logging.getLogger("BingeWatch")
        self._logger.setLevel(getattr(logging, LOG_LEVEL))
        
        # Avoid duplicate handlers
        if self._logger.handlers:
            return
        
        # File handler
        file_handler = logging.FileHandler(LOG_PATH)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(levelname)s: %(message)s")
        console_handler.setFormatter(console_formatter)
        
        self._logger.addHandler(file_handler)
        self._logger.addHandler(console_handler)
    
    def get_logger(self):
        """Return the configured logger instance."""
        return self._logger


# Convenience function to get logger
def get_logger():
    """Get the application logger instance."""
    return Logger().get_logger()