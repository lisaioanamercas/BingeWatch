"""
Enhanced Logging System for BingeWatch.

This module provides:
- Singleton logger with file and console handlers
- Verbose/quiet mode support
- Operation-specific logging with context
- Structured logging for tracking operations

Phase 6 Enhancement: Added detailed operation logging and verbosity control.
"""

import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from ..config.settings import LOG_PATH, LOG_FORMAT, LOG_LEVEL


class Logger:
    """
    Singleton logger class for application-wide logging.
    
    Supports multiple verbosity levels:
    - QUIET: Only errors and critical messages
    - NORMAL: Standard operation messages
    - VERBOSE: Detailed debug information
    """
    
    _instance = None
    _logger = None
    _verbose_mode = False
    _quiet_mode = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """Configure the logger with file and console handlers."""
        self._logger = logging.getLogger("BingeWatch")
        self._logger.setLevel(logging.DEBUG)  # Always capture all levels to file
        
        # Avoid duplicate handlers
        if self._logger.handlers:
            return
        
        # File handler - captures everything with timestamps
        file_handler = logging.FileHandler(LOG_PATH, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler - respects verbosity settings
        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("%(message)s")
        self._console_handler.setFormatter(console_formatter)
        
        self._logger.addHandler(file_handler)
        self._logger.addHandler(self._console_handler)
    
    def set_verbose(self, enabled: bool = True):
        """Enable or disable verbose mode."""
        self._verbose_mode = enabled
        if enabled:
            self._console_handler.setLevel(logging.DEBUG)
            self._quiet_mode = False
    
    def set_quiet(self, enabled: bool = True):
        """Enable or disable quiet mode."""
        self._quiet_mode = enabled
        if enabled:
            self._console_handler.setLevel(logging.ERROR)
            self._verbose_mode = False
    
    def reset_verbosity(self):
        """Reset to normal verbosity."""
        self._verbose_mode = False
        self._quiet_mode = False
        self._console_handler.setLevel(logging.INFO)
    
    @property
    def is_verbose(self) -> bool:
        """Check if in verbose mode."""
        return self._verbose_mode
    
    @property
    def is_quiet(self) -> bool:
        """Check if in quiet mode."""
        return self._quiet_mode
    
    def get_logger(self):
        """Return the configured logger instance."""
        return self._logger


class OperationLogger:
    """
    Context manager for logging operations with timing and context.
    
    Usage:
        with OperationLogger("Adding series", series_name=name) as op:
            # ... do work ...
            op.success("Series added successfully")
    """
    
    def __init__(self, operation_name: str, **context):
        """
        Initialize operation logger.
        
        Args:
            operation_name: Name of the operation being performed
            **context: Additional context to include in logs
        """
        self.operation_name = operation_name
        self.context = context
        self.logger = get_logger()
        self.start_time = None
        self._completed = False
    
    def __enter__(self):
        self.start_time = datetime.now()
        context_str = self._format_context()
        self.logger.debug(f"[START] {self.operation_name}{context_str}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._completed:
            duration = self._get_duration()
            if exc_type is not None:
                self.logger.error(
                    f"[FAILED] {self.operation_name} after {duration}ms: {exc_val}"
                )
            else:
                self.logger.debug(f"[END] {self.operation_name} ({duration}ms)")
        return False  # Don't suppress exceptions
    
    def _format_context(self) -> str:
        """Format context dictionary as string."""
        if not self.context:
            return ""
        items = [f"{k}={v}" for k, v in self.context.items()]
        return f" [{', '.join(items)}]"
    
    def _get_duration(self) -> int:
        """Get operation duration in milliseconds."""
        if self.start_time:
            return int((datetime.now() - self.start_time).total_seconds() * 1000)
        return 0
    
    def success(self, message: str):
        """Log successful completion."""
        self._completed = True
        duration = self._get_duration()
        self.logger.info(f"[OK] {message}")
        self.logger.debug(f"[SUCCESS] {self.operation_name} ({duration}ms): {message}")
    
    def error(self, message: str):
        """Log error."""
        self._completed = True
        duration = self._get_duration()
        self.logger.error(f"[ERROR] {message}")
        self.logger.debug(f"[ERROR] {self.operation_name} ({duration}ms): {message}")
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(f"[INFO] {message}")
    
    def debug(self, message: str):
        """Log debug message (only shown in verbose mode)."""
        self.logger.debug(f"  → {message}")


# Convenience functions
def get_logger():
    """Get the application logger instance."""
    return Logger().get_logger()


def set_verbose(enabled: bool = True):
    """Enable or disable verbose mode globally."""
    Logger().set_verbose(enabled)


def set_quiet(enabled: bool = True):
    """Enable or disable quiet mode globally."""
    Logger().set_quiet(enabled)


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return Logger().is_verbose


def is_quiet() -> bool:
    """Check if quiet mode is enabled."""
    return Logger().is_quiet


def log_operation(operation_name: str, **context) -> OperationLogger:
    """
    Create an operation logger context manager.
    
    Usage:
        with log_operation("Adding series", name="Breaking Bad") as op:
            # ... do work ...
            op.success("Added!")
    """
    return OperationLogger(operation_name, **context)