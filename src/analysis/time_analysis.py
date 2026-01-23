"""
Time-based analysis of chess games.
Includes opening time usage, long thinks, and opponent time analysis.
"""

from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict

from ..parsers.pgn_parser import read_pgn_file, ParsedGame
from ..parsers.clock_parser import format_time, get_initial_time


@dataclass
class PlayerTimeStats:
    """Time statistics for a single player."""
    player_name: str
    total_time: int = 0
    white_time: int = 0
    black_time: int = 0
    games_as_white: int = 0
    games_as_black: int = 0

    @property
    def total_games(self) -> int:
        return self.games_as_white + self.games_as_black

    @property
    def avg_time_per_game(self) -> float:
        return self.total_time / self.total_games if self.total_games > 0 else 0


@dataclass
class OpponentTimeStats:
    """Opponent time statistics for a single player."""
    player_name: str
    total_opponent_time: int = 0
    vs_white_time: int = 0  # Time spent by white opponents
    vs_black_time: int = 0  # Time spent by black opponents
    games_as_white: int = 0
    games_as_black: int = 0

    @property
    def total_games(self) -> int:
        return self.games_as_white + self.games_as_black

    @property
    def avg_opponent_time_per_game(self) -> float:
        return self.total_opponent_time / self.total_games if self.total_games > 0 else 0


@dataclass
class LongThink:
    """Record of a long think (20+ minutes on a single move)."""
    player: str
    opponent: str
    time_spent: int
    move_number: int
    color: str  # "White" or "Black"
    round_num: str
    event: str


@dataclass
class LongThinkPct:
    """Record of a long think defined as >X% of total time on a single move."""
    player: str
    opponent: str
    time_spent: int
    pct_of_total: float  # e.g., 0.15 = 15% of base time
    move_number: int
    color: str  # "White" or "Black"
    round_num: str
    event: str
    clock_before: int  # Time remaining before this move
    move_san: str = ""  # The move played


@dataclass
class TimePressureMove:
    """Record of a single move made under time pressure."""
    move_number: int
    clock_remaining: int
    pct_remaining: float
    time_spent: int
    move_san: str
    round_num: str
    opponent: str


@dataclass
class TimePressureStats:
    """Time pressure statistics for a single player."""
    player_name: str
    moves_under_threshold: int = 0
    games_in_pressure: int = 0
    total_games: int = 0
    move_details: List[TimePressureMove] = field(default_factory=list)

    @property
    def avg_moves_in_pressure(self) -> float:
        """Average moves made under time pressure per game where it occurred."""
        return self.moves_under_threshold / self.games_in_pressure if self.games_in_pressure > 0 else 0


def analyze_opening_time(
    games: List[ParsedGame],
    opening_moves: int = 10
) -> Dict[str, PlayerTimeStats]:
    """
    Analyze time spent by each player in the opening (first N moves).

    Args:
        games: List of parsed games
        opening_moves: Number of opening moves to analyze per player

    Returns:
        Dict mapping player name to PlayerTimeStats
    """
    stats = defaultdict(PlayerTimeStats)

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        # Initialize if needed
        if white_player not in stats:
            stats[white_player] = PlayerTimeStats(white_player)
        if black_player not in stats:
            stats[black_player] = PlayerTimeStats(black_player)

        # Calculate time spent in opening
        white_opening_time = 0
        black_opening_time = 0

        for move in game.moves:
            if move.player_move_num > opening_moves:
                break

            if move.time_spent is not None:
                if move.is_white:
                    white_opening_time += move.time_spent
                else:
                    black_opening_time += move.time_spent

        # Update stats
        stats[white_player].total_time += white_opening_time
        stats[white_player].white_time += white_opening_time
        stats[white_player].games_as_white += 1

        stats[black_player].total_time += black_opening_time
        stats[black_player].black_time += black_opening_time
        stats[black_player].games_as_black += 1

    return dict(stats)


