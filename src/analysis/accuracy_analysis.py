"""
Accuracy analysis functions for chess games.
Includes player stats, comeback detection, blown lead detection,
and accuracy correlation with thinking time.
"""

from typing import List, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from collections import defaultdict

from .engine_analysis import GameEvaluation, MoveEvaluation, calculate_accuracy

if TYPE_CHECKING:
    from ..parsers.pgn_parser import ParsedGame


@dataclass
class PlayerAccuracyStats:
    """Aggregate accuracy statistics for a player across games."""
    player_name: str
    total_games: int = 0
    total_moves: int = 0
    total_cpl: float = 0.0
    blunders: int = 0  # CPL > 200
    mistakes: int = 0  # CPL 50-200
    inaccuracies: int = 0  # CPL 20-50

    # Time correlation (accuracy by think time)
    moves_under_5min: int = 0
    moves_5_to_15min: int = 0
    moves_over_15min: int = 0
    cpl_under_5min: float = 0.0
    cpl_5_to_15min: float = 0.0
    cpl_over_15min: float = 0.0

    @property
    def avg_cpl(self) -> float:
        """Average centipawn loss per move."""
        return self.total_cpl / self.total_moves if self.total_moves > 0 else 0.0

    @property
    def accuracy_pct(self) -> float:
        """Overall accuracy percentage."""
        return calculate_accuracy(self.avg_cpl)

    @property
    def avg_cpl_under_5min(self) -> float:
        """Average CPL on moves under 5 minutes."""
        return self.cpl_under_5min / self.moves_under_5min if self.moves_under_5min > 0 else 0.0

    @property
    def avg_cpl_5_to_15min(self) -> float:
        """Average CPL on moves between 5-15 minutes."""
        return self.cpl_5_to_15min / self.moves_5_to_15min if self.moves_5_to_15min > 0 else 0.0

    @property
    def avg_cpl_over_15min(self) -> float:
        """Average CPL on moves over 15 minutes."""
        return self.cpl_over_15min / self.moves_over_15min if self.moves_over_15min > 0 else 0.0

    @property
    def accuracy_under_5min(self) -> float:
        """Accuracy on quick moves."""
        return calculate_accuracy(self.avg_cpl_under_5min)

    @property
    def accuracy_5_to_15min(self) -> float:
        """Accuracy on medium thinks."""
        return calculate_accuracy(self.avg_cpl_5_to_15min)

    @property
    def accuracy_over_15min(self) -> float:
        """Accuracy on deep thinks (15+ min)."""
        return calculate_accuracy(self.avg_cpl_over_15min)


@dataclass
class ComebackRecord:
    """Record of a player coming back from a losing position."""
    player: str
    opponent: str
    game_id: str
    worst_eval: int  # Centipawns (negative = bad for player)
    result: str  # "1-0", "0-1", or "1/2-1/2"
    recovery_moves: int  # Moves from worst position to draw/win
    played_as_white: bool


@dataclass
class BlownLeadRecord:
    """Record of a player squandering a winning position."""
    player: str
    opponent: str
    game_id: str
    best_eval: int  # Centipawns (positive = good for player)
    result: str
    collapse_moves: int  # Moves from best position to draw/loss
    played_as_white: bool


@dataclass
class TimePressureAccuracy:
    """Accuracy statistics when under time pressure."""
    player_name: str
    moves_under_threshold: int = 0
    total_cpl_under_pressure: float = 0.0
    blunders_under_pressure: int = 0
    mistakes_under_pressure: int = 0

    @property
    def avg_cpl_under_pressure(self) -> float:
        """Average CPL when under time pressure."""
        return self.total_cpl_under_pressure / self.moves_under_threshold if self.moves_under_threshold > 0 else 0.0

    @property
    def accuracy_under_pressure(self) -> float:
        """Accuracy percentage when under time pressure."""
        return calculate_accuracy(self.avg_cpl_under_pressure)


