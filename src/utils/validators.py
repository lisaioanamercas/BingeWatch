"""
Input validation utilities.
Provides reusable validation functions for user inputs.
"""

import re
from urllib.parse import urlparse
from ..config.settings import MIN_SCORE, MAX_SCORE, IMDB_ID_PREFIX


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_series_name(name):
    """
    Validate series name.
    
    Args:
        name: Series name string
        
    Returns:
        str: Cleaned series name
        
    Raises:
        ValidationError: If name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Series name cannot be empty")
    
    cleaned_name = name.strip()
    if len(cleaned_name) < 2:
        raise ValidationError("Series name must be at least 2 characters long")
    
    return cleaned_name


def validate_imdb_link(link):
    """
    Validate and extract IMDB ID from link.
    
    Args:
        link: IMDB URL or ID string
        
    Returns:
        str: Extracted IMDB ID (e.g., 'tt1234567')
        
    Raises:
        ValidationError: If link is invalid
    """
    if not link or not link.strip():
        raise ValidationError("IMDB link cannot be empty")
    
    # If it's already an ID (starts with 'tt')
    if link.startswith(IMDB_ID_PREFIX):
        imdb_id = link.strip()
        if re.match(r'^tt\d{7,}$', imdb_id):
            return imdb_id
        raise ValidationError(f"Invalid IMDB ID format: {imdb_id}")
    
    # If it's a URL, extract the ID
    try:
        parsed = urlparse(link)
        path_parts = parsed.path.split('/')
        
        # Find the part that starts with 'tt'
        for part in path_parts:
            if part.startswith(IMDB_ID_PREFIX):
                if re.match(r'^tt\d{7,}$', part):
                    return part
        
        raise ValidationError(f"Could not extract IMDB ID from URL: {link}")
    
    except Exception as e:
        raise ValidationError(f"Invalid IMDB link: {link} - {str(e)}")


def validate_score(score):
    """
    Validate score value.
    
    Args:
        score: Score value (int or str)
        
    Returns:
        int: Valid score
        
    Raises:
        ValidationError: If score is invalid
    """
    try:
        score_int = int(score)
    except (ValueError, TypeError):
        raise ValidationError(f"Score must be an integer, got: {score}")
    
    if not MIN_SCORE <= score_int <= MAX_SCORE:
        raise ValidationError(
            f"Score must be between {MIN_SCORE} and {MAX_SCORE}, got: {score_int}"
        )
    
    return score_int


def validate_episode_format(episode_str):
    """
    Validate episode format (e.g., 'S01E05' or '1x5').
    
    Args:
        episode_str: Episode string
        
    Returns:
        tuple: (season, episode) as integers
        
    Raises:
        ValidationError: If format is invalid
    """
    if not episode_str:
        raise ValidationError("Episode format cannot be empty")
    
    # Try S01E05 format
    match = re.match(r'S(\d+)E(\d+)', episode_str.upper())
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Try 1x5 format
    match = re.match(r'(\d+)x(\d+)', episode_str.lower())
    if match:
        return int(match.group(1)), int(match.group(2))
    
    raise ValidationError(
        f"Invalid episode format: {episode_str}. Use 'S01E05' or '1x5' format"
    )