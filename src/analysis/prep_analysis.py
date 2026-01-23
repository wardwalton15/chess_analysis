"""
Preparation analysis for chess games.
Detects when players leave their opening preparation based on thinking time.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

from ..parsers.pgn_parser import ParsedGame
from ..parsers.clock_parser import format_time, get_initial_time


@dataclass
class PrepExit:
    """Record of when a player left their preparation."""
    player: str
    opponent: str
    exit_move: int  # Move number where they left prep
    time_spent_on_exit: int  # Seconds spent on the exit move
    pct_of_time: float  # Percentage of base time spent
    color: str  # "White" or "Black"
    round_num: str
    event: str
    move_san: str = ""  # The move they thought about


@dataclass
class PrepStats:
    """Aggregate preparation statistics for a player."""
    player_name: str
    total_games: int = 0
    avg_prep_exit_move: float = 0.0
    earliest_exit: int = 999
    latest_exit: int = 0
    times_first_to_think: int = 0  # Games where they thought first
    prep_exits: List[PrepExit] = None

    def __post_init__(self):
        if self.prep_exits is None:
            self.prep_exits = []


def detect_prep_exit(
    game: ParsedGame,
    time_control_config: Optional[Dict] = None,
    method: str = "hybrid",
    pct_threshold: float = 0.05,
    absolute_threshold_minutes: int = 10,
    min_move_number: int = 4
) -> Tuple[Optional[PrepExit], Optional[PrepExit]]:
    """
    Detect when each player leaves their preparation in a game.

    A player is considered to have left prep when they first spend significant
    time on a move, indicating they're now calculating on their own.

    Args:
        game: Parsed game data
        time_control_config: Time control settings
        method: Detection method - "percentage", "absolute", or "hybrid"
        pct_threshold: Percentage threshold (0.05 = 5% of base time)
        absolute_threshold_minutes: Absolute threshold in minutes
        min_move_number: Don't count prep exit before this move

    Returns:
        Tuple of (white_prep_exit, black_prep_exit), either can be None
    """
    base_time = get_initial_time(time_control_config) if time_control_config else 7200
    pct_threshold_seconds = base_time * pct_threshold
    absolute_threshold_seconds = absolute_threshold_minutes * 60

    white_exit = None
    black_exit = None

    white_player = game.metadata.white
    black_player = game.metadata.black

    for move in game.moves:
        if move.time_spent is None:
            continue

        # Skip very early moves
        if move.player_move_num < min_move_number:
            continue

        # Check if this move qualifies as leaving prep
        is_prep_exit = False

        if method == "percentage":
            is_prep_exit = move.time_spent >= pct_threshold_seconds
        elif method == "absolute":
            is_prep_exit = move.time_spent >= absolute_threshold_seconds
        elif method == "hybrid":
            # Either condition triggers prep exit
            is_prep_exit = (move.time_spent >= pct_threshold_seconds or
                          move.time_spent >= absolute_threshold_seconds)

        if is_prep_exit:
            current_player = white_player if move.is_white else black_player
            opponent = black_player if move.is_white else white_player

            prep_exit = PrepExit(
                player=current_player,
                opponent=opponent,
                exit_move=move.player_move_num,
                time_spent_on_exit=move.time_spent,
                pct_of_time=move.time_spent / base_time,
                color="White" if move.is_white else "Black",
                round_num=game.metadata.round,
                event=game.metadata.event,
                move_san=move.san
            )

            if move.is_white and white_exit is None:
                white_exit = prep_exit
            elif not move.is_white and black_exit is None:
                black_exit = prep_exit

        # Stop once we've found both
        if white_exit is not None and black_exit is not None:
            break

    return white_exit, black_exit


def who_thought_first(
    game: ParsedGame,
    time_control_config: Optional[Dict] = None,
    method: str = "hybrid",
    pct_threshold: float = 0.05,
    absolute_threshold_minutes: int = 10,
    min_move_number: int = 4
) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Determine which player first spent significant time thinking.

    Args:
        game: Parsed game data
        time_control_config: Time control settings
        method: Detection method
        pct_threshold: Percentage threshold
        absolute_threshold_minutes: Absolute threshold in minutes
        min_move_number: Don't count prep exit before this move

    Returns:
        Tuple of (player_name, move_number, color) or (None, None, None)
    """
    white_exit, black_exit = detect_prep_exit(
        game, time_control_config, method,
        pct_threshold, absolute_threshold_minutes, min_move_number
    )

    if white_exit is None and black_exit is None:
        return None, None, None

    if white_exit is None:
        return black_exit.player, black_exit.exit_move, black_exit.color
    if black_exit is None:
        return white_exit.player, white_exit.exit_move, white_exit.color

    # Both exited prep - who was first?
    # Use full move number to compare (white move 5 = full move 9, black move 5 = full move 10)
    white_full_move = (white_exit.exit_move * 2) - 1
    black_full_move = black_exit.exit_move * 2

    if white_full_move <= black_full_move:
        return white_exit.player, white_exit.exit_move, white_exit.color
    else:
        return black_exit.player, black_exit.exit_move, black_exit.color