def analyze_opponent_opening_time(
    games: List[ParsedGame],
    opening_moves: int = 10
) -> Dict[str, OpponentTimeStats]:
    """
    Analyze time spent by opponents in the opening.
    This shows which players force their opponents to think the most.

    Args:
        games: List of parsed games
        opening_moves: Number of opening moves to analyze per player

    Returns:
        Dict mapping player name to OpponentTimeStats
    """
    stats = defaultdict(OpponentTimeStats)

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        # Initialize if needed
        if white_player not in stats:
            stats[white_player] = OpponentTimeStats(white_player)
        if black_player not in stats:
            stats[black_player] = OpponentTimeStats(black_player)

        # Calculate time spent in opening
        white_opening_time = 0
        black_opening_time = 0

        for move in game.moves:
            if move.player_move_num > opening_moves:
                break

            if move.time_spent is not None:
                if move.is_white:
                    white_opening_time += move.time_spent
                else:
                    black_opening_time += move.time_spent

        # For white player: their opponent (black) spent black_opening_time
        stats[white_player].total_opponent_time += black_opening_time
        stats[white_player].vs_black_time += black_opening_time
        stats[white_player].games_as_white += 1

        # For black player: their opponent (white) spent white_opening_time
        stats[black_player].total_opponent_time += white_opening_time
        stats[black_player].vs_white_time += white_opening_time
        stats[black_player].games_as_black += 1

    return dict(stats)


def find_long_thinks(
    games: List[ParsedGame],
    threshold_seconds: int = 1200  # 20 minutes
) -> Tuple[Dict[str, int], List[LongThink]]:
    """
    Find all instances where players spent significant time on a single move.

    Args:
        games: List of parsed games
        threshold_seconds: Minimum time to qualify as a long think

    Returns:
        Tuple of (player_counts, detailed_list)
        - player_counts: Dict mapping player name to count of long thinks
        - detailed_list: List of LongThink objects with full details
    """
    player_counts = defaultdict(int)
    long_thinks = []

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        for move in game.moves:
            if move.time_spent is not None and move.time_spent >= threshold_seconds:
                current_player = white_player if move.is_white else black_player
                opponent = black_player if move.is_white else white_player

                player_counts[current_player] += 1

                long_thinks.append(LongThink(
                    player=current_player,
                    opponent=opponent,
                    time_spent=move.time_spent,
                    move_number=move.player_move_num,
                    color="White" if move.is_white else "Black",
                    round_num=game.metadata.round,
                    event=game.metadata.event
                ))

    return dict(player_counts), long_thinks


def analyze_time_pressure(
    games: List[ParsedGame],
    time_pressure_threshold: int = 600  # 10 minutes remaining
) -> Dict[str, Dict[str, int]]:
    """
    Analyze how often players get into time pressure.

    Args:
        games: List of parsed games
        time_pressure_threshold: Clock time below which is considered "time pressure"

    Returns:
        Dict mapping player name to stats dict with:
        - games_in_pressure: Count of games where they went below threshold
        - moves_in_pressure: Total moves made under time pressure
    """
    stats = defaultdict(lambda: {"games_in_pressure": 0, "moves_in_pressure": 0})

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        white_in_pressure = False
        black_in_pressure = False

        for move in game.moves:
            if move.clock_remaining is not None:
                if move.clock_remaining < time_pressure_threshold:
                    current_player = white_player if move.is_white else black_player

                    # Mark that this player experienced time pressure in this game
                    if move.is_white and not white_in_pressure:
                        stats[current_player]["games_in_pressure"] += 1
                        white_in_pressure = True
                    elif not move.is_white and not black_in_pressure:
                        stats[current_player]["games_in_pressure"] += 1
                        black_in_pressure = True

                    # Count the move
                    stats[current_player]["moves_in_pressure"] += 1

    return dict(stats)


