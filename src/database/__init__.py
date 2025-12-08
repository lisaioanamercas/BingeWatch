"""
Database layer for BingeWatch.
"""

from .db_manager import DBManager
from .models import Series, Episode

__all__ = ['DBManager', 'Series', 'Episode']