@dataclass
class LongThinkAccuracy:
    """Accuracy statistics on long thinks."""
    player_name: str
    long_think_count: int = 0
    total_cpl_on_long_thinks: float = 0.0
    blunders_on_long_thinks: int = 0
    perfect_moves: int = 0  # CPL < 5

    @property
    def avg_cpl_on_long_thinks(self) -> float:
        """Average CPL on long thinks."""
        return self.total_cpl_on_long_thinks / self.long_think_count if self.long_think_count > 0 else 0.0

    @property
    def accuracy_on_long_thinks(self) -> float:
        """Accuracy percentage on long thinks."""
        return calculate_accuracy(self.avg_cpl_on_long_thinks)

    @property
    def perfect_rate(self) -> float:
        """Percentage of long thinks that were near-perfect."""
        return (self.perfect_moves / self.long_think_count * 100) if self.long_think_count > 0 else 0.0


def calculate_player_accuracy(
    game_evals: List[GameEvaluation]
) -> Dict[str, PlayerAccuracyStats]:
    """
    Calculate aggregate accuracy statistics for each player.

    Args:
        game_evals: List of game evaluations

    Returns:
        Dict mapping player name to PlayerAccuracyStats
    """
    stats: Dict[str, PlayerAccuracyStats] = {}

    for game_eval in game_evals:
        # Initialize players if needed
        for player in [game_eval.white_player, game_eval.black_player]:
            if player not in stats:
                stats[player] = PlayerAccuracyStats(player_name=player)

        white_stats = stats[game_eval.white_player]
        black_stats = stats[game_eval.black_player]

        white_stats.total_games += 1
        black_stats.total_games += 1

        for move_eval in game_eval.move_evaluations:
            player_stats = white_stats if move_eval.is_white else black_stats

            player_stats.total_moves += 1
            player_stats.total_cpl += move_eval.centipawn_loss

            # Count move quality
            if move_eval.is_blunder:
                player_stats.blunders += 1
            elif move_eval.is_mistake:
                player_stats.mistakes += 1
            elif move_eval.is_inaccuracy:
                player_stats.inaccuracies += 1

            # Time correlation
            if move_eval.time_spent is not None:
                time_minutes = move_eval.time_spent / 60

                if time_minutes < 5:
                    player_stats.moves_under_5min += 1
                    player_stats.cpl_under_5min += move_eval.centipawn_loss
                elif time_minutes < 15:
                    player_stats.moves_5_to_15min += 1
                    player_stats.cpl_5_to_15min += move_eval.centipawn_loss
                else:
                    player_stats.moves_over_15min += 1
                    player_stats.cpl_over_15min += move_eval.centipawn_loss

    return stats


def find_comebacks(
    game_evals: List[GameEvaluation],
    threshold_cp: int = 200
) -> List[ComebackRecord]:
    """
    Find games where a player recovered from a losing position to draw or win.

    A comeback is when:
    - Player was at -threshold_cp or worse (from their perspective)
    - Player ended up drawing or winning

    Args:
        game_evals: List of game evaluations
        threshold_cp: Centipawn threshold for "losing" (default 200 = -2.0)

    Returns:
        List of ComebackRecord objects, sorted by magnitude of comeback
    """
    comebacks = []

    for game_eval in game_evals:
        # Check white's perspective
        if game_eval.min_white_eval <= -threshold_cp:
            # White was losing
            if game_eval.result in ["1-0", "1/2-1/2"]:
                # White drew or won
                comebacks.append(ComebackRecord(
                    player=game_eval.white_player,
                    opponent=game_eval.black_player,
                    game_id=game_eval.game_id,
                    worst_eval=game_eval.min_white_eval,
                    result=game_eval.result,
                    recovery_moves=_count_recovery_moves(
                        game_eval.move_evaluations,
                        game_eval.min_white_eval,
                        is_white=True
                    ),
                    played_as_white=True
                ))

        # Check black's perspective (invert evals)
        if game_eval.max_white_eval >= threshold_cp:
            # Black was losing (white was winning)
            if game_eval.result in ["0-1", "1/2-1/2"]:
                # Black drew or won
                comebacks.append(ComebackRecord(
                    player=game_eval.black_player,
                    opponent=game_eval.white_player,
                    game_id=game_eval.game_id,
                    worst_eval=-game_eval.max_white_eval,  # From black's view
                    result=game_eval.result,
                    recovery_moves=_count_recovery_moves(
                        game_eval.move_evaluations,
                        game_eval.max_white_eval,
                        is_white=False
                    ),
                    played_as_white=False
                ))

    # Sort by magnitude of comeback (most impressive first)
    comebacks.sort(key=lambda x: x.worst_eval)

    return comebacks


