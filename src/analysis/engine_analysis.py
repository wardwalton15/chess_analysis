"""
Stockfish engine integration for chess position analysis.
Calculates centipawn loss for each move in a game.
"""

import chess
import chess.engine
from pathlib import Path
from typing import List, Optional, Dict, Any, Iterator
from dataclasses import dataclass, field
from contextlib import contextmanager

from ..parsers.pgn_parser import ParsedGame, MoveData
from .evaluation_cache import EvaluationCache, CachedEvaluation


# Large value to represent mate scores in centipawns
MATE_SCORE = 10000


@dataclass
class MoveEvaluation:
    """Evaluation data for a single move."""
    move_number: int
    is_white: bool
    eval_before: int  # Centipawns from white's perspective
    eval_after: int  # Eval after move played
    best_move_eval: int  # Eval if best move was played
    move_played: str  # UCI format
    best_move: str  # Stockfish's recommended move
    centipawn_loss: int  # Always positive
    is_blunder: bool  # CPL > 200
    is_mistake: bool  # CPL 50-200
    is_inaccuracy: bool  # CPL 20-50
    time_spent: Optional[int] = None


@dataclass
class GameEvaluation:
    """Complete evaluation for a game."""
    game_id: str  # "White vs Black Round X"
    white_player: str
    black_player: str
    move_evaluations: List[MoveEvaluation]
    white_avg_cpl: float
    black_avg_cpl: float
    white_accuracy: float  # Percentage
    black_accuracy: float
    largest_eval_swing: int  # For comeback/blown lead detection
    min_white_eval: int  # Worst position for white
    max_white_eval: int  # Best position for white
    result: str

    @property
    def white_blunders(self) -> int:
        return sum(1 for m in self.move_evaluations if m.is_white and m.is_blunder)

    @property
    def black_blunders(self) -> int:
        return sum(1 for m in self.move_evaluations if not m.is_white and m.is_blunder)

    @property
    def white_mistakes(self) -> int:
        return sum(1 for m in self.move_evaluations if m.is_white and m.is_mistake)

    @property
    def black_mistakes(self) -> int:
        return sum(1 for m in self.move_evaluations if not m.is_white and m.is_mistake)


def score_to_cp(score: chess.engine.PovScore, perspective_white: bool = True) -> int:
    """
    Convert engine score to centipawns from white's perspective.

    Args:
        score: PovScore from python-chess engine
        perspective_white: If True, return from white's perspective

    Returns:
        Centipawns (positive = good for white)
    """
    # Get score from white's perspective
    white_score = score.white()

    if white_score.is_mate():
        mate_in = white_score.mate()
        # Positive mate_in means white mates, negative means black mates
        if mate_in > 0:
            return MATE_SCORE - mate_in  # Closer mate = higher score
        else:
            return -MATE_SCORE - mate_in  # Closer mate against = lower score
    else:
        return white_score.score()


def calculate_accuracy(avg_cpl: float) -> float:
    """
    Calculate Lichess-style accuracy percentage from average centipawn loss.

    Formula: 103.1668 * exp(-0.04354 * (avg_cpl - 1)) - 3.1669
    Capped between 0 and 100.

    Args:
        avg_cpl: Average centipawn loss

    Returns:
        Accuracy percentage (0-100)
    """
    import math

    if avg_cpl < 0:
        return 100.0

    accuracy = 103.1668 * math.exp(-0.04354 * (avg_cpl - 1)) - 3.1669
    return max(0.0, min(100.0, accuracy))


@contextmanager
def create_engine(
    engine_path: str = "stockfish",
    threads: int = 4,
    hash_mb: int = 1024
):
    """
    Create and configure a Stockfish engine instance.

    Args:
        engine_path: Path to Stockfish binary
        threads: Number of CPU threads
        hash_mb: Hash table size in MB

    Yields:
        Configured chess.engine.SimpleEngine instance
    """
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    try:
        engine.configure({
            "Threads": threads,
            "Hash": hash_mb
        })
        yield engine
    finally:
        engine.quit()


