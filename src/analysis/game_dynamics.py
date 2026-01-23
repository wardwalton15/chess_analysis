"""
Game dynamics analysis for chess games.
Includes dominance (controlling the game) and resilience (holding under pressure) metrics.
"""

from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .engine_analysis import GameEvaluation, MoveEvaluation


@dataclass
class GameDominance:
    """Dominance metrics for a single game."""
    game_id: str
    white_player: str
    black_player: str
    white_dominance: float  # 0-100 score
    black_dominance: float
    white_moves_ahead: int
    black_moves_ahead: int
    white_longest_streak: int
    black_longest_streak: int
    white_avg_advantage: float  # Average eval when ahead
    black_avg_advantage: float


@dataclass
class DominanceMetrics:
    """Aggregate dominance statistics for a player."""
    player_name: str
    games_analyzed: int = 0
    total_dominance_score: float = 0.0
    games_dominated: int = 0  # Games where dominance > threshold
    total_moves_with_advantage: int = 0
    longest_advantage_streak: int = 0
    total_advantage_magnitude: float = 0.0  # Sum of evals when ahead
    moves_counted_for_advantage: int = 0

    @property
    def avg_dominance_score(self) -> float:
        """Average dominance score across games."""
        return self.total_dominance_score / self.games_analyzed if self.games_analyzed > 0 else 0.0

    @property
    def avg_advantage_when_ahead(self) -> float:
        """Average centipawn advantage when in a winning position."""
        return self.total_advantage_magnitude / self.moves_counted_for_advantage if self.moves_counted_for_advantage > 0 else 0.0

    @property
    def dominance_rate(self) -> float:
        """Percentage of games where player dominated."""
        return (self.games_dominated / self.games_analyzed * 100) if self.games_analyzed > 0 else 0.0


@dataclass
class GameResilience:
    """Resilience metrics for a single game."""
    game_id: str
    white_player: str
    black_player: str
    white_resilience: float  # 0-100 score
    black_resilience: float
    white_positions_defended: int
    black_positions_defended: int
    white_collapses: int  # Blunders when already worse
    black_collapses: int


@dataclass
class ResilienceMetrics:
    """Aggregate resilience statistics for a player."""
    player_name: str
    games_analyzed: int = 0
    total_resilience_score: float = 0.0
    total_positions_defended: int = 0  # Bad positions held without blundering
    total_difficult_positions: int = 0  # Total bad positions faced
    total_collapses: int = 0  # Blunders when already worse
    total_cpl_when_worse: float = 0.0
    moves_when_worse: int = 0

    @property
    def avg_resilience_score(self) -> float:
        """Average resilience score across games."""
        return self.total_resilience_score / self.games_analyzed if self.games_analyzed > 0 else 0.0

    @property
    def defense_rate(self) -> float:
        """Percentage of bad positions successfully defended."""
        return (self.total_positions_defended / self.total_difficult_positions * 100) if self.total_difficult_positions > 0 else 100.0

    @property
    def collapse_rate(self) -> float:
        """Percentage of bad positions where player blundered."""
        return (self.total_collapses / self.total_difficult_positions * 100) if self.total_difficult_positions > 0 else 0.0

    @property
    def avg_cpl_when_worse(self) -> float:
        """Average CPL when in difficult positions."""
        return self.total_cpl_when_worse / self.moves_when_worse if self.moves_when_worse > 0 else 0.0