def analyze_prep_exits(
    games: List[ParsedGame],
    time_control_config: Optional[Dict] = None,
    method: str = "hybrid",
    pct_threshold: float = 0.05,
    absolute_threshold_minutes: int = 10,
    min_move_number: int = 4
) -> Dict[str, PrepStats]:
    """
    Analyze preparation exits across multiple games.

    Args:
        games: List of parsed games
        time_control_config: Time control settings
        method: Detection method
        pct_threshold: Percentage threshold
        absolute_threshold_minutes: Absolute threshold
        min_move_number: Minimum move number for detection

    Returns:
        Dict mapping player name to PrepStats
    """
    stats: Dict[str, PrepStats] = {}

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        # Initialize players
        for player in [white_player, black_player]:
            if player not in stats:
                stats[player] = PrepStats(player_name=player)

        stats[white_player].total_games += 1
        stats[black_player].total_games += 1

        # Detect prep exits
        white_exit, black_exit = detect_prep_exit(
            game, time_control_config, method,
            pct_threshold, absolute_threshold_minutes, min_move_number
        )

        # Record exits
        if white_exit:
            stats[white_player].prep_exits.append(white_exit)
            if white_exit.exit_move < stats[white_player].earliest_exit:
                stats[white_player].earliest_exit = white_exit.exit_move
            if white_exit.exit_move > stats[white_player].latest_exit:
                stats[white_player].latest_exit = white_exit.exit_move

        if black_exit:
            stats[black_player].prep_exits.append(black_exit)
            if black_exit.exit_move < stats[black_player].earliest_exit:
                stats[black_player].earliest_exit = black_exit.exit_move
            if black_exit.exit_move > stats[black_player].latest_exit:
                stats[black_player].latest_exit = black_exit.exit_move

        # Who thought first?
        first_player, _, _ = who_thought_first(
            game, time_control_config, method,
            pct_threshold, absolute_threshold_minutes, min_move_number
        )

        if first_player:
            stats[first_player].times_first_to_think += 1

    # Calculate averages
    for player, player_stats in stats.items():
        if player_stats.prep_exits:
            total_exit_moves = sum(e.exit_move for e in player_stats.prep_exits)
            player_stats.avg_prep_exit_move = total_exit_moves / len(player_stats.prep_exits)
        if player_stats.earliest_exit == 999:
            player_stats.earliest_exit = 0

    return stats


def get_first_to_think_summary(
    games: List[ParsedGame],
    time_control_config: Optional[Dict] = None,
    method: str = "hybrid",
    pct_threshold: float = 0.05,
    absolute_threshold_minutes: int = 10,
    min_move_number: int = 4
) -> List[Tuple[str, str, str, int, str]]:
    """
    Get a summary of who thought first in each game.

    Returns:
        List of (round_num, white_player, black_player, exit_move, first_thinker_color)
    """
    results = []

    for game in games:
        first_player, exit_move, color = who_thought_first(
            game, time_control_config, method,
            pct_threshold, absolute_threshold_minutes, min_move_number
        )

        if first_player:
            results.append((
                game.metadata.round,
                game.metadata.white,
                game.metadata.black,
                exit_move,
                color
            ))

    return results


def print_prep_analysis_report(
    stats: Dict[str, PrepStats],
    first_to_think: List[Tuple[str, str, str, int, str]]
) -> None:
    """
    Print formatted preparation analysis report.

    Args:
        stats: Player prep statistics
        first_to_think: List of first-to-think results per game
    """
    print("\n" + "=" * 100)
    print("PREPARATION ANALYSIS")
    print("=" * 100)

    # Player summary
    print("\n--- Player Prep Summary ---\n")
    print(f"{'Player':<25} {'Games':<8} {'Avg Exit':<10} {'Earliest':<10} {'Latest':<10} {'1st Think':<10}")
    print("-" * 80)

    sorted_stats = sorted(stats.values(), key=lambda x: x.avg_prep_exit_move)

    for s in sorted_stats:
        avg_str = f"Move {s.avg_prep_exit_move:.1f}" if s.avg_prep_exit_move > 0 else "N/A"
        earliest_str = f"Move {s.earliest_exit}" if s.earliest_exit > 0 else "N/A"
        latest_str = f"Move {s.latest_exit}" if s.latest_exit > 0 else "N/A"
        print(f"{s.player_name:<25} "
              f"{s.total_games:<8} "
              f"{avg_str:<10} "
              f"{earliest_str:<10} "
              f"{latest_str:<10} "
              f"{s.times_first_to_think:<10}")

    # Who thought first per game
    print("\n--- Who Thought First (by game) ---\n")
    print(f"{'Round':<8} {'White':<22} {'Black':<22} {'First Thinker':<22} {'Move':<6}")
    print("-" * 85)

    for round_num, white, black, exit_move, color in first_to_think:
        first_thinker = white if color == "White" else black
        print(f"{round_num:<8} {white:<22} {black:<22} {first_thinker:<22} {exit_move:<6}")
