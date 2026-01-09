"""
Add command implementation.
Handles adding new series to the database.

Phase 6 Enhancement: Detailed operation logging.
Phase 7 Enhancement: Auto IMDB lookup by series name.
"""

from datetime import datetime

from .base import Command
from ..database.models import Series
from ..scrapers.imdb_scraper import IMDBScraper
from ..utils.validators import (
    validate_series_name,
    validate_imdb_link,
    validate_score,
    ValidationError
)


class AddCommand(Command):
    """Command to add a new series to tracking."""
    
    def __init__(self, db_manager):
        """Initialize with database manager and IMDB scraper."""
        super().__init__(db_manager)
        self.imdb_scraper = IMDBScraper()
    
    def _is_imdb_id(self, value: str) -> bool:
        """Check if a value looks like an IMDB ID or URL."""
        if not value:
            return False
        value_lower = value.lower()
        # Check for tt prefix (IMDB ID) or imdb.com URL
        return value_lower.startswith('tt') or 'imdb.com' in value_lower
    
    def _is_numeric_score(self, value: str) -> bool:
        """Check if a value looks like a numeric score."""
        try:
            score = int(value)
            return 1 <= score <= 10
        except (ValueError, TypeError):
            return False
    
    def execute(self, args):
        """
        Add a new series to the database.
        
        Supports two formats:
        1. add <name> <imdb_id> [score]    - Traditional with IMDB ID
        2. add <name> [score]              - Auto-lookup by name
        
        Args:
            args: List containing [name, imdb_id_or_score, score (optional)]
            
        Returns:
            str: Success or failure message
        """
        with self.log_op("Add series", args=args) as op:
            try:
                # Validate argument count
                if len(args) < 1:
                    return (
                        self.error_msg("Missing required arguments") + "\n\n"
                        "Usage:\n"
                        "  add <name> [score]              - Auto-lookup IMDB ID\n"
                        "  add <name> <imdb_id> [score]    - With explicit IMDB ID\n\n"
                        "Examples:\n"
                        "  add \"Breaking Bad\" 9\n"
                        "  add \"Breaking Bad\" tt0903747 9"
                    )
                
                name = args[0]
                imdb_id = None
                score = 5  # Default score
                
                # Detect argument pattern
                if len(args) >= 2:
                    second_arg = args[1]
                    
                    if self._is_imdb_id(second_arg):
                        # Pattern: add <name> <imdb_id> [score]
                        imdb_id = second_arg
                        if len(args) >= 3:
                            score = args[2]
                    elif self._is_numeric_score(second_arg):
                        # Pattern: add <name> <score>
                        score = second_arg
                        # imdb_id remains None - will search
                    else:
                        # This looks like a plain word - likely an unquoted multi-word name
                        # e.g., add Breaking Bad 9 → ["Breaking", "Bad", "9"]
                        # Give a helpful error message
                        possible_full_name = " ".join(args[:-1]) if self._is_numeric_score(args[-1]) else " ".join(args)
                        return (
                            self.error_msg("It looks like the series name contains spaces") + "\n\n"
                            "Please use quotes around names with spaces:\n"
                            f'  add "{possible_full_name}" {args[-1] if self._is_numeric_score(args[-1]) else "9"}\n\n'
                            "Examples:\n"
                            '  add "Breaking Bad" 9\n'
                            '  add "Game of Thrones" tt0944947 10'
                        )
                
                # Validate name and score first
                validated_name = validate_series_name(name)
                validated_score = validate_score(score)
                
                # If no IMDB ID provided, search for it
                if imdb_id is None:
                    op.debug(f"No IMDB ID provided, searching for '{validated_name}'...")
                    return self._handle_search_and_add(validated_name, validated_score, op)
                
                # IMDB ID was provided - traditional flow
                op.debug(f"Validating IMDB ID: {imdb_id}")
                validated_imdb_id = validate_imdb_link(imdb_id)
                
                return self._add_series_to_db(
                    validated_name, validated_imdb_id, validated_score, op
                )
            
            except ValidationError as e:
                op.error(f"Validation: {e}")
                if "IMDB" in str(e):
                    return (
                        self.error_msg(f"Invalid IMDB ID: {e}") + "\n\n"
                        "The IMDB ID should look like: tt0903747\n"
                        "Or simply omit it and we'll search by name:\n"
                        "  add \"Breaking Bad\" 9"
                    )
                return self.error_msg(f"Validation error: {e}")
            
            except ValueError as e:
                op.error(str(e))
                if "already exists" in str(e).lower():
                    return (
                        self.error_msg("Series already exists in database") + "\n\n"
                        "Use 'list' to see your tracked series\n"
                        "Use 'delete <imdb_id>' to remove and re-add"
                    )
                return self.error_msg(str(e))
            
            except Exception as e:
                op.error(str(e))
                return self.error_msg(f"Failed to add series: {e}")
    
    def _handle_search_and_add(self, name: str, score: int, op):
        """
        Search IMDB by name and handle the results.
        
        Args:
            name: Series name to search
            score: Score to assign
            op: Operation logger context
            
        Returns:
            str: Result message
        """
        results = self.imdb_scraper.search_series(name)
        
        if not results:
            op.error(f"No results found for '{name}'")
            return (
                self.error_msg(f"No series found matching '{name}'") + "\n\n"
                "Try:\n"
                "  • Check the spelling\n"
                "  • Use the official series title\n"
                "  • Provide the IMDB ID directly: add \"Name\" tt1234567 9"
            )
        
        if len(results) == 1:
            # Single match - auto-add
            result = results[0]
            op.debug(f"Single match found: {result.imdb_id} - {result.title}")
            return self._add_series_to_db(name, result.imdb_id, score, op)
        
        # Multiple matches - show options
        op.debug(f"Multiple matches found: {len(results)}")
        lines = [
            self.info_msg(f"Found {len(results)} series matching '{name}'"),
            "",
            "Please re-run with the specific IMDB ID:",
            ""
        ]
        
        for i, result in enumerate(results, 1):
            year_info = f" ({result.year_range})" if result.year_range else ""
            type_info = f" [{result.type_info}]" if result.type_info else ""
            lines.append(f"  {i}. {result.title}{year_info}{type_info}")
            lines.append(f"     add \"{name}\" {result.imdb_id} {score}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _add_series_to_db(self, name: str, imdb_id: str, score: int, op):
        """
        Add series to the database.
        
        Args:
            name: Series name
            imdb_id: IMDB ID
            score: User score
            op: Operation logger context
            
        Returns:
            str: Success message
        """
        # Check for duplicates (by IMDB ID and by similar name)
        existing_by_id = self.db_manager.find_by_imdb_id(imdb_id)
        if existing_by_id:
            op.debug(f"Series with IMDB ID {imdb_id} already exists")
            return (
                self.error_msg(f"Series already tracked!") + "\n\n"
                f"  Name:     {existing_by_id.name}\n"
                f"  IMDB ID:  {existing_by_id.imdb_id}\n"
                f"  Score:    {existing_by_id.score}/10\n\n"
                "Use 'update' to modify this series."
            )
        
        # Check for similar names (duplicate detection)
        similar_series = self.db_manager.find_similar_by_name(name)
        duplicate_warning = ""
        if similar_series:
            op.debug(f"Found {len(similar_series)} similar series")
            duplicate_warning = (
                "\n" + self.warning_msg("Similar series already tracked:") + "\n"
            )
            for s in similar_series[:3]:  # Limit to 3 suggestions
                snoozed = " [SNOOZED]" if s.snoozed else ""
                duplicate_warning += f"  • {s.name} ({s.imdb_id}){snoozed}\n"
            duplicate_warning += "\n"
        
        # Create series object
        series = Series(
            name=name,
            imdb_id=imdb_id,
            score=score,
            last_episode="S00E00",
            last_watch_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            snoozed=0
        )
        
        op.debug(f"Adding to database...")
        
        # Add to database
        series_id = self.db_manager.add_series(series)
        
        op.success(f"Added '{name}' (ID: {series_id})")
        
        return (
            self.success_msg("Successfully added series:") + "\n"
            f"  Name:     {name}\n"
            f"  IMDB ID:  {imdb_id}\n"
            f"  Score:    {score}/10\n"
            + duplicate_warning +
            "\nNext steps:\n"
            f"  • Use 'episodes' to see new episodes\n"
            f"  • Use 'update episode {imdb_id} S01E01' to mark watched"
        )
    
    def info_msg(self, msg: str) -> str:
        """Format an info message."""
        return f"ℹ {msg}"
    
    def get_help(self):
        """Return help text for add command."""
        return """
Add a new series to track.

Usage:
  add <name> [score]              Auto-lookup IMDB ID by series name
  add <name> <imdb_id> [score]    With explicit IMDB ID

Arguments:
  name              Series name (use quotes if it contains spaces)
  imdb_id           IMDB ID (e.g., tt0903747) or full IMDB URL
  score             Optional: Your rating (1-10, default: 5)

Examples:
  add "Breaking Bad" 9                    # Auto-lookup
  add "Breaking Bad" tt0903747 9          # With IMDB ID
  add "The Office" 8                      # May show options if multiple matches
  add "Stranger Things" tt4574334
        """