def find_blown_leads(
    game_evals: List[GameEvaluation],
    threshold_cp: int = 200
) -> List[BlownLeadRecord]:
    """
    Find games where a player squandered a winning position.

    A blown lead is when:
    - Player was at +threshold_cp or better (from their perspective)
    - Player ended up drawing or losing

    Args:
        game_evals: List of game evaluations
        threshold_cp: Centipawn threshold for "winning" (default 200 = +2.0)

    Returns:
        List of BlownLeadRecord objects, sorted by magnitude
    """
    blown_leads = []

    for game_eval in game_evals:
        # Check white's perspective
        if game_eval.max_white_eval >= threshold_cp:
            # White was winning
            if game_eval.result in ["0-1", "1/2-1/2"]:
                # White drew or lost
                blown_leads.append(BlownLeadRecord(
                    player=game_eval.white_player,
                    opponent=game_eval.black_player,
                    game_id=game_eval.game_id,
                    best_eval=game_eval.max_white_eval,
                    result=game_eval.result,
                    collapse_moves=_count_collapse_moves(
                        game_eval.move_evaluations,
                        game_eval.max_white_eval,
                        is_white=True
                    ),
                    played_as_white=True
                ))

        # Check black's perspective
        if game_eval.min_white_eval <= -threshold_cp:
            # Black was winning (white was losing)
            if game_eval.result in ["1-0", "1/2-1/2"]:
                # Black drew or lost
                blown_leads.append(BlownLeadRecord(
                    player=game_eval.black_player,
                    opponent=game_eval.white_player,
                    game_id=game_eval.game_id,
                    best_eval=-game_eval.min_white_eval,  # From black's view
                    result=game_eval.result,
                    collapse_moves=_count_collapse_moves(
                        game_eval.move_evaluations,
                        game_eval.min_white_eval,
                        is_white=False
                    ),
                    played_as_white=False
                ))

    # Sort by magnitude (biggest blown leads first)
    blown_leads.sort(key=lambda x: -x.best_eval)

    return blown_leads


def calculate_time_pressure_accuracy(
    game_evals: List[GameEvaluation],
    games: List["ParsedGame"],
    pct_threshold: float = 0.05,
    base_time: int = 7200
) -> Dict[str, TimePressureAccuracy]:
    """
    Calculate accuracy statistics for moves made under time pressure.

    Args:
        game_evals: List of game evaluations (with engine analysis)
        games: List of parsed games (with clock data)
        pct_threshold: Percentage threshold (0.05 = 5% remaining)
        base_time: Base time in seconds for percentage calculation

    Returns:
        Dict mapping player name to TimePressureAccuracy
    """
    stats: Dict[str, TimePressureAccuracy] = {}
    threshold_seconds = base_time * pct_threshold

    # Create a mapping from game_id to parsed game for clock data
    game_map = {}
    for game in games:
        game_id = f"{game.metadata.white} vs {game.metadata.black} R{game.metadata.round}"
        game_map[game_id] = game

    for game_eval in game_evals:
        # Get the corresponding parsed game with clock data
        parsed_game = game_map.get(game_eval.game_id)
        if not parsed_game:
            continue

        # Build move number -> clock remaining mapping
        clock_data = {}
        for move in parsed_game.moves:
            key = (move.move_number, move.is_white)
            clock_data[key] = move.clock_remaining

        # Initialize players
        for player in [game_eval.white_player, game_eval.black_player]:
            if player not in stats:
                stats[player] = TimePressureAccuracy(player_name=player)

        # Check each evaluated move
        for move_eval in game_eval.move_evaluations:
            key = (move_eval.move_number, move_eval.is_white)
            clock_remaining = clock_data.get(key)

            if clock_remaining is not None and clock_remaining < threshold_seconds:
                player = game_eval.white_player if move_eval.is_white else game_eval.black_player
                stats[player].moves_under_threshold += 1
                stats[player].total_cpl_under_pressure += move_eval.centipawn_loss

                if move_eval.is_blunder:
                    stats[player].blunders_under_pressure += 1
                elif move_eval.is_mistake:
                    stats[player].mistakes_under_pressure += 1

    return stats