def find_long_thinks_pct(
    games: List[ParsedGame],
    pct_threshold: float = 0.10,
    time_control_config: Optional[Dict] = None
) -> Tuple[Dict[str, int], List[LongThinkPct]]:
    """
    Find all instances where players spent >X% of their total time on a single move.

    Args:
        games: List of parsed games
        pct_threshold: Percentage of base time to qualify (0.10 = 10%)
        time_control_config: Time control settings (for base time)

    Returns:
        Tuple of (player_counts, detailed_list)
        - player_counts: Dict mapping player name to count of long thinks
        - detailed_list: List of LongThinkPct objects with full details
    """
    player_counts = defaultdict(int)
    long_thinks = []

    # Get base time for percentage calculation
    base_time = get_initial_time(time_control_config) if time_control_config else 7200
    threshold_seconds = base_time * pct_threshold

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        # Track previous clock for each player to calculate clock_before
        white_prev_clock = base_time
        black_prev_clock = base_time

        for move in game.moves:
            if move.time_spent is not None and move.time_spent >= threshold_seconds:
                current_player = white_player if move.is_white else black_player
                opponent = black_player if move.is_white else white_player
                clock_before = white_prev_clock if move.is_white else black_prev_clock

                player_counts[current_player] += 1

                long_thinks.append(LongThinkPct(
                    player=current_player,
                    opponent=opponent,
                    time_spent=move.time_spent,
                    pct_of_total=move.time_spent / base_time,
                    move_number=move.player_move_num,
                    color="White" if move.is_white else "Black",
                    round_num=game.metadata.round,
                    event=game.metadata.event,
                    clock_before=clock_before,
                    move_san=move.san
                ))

            # Update previous clock tracking
            if move.clock_remaining is not None:
                if move.is_white:
                    white_prev_clock = move.clock_remaining
                else:
                    black_prev_clock = move.clock_remaining

    # Sort by percentage of time spent (highest first)
    long_thinks.sort(key=lambda x: x.pct_of_total, reverse=True)

    return dict(player_counts), long_thinks


def analyze_time_pressure_pct(
    games: List[ParsedGame],
    pct_threshold: float = 0.05,
    time_control_config: Optional[Dict] = None
) -> Dict[str, TimePressureStats]:
    """
    Analyze moves made when players have less than X% of their total time remaining.

    Args:
        games: List of parsed games
        pct_threshold: Percentage threshold (0.05 = 5% of base time remaining)
        time_control_config: Time control settings (for base time)

    Returns:
        Dict mapping player name to TimePressureStats
    """
    stats: Dict[str, TimePressureStats] = {}

    # Get base time for percentage calculation
    base_time = get_initial_time(time_control_config) if time_control_config else 7200
    threshold_seconds = base_time * pct_threshold

    for game in games:
        white_player = game.metadata.white
        black_player = game.metadata.black

        # Initialize if needed
        for player in [white_player, black_player]:
            if player not in stats:
                stats[player] = TimePressureStats(player_name=player)

        white_in_pressure_this_game = False
        black_in_pressure_this_game = False

        stats[white_player].total_games += 1
        stats[black_player].total_games += 1

        for move in game.moves:
            if move.clock_remaining is not None and move.clock_remaining < threshold_seconds:
                current_player = white_player if move.is_white else black_player
                opponent = black_player if move.is_white else white_player

                # Track that player experienced pressure in this game
                if move.is_white and not white_in_pressure_this_game:
                    stats[current_player].games_in_pressure += 1
                    white_in_pressure_this_game = True
                elif not move.is_white and not black_in_pressure_this_game:
                    stats[current_player].games_in_pressure += 1
                    black_in_pressure_this_game = True

                # Count the move and record details
                stats[current_player].moves_under_threshold += 1
                stats[current_player].move_details.append(TimePressureMove(
                    move_number=move.player_move_num,
                    clock_remaining=move.clock_remaining,
                    pct_remaining=move.clock_remaining / base_time,
                    time_spent=move.time_spent or 0,
                    move_san=move.san,
                    round_num=game.metadata.round,
                    opponent=opponent
                ))

    return stats


def print_opening_time_report(
    stats: Dict[str, PlayerTimeStats],
    sort_by: str = "total"
) -> None:
    """
    Print a formatted report of opening time analysis.

    Args:
        stats: Player time statistics
        sort_by: Sort key - "total", "white", "black", or "avg"
    """
    # Sort players
    if sort_by == "total":
        sorted_players = sorted(stats.values(), key=lambda x: x.total_time, reverse=True)
    elif sort_by == "white":
        sorted_players = sorted(stats.values(), key=lambda x: x.white_time, reverse=True)
    elif sort_by == "black":
        sorted_players = sorted(stats.values(), key=lambda x: x.black_time, reverse=True)
    elif sort_by == "avg":
        sorted_players = sorted(stats.values(), key=lambda x: x.avg_time_per_game, reverse=True)
    else:
        sorted_players = list(stats.values())

    print(f"{'Player':<30} {'Total Time':<12} {'As White':<12} {'As Black':<12} {'W Games':<8} {'B Games':<8}")
    print("=" * 100)

    for player_stats in sorted_players:
        print(f"{player_stats.player_name:<30} "
              f"{format_time(player_stats.total_time):<12} "
              f"{format_time(player_stats.white_time):<12} "
              f"{format_time(player_stats.black_time):<12} "
              f"{player_stats.games_as_white:<8} "
              f"{player_stats.games_as_black:<8}")