def evaluate_position(
    engine: chess.engine.SimpleEngine,
    fen: str,
    depth: int = 20,
    cache: Optional[EvaluationCache] = None
) -> CachedEvaluation:
    """
    Evaluate a position using Stockfish.

    Args:
        engine: Stockfish engine instance
        fen: Position in FEN format
        depth: Search depth
        cache: Optional evaluation cache

    Returns:
        CachedEvaluation with score and best move
    """
    # Check cache first
    if cache is not None:
        cached = cache.get(fen, depth)
        if cached is not None:
            return cached

    # Evaluate position
    board = chess.Board(fen)
    info = engine.analyse(board, chess.engine.Limit(depth=depth))

    score = info["score"]
    best_move = info.get("pv", [None])[0]

    # Convert to centipawns from white's perspective
    cp_score = score_to_cp(score, perspective_white=True)

    # Check for mate
    white_score = score.white()
    is_mate = white_score.is_mate()
    mate_in = white_score.mate() if is_mate else None

    evaluation = CachedEvaluation(
        score_cp=cp_score,
        best_move=best_move.uci() if best_move else "",
        depth=depth,
        is_mate=is_mate,
        mate_in=mate_in
    )

    # Store in cache
    if cache is not None:
        cache.put(fen, evaluation)

    return evaluation


def evaluate_move(
    engine: chess.engine.SimpleEngine,
    fen_before: str,
    move_uci: str,
    depth: int = 20,
    cache: Optional[EvaluationCache] = None
) -> tuple[CachedEvaluation, CachedEvaluation, int]:
    """
    Evaluate a move by comparing position before and after.

    Args:
        engine: Stockfish engine instance
        fen_before: Position before the move
        move_uci: Move played in UCI format
        depth: Search depth
        cache: Optional evaluation cache

    Returns:
        Tuple of (eval_before, eval_after, centipawn_loss)
    """
    # Get evaluation before move (includes best move)
    eval_before = evaluate_position(engine, fen_before, depth, cache)

    # Apply move to get position after
    board = chess.Board(fen_before)
    move = chess.Move.from_uci(move_uci)
    board.push(move)
    fen_after = board.fen()

    # Get evaluation after move
    eval_after = evaluate_position(engine, fen_after, depth, cache)

    # Calculate centipawn loss
    # For white: loss = eval_before - eval_after (if positive, white lost advantage)
    # For black: loss = eval_after - eval_before (if positive, black lost advantage)
    is_white_move = " w " in fen_before
    if is_white_move:
        # White moved: compare best possible eval vs actual result
        # Best: eval if best move played = eval_before (roughly, since we evaluated after best move would be played)
        # Actual: -eval_after (from white's perspective after move)
        cpl = max(0, eval_before.score_cp - (-eval_after.score_cp))
    else:
        # Black moved: eval_after should be more negative (better for black) than eval_before
        cpl = max(0, (-eval_before.score_cp) - eval_after.score_cp)

    return eval_before, eval_after, cpl


