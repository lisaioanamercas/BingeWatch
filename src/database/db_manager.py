"""
Database manager using Repository pattern.
Handles all database operations for series data.
"""

import sqlite3
from typing import List, Optional
from contextlib import contextmanager

from .models import Series
from ..config.settings import DB_PATH
from ..utils.logger import get_logger


class DBManager:
    """
    Manages database operations for BingeWatch.
    Implements Repository pattern for data persistence.
    """
    
    def __init__(self, db_path=None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file (optional)
        """
        self.db_path = db_path or DB_PATH
        self.logger = get_logger()
        self._initialize_database()
    
    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections.
        Ensures proper connection handling and cleanup.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def _initialize_database(self):
        """Create the series table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            imdb_id TEXT UNIQUE NOT NULL,
            last_episode TEXT DEFAULT 'S00E00',
            last_watch_date TEXT NOT NULL,
            score INTEGER DEFAULT 5 CHECK(score >= 1 AND score <= 10),
            snoozed INTEGER DEFAULT 0 CHECK(snoozed IN (0, 1))
        );
        """
        
        create_index_sql = """
        CREATE INDEX IF NOT EXISTS idx_imdb_id ON series(imdb_id);
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(create_table_sql)
                cursor.execute(create_index_sql)
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise
    
    def add_series(self, series: Series) -> int:
        """
        Add a new series to the database.
        
        Args:
            series: Series object to add
            
        Returns:
            int: ID of the inserted series
            
        Raises:
            sqlite3.IntegrityError: If series with same IMDB ID exists
        """
        insert_sql = """
        INSERT INTO series (name, imdb_id, last_episode, last_watch_date, score, snoozed)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(insert_sql, (
                    series.name,
                    series.imdb_id,
                    series.last_episode,
                    series.last_watch_date,
                    series.score,
                    series.snoozed
                ))
                series_id = cursor.lastrowid
            
            self.logger.info(f"Added series: {series.name} (ID: {series_id})")
            return series_id
        
        except sqlite3.IntegrityError:
            self.logger.error(f"Series with IMDB ID {series.imdb_id} already exists")
            raise ValueError(f"Series with IMDB ID {series.imdb_id} already exists")
    
    def delete_series(self, imdb_id: str) -> bool:
        """
        Delete a series from the database.
        
        Args:
            imdb_id: IMDB ID of the series to delete
            
        Returns:
            bool: True if deleted, False if not found
        """
        delete_sql = "DELETE FROM series WHERE imdb_id = ?"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(delete_sql, (imdb_id,))
                deleted = cursor.rowcount > 0
            
            if deleted:
                self.logger.info(f"Deleted series with IMDB ID: {imdb_id}")
            else:
                self.logger.warning(f"Series with IMDB ID {imdb_id} not found")
            
            return deleted
        
        except Exception as e:
            self.logger.error(f"Error deleting series {imdb_id}: {e}")
            raise
    
    def update_score(self, imdb_id: str, score: int) -> bool:
        """
        Update the score of a series.
        
        Args:
            imdb_id: IMDB ID of the series
            score: New score (1-10)
            
        Returns:
            bool: True if updated, False if not found
        """
        update_sql = "UPDATE series SET score = ? WHERE imdb_id = ?"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(update_sql, (score, imdb_id))
                updated = cursor.rowcount > 0
            
            if updated:
                self.logger.info(f"Updated score for {imdb_id} to {score}")
            else:
                self.logger.warning(f"Series with IMDB ID {imdb_id} not found")
            
            return updated
        
        except Exception as e:
            self.logger.error(f"Error updating score for {imdb_id}: {e}")
            raise
    
    def update_snooze(self, imdb_id: str, snoozed: bool) -> bool:
        """
        Update the snooze status of a series.
        
        Args:
            imdb_id: IMDB ID of the series
            snoozed: New snooze status
            
        Returns:
            bool: True if updated, False if not found
        """
        update_sql = "UPDATE series SET snoozed = ? WHERE imdb_id = ?"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(update_sql, (1 if snoozed else 0, imdb_id))
                updated = cursor.rowcount > 0
            
            status = "snoozed" if snoozed else "unsnoozed"
            if updated:
                self.logger.info(f"Series {imdb_id} {status}")
            else:
                self.logger.warning(f"Series with IMDB ID {imdb_id} not found")
            
            return updated
        
        except Exception as e:
            self.logger.error(f"Error updating snooze for {imdb_id}: {e}")
            raise
    
    def update_last_episode(self, imdb_id: str, episode: str) -> bool:
        """
        Update the last watched episode.
        
        Args:
            imdb_id: IMDB ID of the series
            episode: Episode code (e.g., 'S01E05')
            
        Returns:
            bool: True if updated, False if not found
        """
        from datetime import datetime
        
        update_sql = """
        UPDATE series 
        SET last_episode = ?, last_watch_date = ? 
        WHERE imdb_id = ?
        """
        
        try:
            watch_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(update_sql, (episode, watch_date, imdb_id))
                updated = cursor.rowcount > 0
            
            if updated:
                self.logger.info(f"Updated last episode for {imdb_id} to {episode}")
            else:
                self.logger.warning(f"Series with IMDB ID {imdb_id} not found")
            
            return updated
        
        except Exception as e:
            self.logger.error(f"Error updating last episode for {imdb_id}: {e}")
            raise
    
    def get_series(self, imdb_id: str) -> Optional[Series]:
        """
        Retrieve a series by IMDB ID.
        
        Args:
            imdb_id: IMDB ID of the series
            
        Returns:
            Series object or None if not found
        """
        select_sql = "SELECT * FROM series WHERE imdb_id = ?"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(select_sql, (imdb_id,))
                row = cursor.fetchone()
            
            if row:
                return Series.from_db_row(row)
            return None
        
        except Exception as e:
            self.logger.error(f"Error retrieving series {imdb_id}: {e}")
            raise
    
    def get_all_series(self, include_snoozed: bool = True) -> List[Series]:
        """
        Retrieve all series from the database.
        
        Args:
            include_snoozed: Whether to include snoozed series
            
        Returns:
            List of Series objects
        """
        if include_snoozed:
            select_sql = "SELECT * FROM series ORDER BY score DESC, name ASC"
            params = ()
        else:
            select_sql = "SELECT * FROM series WHERE snoozed = 0 ORDER BY score DESC, name ASC"
            params = ()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(select_sql, params)
                rows = cursor.fetchall()
            
            return [Series.from_db_row(row) for row in rows]
        
        except Exception as e:
            self.logger.error(f"Error retrieving all series: {e}")
            raise