def calculate_game_dominance(
    game_eval: GameEvaluation,
    advantage_threshold: int = 50
) -> GameDominance:
    """
    Calculate dominance metrics for a single game.

    Dominance measures how much a player controlled the game:
    - % of moves with advantage (eval > threshold from player's view)
    - Average advantage magnitude when ahead
    - Longest streak of consecutive advantageous positions

    Args:
        game_eval: Game evaluation data
        advantage_threshold: Centipawns to be considered "ahead" (default 50 = +0.5)

    Returns:
        GameDominance with metrics for both players
    """
    white_ahead_count = 0
    black_ahead_count = 0
    white_advantage_sum = 0.0
    black_advantage_sum = 0.0

    # Track streaks
    white_current_streak = 0
    black_current_streak = 0
    white_max_streak = 0
    black_max_streak = 0

    total_positions = len(game_eval.move_evaluations)

    for move_eval in game_eval.move_evaluations:
        # Get eval from white's perspective after the move
        # After white's move, eval_after is from black's perspective, so negate
        # After black's move, eval_after is from white's perspective
        if move_eval.is_white:
            current_eval = -move_eval.eval_after
        else:
            current_eval = move_eval.eval_after

        if current_eval > advantage_threshold:
            # White is ahead
            white_ahead_count += 1
            white_advantage_sum += current_eval
            white_current_streak += 1
            white_max_streak = max(white_max_streak, white_current_streak)
            black_current_streak = 0
        elif current_eval < -advantage_threshold:
            # Black is ahead
            black_ahead_count += 1
            black_advantage_sum += abs(current_eval)
            black_current_streak += 1
            black_max_streak = max(black_max_streak, black_current_streak)
            white_current_streak = 0
        else:
            # Roughly equal
            white_current_streak = 0
            black_current_streak = 0

    # Calculate dominance scores (0-100)
    # Based on: % moves ahead + bonus for streak + bonus for magnitude
    if total_positions > 0:
        white_pct_ahead = (white_ahead_count / total_positions) * 100
        black_pct_ahead = (black_ahead_count / total_positions) * 100

        white_avg_adv = white_advantage_sum / white_ahead_count if white_ahead_count > 0 else 0
        black_avg_adv = black_advantage_sum / black_ahead_count if black_ahead_count > 0 else 0

        # Dominance score: 60% from percentage ahead, 20% from streak, 20% from magnitude
        # Normalize magnitude contribution (cap at 300cp = full bonus)
        white_mag_bonus = min(20, (white_avg_adv / 300) * 20)
        black_mag_bonus = min(20, (black_avg_adv / 300) * 20)

        # Streak bonus (cap at 10 moves = full bonus)
        white_streak_bonus = min(20, (white_max_streak / 10) * 20)
        black_streak_bonus = min(20, (black_max_streak / 10) * 20)

        white_dominance = (white_pct_ahead * 0.6) + white_streak_bonus + white_mag_bonus
        black_dominance = (black_pct_ahead * 0.6) + black_streak_bonus + black_mag_bonus
    else:
        white_dominance = 0
        black_dominance = 0
        white_avg_adv = 0
        black_avg_adv = 0

    return GameDominance(
        game_id=game_eval.game_id,
        white_player=game_eval.white_player,
        black_player=game_eval.black_player,
        white_dominance=white_dominance,
        black_dominance=black_dominance,
        white_moves_ahead=white_ahead_count,
        black_moves_ahead=black_ahead_count,
        white_longest_streak=white_max_streak,
        black_longest_streak=black_max_streak,
        white_avg_advantage=white_avg_adv,
        black_avg_advantage=black_avg_adv
    )