def print_long_thinks_report(
    player_counts: Dict[str, int],
    long_thinks: List[LongThink],
    top_n: int = 10
) -> None:
    """
    Print a formatted report of long thinks analysis.

    Args:
        player_counts: Dict of player names to long think counts
        long_thinks: List of all long thinks
        top_n: Number of longest thinks to show in detail
    """
    # Sort by count
    sorted_counts = sorted(player_counts.items(), key=lambda x: x[1], reverse=True)

    print(f"{'Player':<30} {'Times 20+ min':<15}")
    print("=" * 45)
    for player, count in sorted_counts:
        print(f"{player:<30} {count:<15}")

    # Show longest thinks
    print("\n" + "=" * 110)
    print(f"\nTop {top_n} longest thinks:\n")

    sorted_thinks = sorted(long_thinks, key=lambda x: x.time_spent, reverse=True)[:top_n]

    print(f"{'Player':<25} {'Time':<10} {'Move':<8} {'Color':<8} {'vs Opponent':<25} {'Round':<10}")
    print("=" * 110)

    for think in sorted_thinks:
        print(f"{think.player:<25} "
              f"{format_time(think.time_spent, 'MM:SS'):<10} "
              f"{think.move_number:<8} "
              f"{think.color:<8} "
              f"{think.opponent:<25} "
              f"{think.round_num:<10}")


def print_long_thinks_pct_report(
    player_counts: Dict[str, int],
    long_thinks: List[LongThinkPct],
    pct_threshold: float = 0.10,
    top_n: int = 10
) -> None:
    """
    Print a formatted report of percentage-based long thinks analysis.

    Args:
        player_counts: Dict of player names to long think counts
        long_thinks: List of all long thinks
        pct_threshold: The threshold used (for display)
        top_n: Number of longest thinks to show in detail
    """
    pct_display = int(pct_threshold * 100)

    print("\n" + "=" * 110)
    print(f"LONG THINKS (>{pct_display}% of total time on a single move)")
    print("=" * 110)

    # Sort by count
    sorted_counts = sorted(player_counts.items(), key=lambda x: x[1], reverse=True)

    print(f"\n{'Player':<30} {'Count':<10}")
    print("-" * 40)
    for player, count in sorted_counts:
        print(f"{player:<30} {count:<10}")

    # Show longest thinks
    print("\n" + "-" * 110)
    print(f"\nTop {top_n} longest thinks:\n")

    print(f"{'Player':<22} {'Time':<8} {'% Total':<10} {'Move':<6} {'As':<6} {'vs Opponent':<22} {'Round':<8}")
    print("-" * 110)

    for think in long_thinks[:top_n]:
        pct_str = f"{think.pct_of_total*100:.1f}%"
        print(f"{think.player:<22} "
              f"{format_time(think.time_spent, 'MM:SS'):<8} "
              f"{pct_str:<10} "
              f"{think.move_number:<6} "
              f"{think.color:<6} "
              f"{think.opponent:<22} "
              f"{think.round_num:<8}")


def print_time_pressure_pct_report(
    stats: Dict[str, TimePressureStats],
    pct_threshold: float = 0.05
) -> None:
    """
    Print a formatted report of percentage-based time pressure analysis.

    Args:
        stats: Player time pressure statistics
        pct_threshold: The threshold used (for display)
    """
    pct_display = int(pct_threshold * 100)

    print("\n" + "=" * 100)
    print(f"TIME PRESSURE ANALYSIS (<{pct_display}% of time remaining)")
    print("=" * 100)

    # Sort by moves under pressure
    sorted_stats = sorted(stats.values(), key=lambda x: x.moves_under_threshold, reverse=True)

    print(f"\n{'Player':<25} {'Moves':<10} {'Games':<10} {'Total Games':<12} {'Pressure %':<12}")
    print("-" * 75)

    for s in sorted_stats:
        pressure_pct = (s.games_in_pressure / s.total_games * 100) if s.total_games > 0 else 0
        print(f"{s.player_name:<25} "
              f"{s.moves_under_threshold:<10} "
              f"{s.games_in_pressure:<10} "
              f"{s.total_games:<12} "
              f"{pressure_pct:.1f}%")
