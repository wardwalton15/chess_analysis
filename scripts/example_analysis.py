"""
Example script demonstrating how to use the refactored chess analysis modules.
This replicates the analysis from intro.ipynb using the new structure.
"""

from pathlib import Path
import sys

# Add src to path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import get_config
from src.parsers.pgn_parser import read_pgn_file
from src.analysis.time_analysis import (
    analyze_opening_time,
    analyze_opponent_opening_time,
    find_long_thinks,
    print_opening_time_report,
    print_long_thinks_report
)


def main():
    """Run example analysis on the 2024 Candidates tournament."""

    # Load configuration
    print("Loading configuration...")
    config = get_config()
    print(f"Active tournament: {config.get('tournament', 'name')}")
    print(f"Time control: {config.get('active_tournament', 'time_control')}")
    print()

    # Parse PGN file
    pgn_path = config.data_raw_path / config.active_pgn_file
    print(f"Parsing games from: {pgn_path}")

    time_control = config.active_time_control
    games = list(read_pgn_file(pgn_path, time_control))
    print(f"Loaded {len(games)} games")
    print()

    # Analysis 1: Opening time spent
    print("=" * 100)
    print("OPENING TIME ANALYSIS (First 10 moves)")
    print("=" * 100)
    opening_stats = analyze_opening_time(games, opening_moves=config.opening_moves)
    print_opening_time_report(opening_stats, sort_by="total")
    print()

    # Analysis 2: Opponent opening time
    print("=" * 100)
    print("OPPONENT OPENING TIME (Who forces opponents to think?)")
    print("=" * 100)
    opponent_stats = analyze_opponent_opening_time(games, opening_moves=config.opening_moves)

    # Print opponent stats
    sorted_opponent = sorted(
        opponent_stats.values(),
        key=lambda x: x.total_opponent_time,
        reverse=True
    )

    print(f"{'Player':<30} {'Opp Total Time':<15} {'vs White Opp':<15} {'vs Black Opp':<15}")
    print("=" * 80)
    for stats in sorted_opponent:
        from src.parsers.clock_parser import format_time
        print(f"{stats.player_name:<30} "
              f"{format_time(stats.total_opponent_time):<15} "
              f"{format_time(stats.vs_white_time):<15} "
              f"{format_time(stats.vs_black_time):<15}")
    print()

    # Analysis 3: Long thinks
    print("=" * 100)
    print("LONG THINKS (20+ minutes on a single move)")
    print("=" * 100)
    long_think_counts, long_thinks = find_long_thinks(
        games,
        threshold_seconds=config.long_think_seconds
    )
    print_long_thinks_report(long_think_counts, long_thinks, top_n=15)
    print()

    print(f"\nTotal long thinks (20+ min) in tournament: {len(long_thinks)}")
    print(f"Total games analyzed: {len(games)}")


if __name__ == "__main__":
    main()