def analyze_game(
    engine: chess.engine.SimpleEngine,
    game: ParsedGame,
    depth: int = 20,
    skip_opening_moves: int = 8,
    cache: Optional[EvaluationCache] = None,
    progress_callback: Optional[callable] = None
) -> GameEvaluation:
    """
    Analyze a complete game with Stockfish.

    Args:
        engine: Stockfish engine instance
        game: Parsed game data
        depth: Search depth
        skip_opening_moves: Skip first N moves of the game
        cache: Optional evaluation cache
        progress_callback: Optional callback(current_move, total_moves)

    Returns:
        GameEvaluation with all move evaluations
    """
    move_evals = []
    white_cpl_total = 0
    white_move_count = 0
    black_cpl_total = 0
    black_move_count = 0

    # Track evaluation extremes for comeback/blown lead detection
    evals_over_time = []
    min_eval = 0
    max_eval = 0

    total_moves = len(game.moves)

    for i, move in enumerate(game.moves):
        # Progress callback
        if progress_callback:
            progress_callback(i + 1, total_moves)

        # Skip opening moves
        if move.player_move_num <= skip_opening_moves:
            continue

        # Evaluate the move
        eval_before = evaluate_position(engine, move.fen_before, depth, cache)
        eval_after = evaluate_position(engine, move.fen_after, depth, cache)

        # Calculate centipawn loss
        # The key insight: we compare what the eval was before the move
        # to what it is after (from the same player's perspective)
        if move.is_white:
            # White wants higher eval (positive)
            # After white moves, it's black's turn, so eval_after is from black's view
            # We negate it to get white's perspective
            cpl = max(0, eval_before.score_cp - (-eval_after.score_cp))
            white_cpl_total += cpl
            white_move_count += 1
        else:
            # Black wants lower eval (negative from white's perspective)
            # After black moves, it's white's turn, eval_after is white's perspective
            cpl = max(0, (-eval_before.score_cp) - eval_after.score_cp)
            black_cpl_total += cpl
            black_move_count += 1

        # Track eval over time (from white's perspective, after move)
        current_eval = -eval_after.score_cp if move.is_white else eval_after.score_cp
        evals_over_time.append(current_eval)
        min_eval = min(min_eval, current_eval)
        max_eval = max(max_eval, current_eval)

        # Classify move quality
        is_blunder = cpl > 200
        is_mistake = 50 < cpl <= 200
        is_inaccuracy = 20 < cpl <= 50

        move_evals.append(MoveEvaluation(
            move_number=move.move_number,
            is_white=move.is_white,
            eval_before=eval_before.score_cp,
            eval_after=eval_after.score_cp,
            best_move_eval=eval_before.score_cp,  # Eval if best move played
            move_played=move.uci,
            best_move=eval_before.best_move,
            centipawn_loss=cpl,
            is_blunder=is_blunder,
            is_mistake=is_mistake,
            is_inaccuracy=is_inaccuracy,
            time_spent=move.time_spent
        ))

    # Calculate averages
    white_avg_cpl = white_cpl_total / white_move_count if white_move_count > 0 else 0
    black_avg_cpl = black_cpl_total / black_move_count if black_move_count > 0 else 0

    # Calculate accuracy
    white_accuracy = calculate_accuracy(white_avg_cpl)
    black_accuracy = calculate_accuracy(black_avg_cpl)

    # Largest swing
    largest_swing = max_eval - min_eval if evals_over_time else 0

    game_id = f"{game.metadata.white} vs {game.metadata.black} R{game.metadata.round}"

    return GameEvaluation(
        game_id=game_id,
        white_player=game.metadata.white,
        black_player=game.metadata.black,
        move_evaluations=move_evals,
        white_avg_cpl=white_avg_cpl,
        black_avg_cpl=black_avg_cpl,
        white_accuracy=white_accuracy,
        black_accuracy=black_accuracy,
        largest_eval_swing=largest_swing,
        min_white_eval=min_eval,
        max_white_eval=max_eval,
        result=game.metadata.result
    )


def analyze_games(
    games: List[ParsedGame],
    engine_path: str = "stockfish",
    depth: int = 20,
    skip_opening_moves: int = 8,
    threads: int = 4,
    hash_mb: int = 1024,
    cache_path: Optional[Path] = None,
    verbose: bool = True
) -> List[GameEvaluation]:
    """
    Analyze multiple games with Stockfish.

    Args:
        games: List of parsed games
        engine_path: Path to Stockfish binary
        depth: Search depth
        skip_opening_moves: Skip first N moves
        threads: CPU threads for Stockfish
        hash_mb: Hash table size
        cache_path: Path to cache directory
        verbose: Print progress

    Returns:
        List of GameEvaluation objects
    """
    results = []

    # Setup cache
    cache = None
    if cache_path:
        cache = EvaluationCache(cache_path)

    try:
        with create_engine(engine_path, threads, hash_mb) as engine:
            for i, game in enumerate(games):
                if verbose:
                    print(f"Analyzing game {i + 1}/{len(games)}: "
                          f"{game.metadata.white} vs {game.metadata.black}")

                game_eval = analyze_game(
                    engine=engine,
                    game=game,
                    depth=depth,
                    skip_opening_moves=skip_opening_moves,
                    cache=cache
                )
                results.append(game_eval)

                if verbose:
                    print(f"  White accuracy: {game_eval.white_accuracy:.1f}% "
                          f"(avg CPL: {game_eval.white_avg_cpl:.1f})")
                    print(f"  Black accuracy: {game_eval.black_accuracy:.1f}% "
                          f"(avg CPL: {game_eval.black_avg_cpl:.1f})")

    finally:
        # Save cache
        if cache:
            cache.save()
            if verbose:
                print(f"Cache saved with {cache.size} positions")

    return results
