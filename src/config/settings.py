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

# HTTP Client settings
# REQUEST_TIMEOUT: How long to wait for a response before giving up
# - Too short: fails on slow connections
# - Too long: blocks the user waiting
# - 15 seconds is a good balance for scraping
REQUEST_TIMEOUT = 15

# MAX_RETRIES: Number of attempts before giving up completely
# - Helps with transient failures (network blips, server hiccups)
# - 3 is standard: original attempt + 2 retries
MAX_RETRIES = 3

# RETRY_DELAY: Base delay between retries (multiplied for exponential backoff)
# - Attempt 1 fails → wait 1s → Attempt 2 fails → wait 2s → Attempt 3
RETRY_DELAY = 1

# IMDB Episode URL template
# {imdb_id}: The series ID (e.g., "tt0903747" for Breaking Bad)
# {season}: Season number (1, 2, 3, etc.)
# Example: https://www.imdb.com/title/tt0903747/episodes?season=1
IMDB_SEASON_URL = "https://www.imdb.com/title/{imdb_id}/episodes?season={season}"

# Validation settings
MIN_SCORE = 1
MAX_SCORE = 10
IMDB_ID_PREFIX = "tt"

# Create necessary directories
DB_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)