"""
BingeWatch - TV Series Tracker
Main entry point and CLI orchestration.

Phase 6 Enhancement: Added verbose/quiet modes and episodes command.
"""

import sys
from typing import Dict

from .database.db_manager import DBManager
from .commands.base import Command
from .commands.add_command import AddCommand
from .commands.delete_command import DeleteCommand
from .commands.update_command import UpdateCommand
from .commands.list_command import ListCommand
from .commands.watchlist_command import WatchlistCommand
from .commands.trailers_command import TrailersCommand
from .commands.check_command import CheckCommand
from .commands.episodes_command import EpisodesCommand
from .utils.logger import get_logger, set_verbose, set_quiet


class CommandFactory:
    """
    Factory for creating command instances.
    Implements Factory pattern for command instantiation.
    """
    
    def __init__(self, db_manager: DBManager):
        """Initialize factory with database manager."""
        self.db_manager = db_manager
        self._commands: Dict[str, Command] = {}
        self._register_commands()
    
    def _register_commands(self):
        """Register all available commands."""
        self._commands = {
            'add': AddCommand(self.db_manager),
            'delete': DeleteCommand(self.db_manager),
            'remove': DeleteCommand(self.db_manager),  # Alias
            'update': UpdateCommand(self.db_manager),
            'list': ListCommand(self.db_manager),
            'ls': ListCommand(self.db_manager),  # Alias
            'watchlist': WatchlistCommand(self.db_manager),
            'wl': WatchlistCommand(self.db_manager),  # Alias
            'trailers': TrailersCommand(self.db_manager),
            'tr': TrailersCommand(self.db_manager),  # Alias
            'check': CheckCommand(self.db_manager),
            'episodes': EpisodesCommand(self.db_manager),
            'ep': EpisodesCommand(self.db_manager),  # Alias
        }
    
    def get_command(self, command_name: str) -> Command:
        """
        Get command instance by name.
        
        Args:
            command_name: Name of the command
            
        Returns:
            Command instance
            
        Raises:
            KeyError: If command not found
        """
        command = self._commands.get(command_name.lower())
        if not command:
            raise KeyError(f"Unknown command: {command_name}")
        return command
    
    def get_all_commands(self) -> Dict[str, Command]:
        """Return all registered commands."""
        return self._commands