def calculate_game_resilience(
    game_eval: GameEvaluation,
    pressure_threshold: int = -150,
    collapse_cpl: int = 200
) -> GameResilience:
    """
    Calculate resilience metrics for a single game.

    Resilience measures ability to hold difficult positions:
    - % of bad positions held without blundering
    - Average CPL when in bad positions
    - Collapse rate (blunders when already worse)

    Args:
        game_eval: Game evaluation data
        pressure_threshold: Centipawns to be "under pressure" (default -150 from player's view)
        collapse_cpl: CPL threshold for a "collapse" (blunder when worse)

    Returns:
        GameResilience with metrics for both players
    """
    white_difficult = 0
    black_difficult = 0
    white_defended = 0
    black_defended = 0
    white_collapses = 0
    black_collapses = 0
    white_cpl_when_worse = 0.0
    black_cpl_when_worse = 0.0

    for move_eval in game_eval.move_evaluations:
        # Get eval from each player's perspective before their move
        if move_eval.is_white:
            player_eval_before = move_eval.eval_before
        else:
            player_eval_before = -move_eval.eval_before

        # Check if player was in a difficult position before moving
        if move_eval.is_white and player_eval_before <= pressure_threshold:
            white_difficult += 1
            white_cpl_when_worse += move_eval.centipawn_loss

            if move_eval.centipawn_loss >= collapse_cpl:
                white_collapses += 1
            else:
                white_defended += 1

        elif not move_eval.is_white and player_eval_before <= pressure_threshold:
            black_difficult += 1
            black_cpl_when_worse += move_eval.centipawn_loss

            if move_eval.centipawn_loss >= collapse_cpl:
                black_collapses += 1
            else:
                black_defended += 1

    # Calculate resilience scores (0-100)
    # Based on defense rate and average CPL when worse
    if white_difficult > 0:
        white_defense_rate = white_defended / white_difficult
        white_avg_cpl_worse = white_cpl_when_worse / white_difficult
        # Lower CPL when worse = more resilient
        white_cpl_bonus = max(0, 50 - (white_avg_cpl_worse / 4))  # Cap at 50 bonus
        white_resilience = (white_defense_rate * 50) + white_cpl_bonus
    else:
        white_resilience = 100  # Never in trouble = perfect resilience

    if black_difficult > 0:
        black_defense_rate = black_defended / black_difficult
        black_avg_cpl_worse = black_cpl_when_worse / black_difficult
        black_cpl_bonus = max(0, 50 - (black_avg_cpl_worse / 4))
        black_resilience = (black_defense_rate * 50) + black_cpl_bonus
    else:
        black_resilience = 100

    return GameResilience(
        game_id=game_eval.game_id,
        white_player=game_eval.white_player,
        black_player=game_eval.black_player,
        white_resilience=white_resilience,
        black_resilience=black_resilience,
        white_positions_defended=white_defended,
        black_positions_defended=black_defended,
        white_collapses=white_collapses,
        black_collapses=black_collapses
    )


def analyze_dominance(
    game_evals: List[GameEvaluation],
    advantage_threshold: int = 50,
    dominance_threshold: float = 60.0
) -> Dict[str, DominanceMetrics]:
    """
    Analyze dominance across multiple games.

    Args:
        game_evals: List of game evaluations
        advantage_threshold: Centipawns to be "ahead"
        dominance_threshold: Score to count as "dominated game"

    Returns:
        Dict mapping player name to DominanceMetrics
    """
    stats: Dict[str, DominanceMetrics] = {}

    for game_eval in game_evals:
        game_dom = calculate_game_dominance(game_eval, advantage_threshold)

        # Initialize players
        for player in [game_eval.white_player, game_eval.black_player]:
            if player not in stats:
                stats[player] = DominanceMetrics(player_name=player)

        # White's stats
        white_stats = stats[game_eval.white_player]
        white_stats.games_analyzed += 1
        white_stats.total_dominance_score += game_dom.white_dominance
        white_stats.total_moves_with_advantage += game_dom.white_moves_ahead
        white_stats.longest_advantage_streak = max(
            white_stats.longest_advantage_streak, game_dom.white_longest_streak
        )
        if game_dom.white_moves_ahead > 0:
            white_stats.total_advantage_magnitude += game_dom.white_avg_advantage * game_dom.white_moves_ahead
            white_stats.moves_counted_for_advantage += game_dom.white_moves_ahead
        if game_dom.white_dominance >= dominance_threshold:
            white_stats.games_dominated += 1

        # Black's stats
        black_stats = stats[game_eval.black_player]
        black_stats.games_analyzed += 1
        black_stats.total_dominance_score += game_dom.black_dominance
        black_stats.total_moves_with_advantage += game_dom.black_moves_ahead
        black_stats.longest_advantage_streak = max(
            black_stats.longest_advantage_streak, game_dom.black_longest_streak
        )
        if game_dom.black_moves_ahead > 0:
            black_stats.total_advantage_magnitude += game_dom.black_avg_advantage * game_dom.black_moves_ahead
            black_stats.moves_counted_for_advantage += game_dom.black_moves_ahead
        if game_dom.black_dominance >= dominance_threshold:
            black_stats.games_dominated += 1

    return stats