def calculate_long_think_accuracy(
    game_evals: List[GameEvaluation],
    pct_threshold: float = 0.10,
    base_time: int = 7200
) -> Dict[str, LongThinkAccuracy]:
    """
    Calculate accuracy statistics for long thinks (>X% of total time).

    Args:
        game_evals: List of game evaluations
        pct_threshold: Percentage threshold (0.10 = 10% of base time)
        base_time: Base time in seconds

    Returns:
        Dict mapping player name to LongThinkAccuracy
    """
    stats: Dict[str, LongThinkAccuracy] = {}
    threshold_seconds = base_time * pct_threshold

    for game_eval in game_evals:
        # Initialize players
        for player in [game_eval.white_player, game_eval.black_player]:
            if player not in stats:
                stats[player] = LongThinkAccuracy(player_name=player)

        for move_eval in game_eval.move_evaluations:
            if move_eval.time_spent is not None and move_eval.time_spent >= threshold_seconds:
                player = game_eval.white_player if move_eval.is_white else game_eval.black_player

                stats[player].long_think_count += 1
                stats[player].total_cpl_on_long_thinks += move_eval.centipawn_loss

                if move_eval.is_blunder:
                    stats[player].blunders_on_long_thinks += 1

                if move_eval.centipawn_loss < 5:
                    stats[player].perfect_moves += 1

    return stats


def _count_recovery_moves(
    move_evals: List[MoveEvaluation],
    worst_eval: int,
    is_white: bool
) -> int:
    """Count moves from worst position to end of game."""
    found_worst = False
    count = 0

    for move_eval in move_evals:
        if not found_worst:
            # Find the worst position
            eval_from_white = (
                -move_eval.eval_after if move_eval.is_white
                else move_eval.eval_after
            )
            if is_white and eval_from_white == worst_eval:
                found_worst = True
            elif not is_white and eval_from_white == -worst_eval:
                found_worst = True
        else:
            # Count remaining moves by the player
            if move_eval.is_white == is_white:
                count += 1

    return count


def _count_collapse_moves(
    move_evals: List[MoveEvaluation],
    best_eval: int,
    is_white: bool
) -> int:
    """Count moves from best position to end of game."""
    found_best = False
    count = 0

    for move_eval in move_evals:
        if not found_best:
            eval_from_white = (
                -move_eval.eval_after if move_eval.is_white
                else move_eval.eval_after
            )
            if is_white and eval_from_white == best_eval:
                found_best = True
            elif not is_white and eval_from_white == -best_eval:
                found_best = True
        else:
            if move_eval.is_white == is_white:
                count += 1

    return count


def print_accuracy_report(
    stats: Dict[str, PlayerAccuracyStats],
    sort_by: str = "accuracy"
) -> None:
    """
    Print formatted accuracy report.

    Args:
        stats: Player accuracy statistics
        sort_by: Sort key - "accuracy", "cpl", "games", "blunders"
    """
    # Sort players
    if sort_by == "accuracy":
        sorted_stats = sorted(stats.values(), key=lambda x: -x.accuracy_pct)
    elif sort_by == "cpl":
        sorted_stats = sorted(stats.values(), key=lambda x: x.avg_cpl)
    elif sort_by == "games":
        sorted_stats = sorted(stats.values(), key=lambda x: -x.total_games)
    elif sort_by == "blunders":
        sorted_stats = sorted(stats.values(), key=lambda x: x.blunders)
    else:
        sorted_stats = list(stats.values())

    print("\n" + "=" * 100)
    print("PLAYER ACCURACY REPORT")
    print("=" * 100)

    print(f"\n{'Player':<25} {'Accuracy':<10} {'Avg CPL':<10} "
          f"{'Blunders':<10} {'Mistakes':<10} {'Games':<8}")
    print("-" * 80)

    for s in sorted_stats:
        print(f"{s.player_name:<25} {s.accuracy_pct:>7.1f}%  "
              f"{s.avg_cpl:>8.1f}  {s.blunders:>8}  "
              f"{s.mistakes:>8}  {s.total_games:>6}")

    # Time-based accuracy
    print("\n" + "=" * 100)
    print("ACCURACY BY THINKING TIME")
    print("=" * 100)

    print(f"\n{'Player':<25} {'<5 min':<15} {'5-15 min':<15} {'>15 min':<15}")
    print("-" * 70)

    for s in sorted_stats:
        under5 = f"{s.accuracy_under_5min:.1f}% ({s.moves_under_5min})"
        mid = f"{s.accuracy_5_to_15min:.1f}% ({s.moves_5_to_15min})"
        over15 = f"{s.accuracy_over_15min:.1f}% ({s.moves_over_15min})"
        print(f"{s.player_name:<25} {under5:<15} {mid:<15} {over15:<15}")


