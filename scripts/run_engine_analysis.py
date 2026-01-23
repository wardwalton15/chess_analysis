"""
Run Stockfish engine analysis on tournament games.

This script demonstrates the full pipeline:
1. Load games from PGN
2. Analyze with Stockfish (using cache)
3. Calculate player accuracy stats
4. Find comebacks and blown leads
5. Show accuracy by thinking time

Usage:
    python scripts/run_engine_analysis.py

Make sure Stockfish is installed and the path is set in config.yaml
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.parsers.pgn_parser import read_pgn_file
from src.analysis.engine_analysis import analyze_games
from src.analysis.accuracy_analysis import (
    calculate_player_accuracy,
    find_comebacks,
    find_blown_leads,
    print_accuracy_report,
    print_comeback_report,
    print_blown_lead_report,
)


def main():
    # Load configuration
    config = get_config()
    print(f"Configuration loaded: {config}")
    print(f"Engine path: {config.engine_path}")
    print(f"Depth: {config.engine_depth}")

    # Load games
    pgn_path = config.data_raw_path / config.active_pgn_file
    print(f"\nLoading games from: {pgn_path}")

    games = list(read_pgn_file(
        pgn_path,
        config.active_time_control,
        include_clock_data=True
    ))
    print(f"Loaded {len(games)} games")

    if not games:
        print("No games found!")
        return

    # Analyze with Stockfish
    print("\n" + "=" * 60)
    print("RUNNING STOCKFISH ANALYSIS")
    print("=" * 60)
    print(f"This may take a while... (depth={config.engine_depth})")

    game_evals = analyze_games(
        games=games,
        engine_path=config.engine_path,
        depth=config.engine_depth,
        skip_opening_moves=config.skip_opening_moves,
        threads=config.engine_threads,
        hash_mb=config.engine_hash_mb,
        cache_path=config.cache_path,
        verbose=True
    )

    # Calculate player accuracy
    print("\nCalculating player statistics...")
    player_stats = calculate_player_accuracy(game_evals)

    # Print accuracy report
    print_accuracy_report(player_stats, sort_by="accuracy")

    # Find comebacks
    comebacks = find_comebacks(game_evals, threshold_cp=config.comeback_threshold)
    if comebacks:
        print_comeback_report(comebacks, top_n=10)
    else:
        print("\nNo comebacks found with current threshold.")

    # Find blown leads
    blown_leads = find_blown_leads(game_evals, threshold_cp=config.blown_lead_threshold)
    if blown_leads:
        print_blown_lead_report(blown_leads, top_n=10)
    else:
        print("\nNo blown leads found with current threshold.")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Games analyzed: {len(game_evals)}")
    print(f"Total comebacks: {len(comebacks)}")
    print(f"Total blown leads: {len(blown_leads)}")

    # Most accurate player
    if player_stats:
        best_player = max(player_stats.values(), key=lambda x: x.accuracy_pct)
        print(f"\nMost accurate player: {best_player.player_name} "
              f"({best_player.accuracy_pct:.1f}%)")

        # Best on long thinks
        players_with_long_thinks = [
            p for p in player_stats.values()
            if p.moves_over_15min >= 5  # Need at least 5 long thinks
        ]
        if players_with_long_thinks:
            best_thinker = max(players_with_long_thinks,
                              key=lambda x: x.accuracy_over_15min)
            print(f"Best on 15+ min thinks: {best_thinker.player_name} "
                  f"({best_thinker.accuracy_over_15min:.1f}% on {best_thinker.moves_over_15min} moves)")


if __name__ == "__main__":
    main()