class BingeWatchCLI:
    """
    Main CLI application class.
    Handles command parsing and execution.
    """
    
    def __init__(self):
        """Initialize CLI with database and command factory."""
        self.logger = get_logger()
        self.db_manager = DBManager()
        self.command_factory = CommandFactory(self.db_manager)
    
    def print_banner(self):
        """Print application banner."""
        banner = """
╔══════════════════════════════════════════════════════════════════╗
║                          BingeWatch                              ║
║                   TV Series Tracker & Monitor                    ║
╚══════════════════════════════════════════════════════════════════╝
        """
        print(banner)
    
    def print_help(self):
        """Print general help information."""
        help_text = """
╔══════════════════════════════════════════════════════════════════╗
║                     BingeWatch Commands                          ║
╚══════════════════════════════════════════════════════════════════╝

📌 GETTING STARTED (do these first!)
─────────────────────────────────────
  add         Add a series → add "Breaking Bad" 9
  list        See your series → list

📺 WHAT TO WATCH
─────────────────────────────────────
  episodes    New episodes across all series → episodes
  watchlist   Prioritized by score → watchlist --top 10

🎬 DISCOVER CONTENT
─────────────────────────────────────
  trailers    YouTube trailers → trailers "Breaking Bad" S01E01
  check       Scan for NEW videos → check

✏️ MANAGE YOUR SERIES
─────────────────────────────────────
  update      Change score/snooze/episode:
              → update score "Breaking Bad" 10
              → update snooze "Breaking Bad"
              → update episode "Breaking Bad" S05E16
  delete      Remove series → delete "Breaking Bad"

❓ HELP
─────────────────────────────────────
  help        Show this message
  help <cmd>  Detailed help → help add

⚙️ OPTIONS
─────────────────────────────────────
  --verbose   Show debug info
  --quiet     Minimal output

Type 'exit' to quit.
        """
        print(help_text)
    
    def print_command_help(self, command_name: str):
        """Print help for a specific command."""
        try:
            command = self.command_factory.get_command(command_name)
            print(command.get_help())
        except KeyError:
            print(f"Unknown command: {command_name}")
            print("Use 'help' to see all available commands.")
    
    def parse_command(self, input_line: str):
        """
        Parse command line input.
        
        Args:
            input_line: Raw input string
            
        Returns:
            tuple: (command_name, arguments_list)
        """
        # Handle quoted strings
        parts = []
        current = []
        in_quotes = False
        
        for char in input_line:
            if char == '"':
                in_quotes = not in_quotes
                if not in_quotes and current:
                    parts.append(''.join(current))
                    current = []
            elif char == ' ' and not in_quotes:
                if current:
                    parts.append(''.join(current))
                    current = []
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        if not parts:
            return None, []
        
        command_name = parts[0].lower()
        args = parts[1:]
        
        return command_name, args
    
    def execute_command(self, command_name: str, args: list):
        """
        Execute a command with given arguments.
        
        Args:
            command_name: Name of the command
            args: List of arguments
            
        Returns:
            str: Result message
        """
        try:
            command = self.command_factory.get_command(command_name)
            result = command.execute(args)
            return result
        
        except KeyError as e:
            return f"Unknown command: {command_name}. Type 'help' for available commands."
        
        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            return f"Error: {e}"
    
    def run_interactive(self):
        """Run interactive CLI mode."""
        self.print_banner()
        print("Type 'help' for available commands or 'exit' to quit.\n")
        
        while True:
            try:
                # Get user input
                user_input = input("bingewatch> ").strip()
                
                if not user_input:
                    continue
                
                # Parse command
                command_name, args = self.parse_command(user_input)
                
                if not command_name:
                    continue
                
                # Handle special commands
                if command_name in ['exit', 'quit', 'q']:
                    print("Goodbye! Happy watching! 📺")
                    break
                
                if command_name == 'help':
                    if args:
                        self.print_command_help(args[0])
                    else:
                        self.print_help()
                    continue
                
                # Execute command
                result = self.execute_command(command_name, args)
                print(result)
                print()  # Empty line for readability
            
            except KeyboardInterrupt:
                print("\n\nInterrupted. Use 'exit' to quit.")
            
            except EOFError:
                print("\nGoodbye! Happy watching! 📺")
                break
            
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                print(f"Unexpected error: {e}")
    
    def run_command(self, command_args: list):
        """
        Run a single command from command-line arguments.
        
        Args:
            command_args: List of command-line arguments
        """
        if not command_args:
            print("✗ Error: No command specified")
            print("  Use 'help' to see available commands.")
            self.print_help()
            return 1
        
        # Handle global flags
        args = list(command_args)
        if '--verbose' in args or '-v' in args:
            set_verbose(True)
            args = [a for a in args if a not in ('--verbose', '-v')]
            self.logger.debug("Verbose mode enabled")
        
        if '--quiet' in args or '-q' in args:
            set_quiet(True)
            args = [a for a in args if a not in ('--quiet', '-q')]
        
        if not args:
            print("✗ Error: No command specified")
            return 1
        
        command_name = args[0]
        command_args = args[1:]
        
        if command_name in ['help', '-h', '--help']:
            if command_args:
                self.print_command_help(command_args[0])
            else:
                self.print_help()
            return 0
        
        result = self.execute_command(command_name, command_args)
        print(result)
        return 0


def main():
    """Main entry point for BingeWatch application."""
    cli = BingeWatchCLI()
    
    # Check if running with command-line arguments
    if len(sys.argv) > 1:
        # Single command mode
        exit_code = cli.run_command(sys.argv[1:])
        sys.exit(exit_code)
    else:
        # Interactive mode
        cli.run_interactive()


if __name__ == "__main__":
    main()