def print_comeback_report(comebacks: List[ComebackRecord], top_n: int = 10) -> None:
    """Print formatted comeback report."""
    print("\n" + "=" * 100)
    print(f"TOP {top_n} BIGGEST COMEBACKS")
    print("=" * 100)

    print(f"\n{'Player':<25} {'Worst Eval':<12} {'Result':<10} "
          f"{'Opponent':<25} {'As':<6}")
    print("-" * 85)

    for comeback in comebacks[:top_n]:
        eval_str = f"{comeback.worst_eval/100:+.2f}"
        color = "White" if comeback.played_as_white else "Black"
        print(f"{comeback.player:<25} {eval_str:<12} {comeback.result:<10} "
              f"{comeback.opponent:<25} {color:<6}")


def print_blown_lead_report(blown_leads: List[BlownLeadRecord], top_n: int = 10) -> None:
    """Print formatted blown lead report."""
    print("\n" + "=" * 100)
    print(f"TOP {top_n} BIGGEST BLOWN LEADS")
    print("=" * 100)

    print(f"\n{'Player':<25} {'Best Eval':<12} {'Result':<10} "
          f"{'Opponent':<25} {'As':<6}")
    print("-" * 85)

    for blown in blown_leads[:top_n]:
        eval_str = f"{blown.best_eval/100:+.2f}"
        color = "White" if blown.played_as_white else "Black"
        print(f"{blown.player:<25} {eval_str:<12} {blown.result:<10} "
              f"{blown.opponent:<25} {color:<6}")


def print_time_pressure_accuracy_report(
    stats: Dict[str, TimePressureAccuracy],
    pct_threshold: float = 0.05
) -> None:
    """Print formatted time pressure accuracy report."""
    pct_display = int(pct_threshold * 100)

    print("\n" + "=" * 100)
    print(f"ACCURACY UNDER TIME PRESSURE (<{pct_display}% time remaining)")
    print("=" * 100)

    # Sort by moves under pressure
    sorted_stats = sorted(
        [s for s in stats.values() if s.moves_under_threshold > 0],
        key=lambda x: x.moves_under_threshold,
        reverse=True
    )

    if not sorted_stats:
        print("\nNo moves found under time pressure threshold.")
        return

    print(f"\n{'Player':<25} {'Moves':<8} {'Accuracy':<10} {'Avg CPL':<10} {'Blunders':<10} {'Mistakes':<10}")
    print("-" * 80)

    for s in sorted_stats:
        print(f"{s.player_name:<25} "
              f"{s.moves_under_threshold:<8} "
              f"{s.accuracy_under_pressure:>6.1f}%   "
              f"{s.avg_cpl_under_pressure:>8.1f} "
              f"{s.blunders_under_pressure:>8} "
              f"{s.mistakes_under_pressure:>8}")


def print_long_think_accuracy_report(
    stats: Dict[str, LongThinkAccuracy],
    pct_threshold: float = 0.10
) -> None:
    """Print formatted long think accuracy report."""
    pct_display = int(pct_threshold * 100)

    print("\n" + "=" * 100)
    print(f"ACCURACY ON LONG THINKS (>{pct_display}% of total time)")
    print("=" * 100)

    # Sort by accuracy (highest first)
    sorted_stats = sorted(
        [s for s in stats.values() if s.long_think_count > 0],
        key=lambda x: x.accuracy_on_long_thinks,
        reverse=True
    )

    if not sorted_stats:
        print("\nNo long thinks found.")
        return

    print(f"\n{'Player':<25} {'Count':<8} {'Accuracy':<10} {'Avg CPL':<10} {'Perfect':<10} {'Blunders':<10}")
    print("-" * 85)

    for s in sorted_stats:
        perfect_str = f"{s.perfect_moves} ({s.perfect_rate:.0f}%)"
        print(f"{s.player_name:<25} "
              f"{s.long_think_count:<8} "
              f"{s.accuracy_on_long_thinks:>6.1f}%   "
              f"{s.avg_cpl_on_long_thinks:>8.1f} "
              f"{perfect_str:<10} "
              f"{s.blunders_on_long_thinks:>8}")