def analyze_resilience(
    game_evals: List[GameEvaluation],
    pressure_threshold: int = -150,
    collapse_cpl: int = 200
) -> Dict[str, ResilienceMetrics]:
    """
    Analyze resilience across multiple games.

    Args:
        game_evals: List of game evaluations
        pressure_threshold: Centipawns to be "under pressure"
        collapse_cpl: CPL threshold for a "collapse"

    Returns:
        Dict mapping player name to ResilienceMetrics
    """
    stats: Dict[str, ResilienceMetrics] = {}

    for game_eval in game_evals:
        game_res = calculate_game_resilience(game_eval, pressure_threshold, collapse_cpl)

        # Initialize players
        for player in [game_eval.white_player, game_eval.black_player]:
            if player not in stats:
                stats[player] = ResilienceMetrics(player_name=player)

        # White's stats
        white_stats = stats[game_eval.white_player]
        white_stats.games_analyzed += 1
        white_stats.total_resilience_score += game_res.white_resilience
        white_stats.total_positions_defended += game_res.white_positions_defended
        white_stats.total_collapses += game_res.white_collapses
        white_stats.total_difficult_positions += (game_res.white_positions_defended + game_res.white_collapses)

        # Black's stats
        black_stats = stats[game_eval.black_player]
        black_stats.games_analyzed += 1
        black_stats.total_resilience_score += game_res.black_resilience
        black_stats.total_positions_defended += game_res.black_positions_defended
        black_stats.total_collapses += game_res.black_collapses
        black_stats.total_difficult_positions += (game_res.black_positions_defended + game_res.black_collapses)

    return stats


def print_dominance_report(stats: Dict[str, DominanceMetrics]) -> None:
    """Print formatted dominance report."""
    print("\n" + "=" * 100)
    print("DOMINANCE METRICS")
    print("=" * 100)

    # Sort by average dominance score
    sorted_stats = sorted(stats.values(), key=lambda x: x.avg_dominance_score, reverse=True)

    print(f"\n{'Player':<25} {'Avg Score':<12} {'Dominated':<12} {'Moves Ahead':<12} {'Max Streak':<12}")
    print("-" * 80)

    for s in sorted_stats:
        dom_rate = f"{s.games_dominated}/{s.games_analyzed}"
        print(f"{s.player_name:<25} "
              f"{s.avg_dominance_score:>8.1f}    "
              f"{dom_rate:<12} "
              f"{s.total_moves_with_advantage:<12} "
              f"{s.longest_advantage_streak:<12}")


def print_resilience_report(stats: Dict[str, ResilienceMetrics]) -> None:
    """Print formatted resilience report."""
    print("\n" + "=" * 100)
    print("RESILIENCE METRICS")
    print("=" * 100)

    # Sort by average resilience score
    sorted_stats = sorted(stats.values(), key=lambda x: x.avg_resilience_score, reverse=True)

    print(f"\n{'Player':<25} {'Avg Score':<12} {'Defense %':<12} {'Collapse %':<12} {'Positions':<12}")
    print("-" * 80)

    for s in sorted_stats:
        print(f"{s.player_name:<25} "
              f"{s.avg_resilience_score:>8.1f}    "
              f"{s.defense_rate:>8.1f}%   "
              f"{s.collapse_rate:>8.1f}%   "
              f"{s.total_difficult_positions:<12}")
