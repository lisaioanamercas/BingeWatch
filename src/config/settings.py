"""
Configuration settings for BingeWatch application.
Centralizes all configuration constants for easy maintenance.
"""

import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Database settings
DB_DIR = PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "bingewatch.db"

# Logging settings
LOG_DIR = PROJECT_ROOT / "logs"
LOG_PATH = LOG_DIR / "bingewatch.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"

# IMDB settings
IMDB_BASE_URL = "https://www.imdb.com"
IMDB_EPISODE_PATH = "/title/{}/episodes"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Validation settings
MIN_SCORE = 1
MAX_SCORE = 10
IMDB_ID_PREFIX = "tt"

# Create necessary directories
DB_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)