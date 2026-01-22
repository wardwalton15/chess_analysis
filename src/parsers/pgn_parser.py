"""
PGN file parsing utilities.
Handles reading chess games and extracting metadata, moves, and clock times.
"""

import chess.pgn
from pathlib import Path
from typing import Iterator, Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from .clock_parser import extract_clock_from_comment, TimeTracker


@dataclass
class GameMetadata:
    """Metadata for a chess game."""
    event: str
    site: str
    date: str
    round: str
    white: str
    black: str
    result: str
    white_elo: Optional[int] = None
    black_elo: Optional[int] = None
    eco: Optional[str] = None  # Opening code


@dataclass
class MoveData:
    """Data for a single move in a game."""
    move_number: int  # Full move number (1, 2, 3...)
    is_white: bool
    player_move_num: int  # Move number for this specific player (1, 2, 3...)
    san: str  # Move in Standard Algebraic Notation
    uci: str  # Move in UCI format
    clock_remaining: Optional[int]  # Seconds remaining after move
    time_spent: Optional[int]  # Seconds spent on this move
    fen_before: str  # Position before move
    fen_after: str  # Position after move


@dataclass
class ParsedGame:
    """Complete parsed game data."""
    metadata: GameMetadata
    moves: List[MoveData]


def parse_game_metadata(game: chess.pgn.Game) -> GameMetadata:
    """
    Extract metadata from a chess.pgn.Game object.

    Args:
        game: chess.pgn.Game object

    Returns:
        GameMetadata object
    """
    headers = game.headers

    # Try to parse ELO ratings
    white_elo = None
    black_elo = None
    if "WhiteElo" in headers:
        try:
            white_elo = int(headers["WhiteElo"])
        except (ValueError, TypeError):
            pass
    if "BlackElo" in headers:
        try:
            black_elo = int(headers["BlackElo"])
        except (ValueError, TypeError):
            pass

    return GameMetadata(
        event=headers.get("Event", "Unknown"),
        site=headers.get("Site", "Unknown"),
        date=headers.get("Date", "Unknown"),
        round=headers.get("Round", "Unknown"),
        white=headers.get("White", "Unknown"),
        black=headers.get("Black", "Unknown"),
        result=headers.get("Result", "*"),
        white_elo=white_elo,
        black_elo=black_elo,
        eco=headers.get("ECO"),
    )


def parse_game_moves(
    game: chess.pgn.Game,
    time_control_config: Optional[Dict[str, Any]] = None,
    include_clock_data: bool = True
) -> List[MoveData]:
    """
    Extract all moves and clock data from a game.

    Args:
        game: chess.pgn.Game object
        time_control_config: Time control settings (for calculating time spent)
        include_clock_data: Whether to extract clock times (faster if False)

    Returns:
        List of MoveData objects
    """
    moves = []
    board = game.board()

    # Initialize time tracker if we have time control config
    time_tracker = None
    if time_control_config and include_clock_data:
        time_tracker = TimeTracker(time_control_config)

    full_move_count = 0
    white_move_num = 0
    black_move_num = 0

    for node in game.mainline():
        full_move_count += 1
        is_white_move = (full_move_count % 2 == 1)

        if is_white_move:
            white_move_num += 1
            player_move_num = white_move_num
        else:
            black_move_num += 1
            player_move_num = black_move_num

        # Store position before move
        fen_before = board.fen()

        # Get move details
        move = node.move
        san = board.san(move)
        uci = move.uci()

        # Apply move
        board.push(move)
        fen_after = board.fen()

        # Extract clock data if available
        clock_remaining = None
        time_spent = None

        if include_clock_data:
            clock_remaining = extract_clock_from_comment(node.comment)

            if clock_remaining is not None and time_tracker:
                time_spent, _ = time_tracker.update(is_white_move, clock_remaining)

        moves.append(MoveData(
            move_number=full_move_count,
            is_white=is_white_move,
            player_move_num=player_move_num,
            san=san,
            uci=uci,
            clock_remaining=clock_remaining,
            time_spent=time_spent,
            fen_before=fen_before,
            fen_after=fen_after
        ))

    return moves


def parse_game(
    game: chess.pgn.Game,
    time_control_config: Optional[Dict[str, Any]] = None,
    include_clock_data: bool = True
) -> ParsedGame:
    """
    Parse a complete game into structured data.

    Args:
        game: chess.pgn.Game object
        time_control_config: Time control settings
        include_clock_data: Whether to extract clock times

    Returns:
        ParsedGame object with all game data
    """
    metadata = parse_game_metadata(game)
    moves = parse_game_moves(game, time_control_config, include_clock_data)

    return ParsedGame(metadata=metadata, moves=moves)


def read_pgn_file(
    pgn_path: Path,
    time_control_config: Optional[Dict[str, Any]] = None,
    include_clock_data: bool = True,
    max_games: Optional[int] = None
) -> Iterator[ParsedGame]:
    """
    Read and parse all games from a PGN file.

    Args:
        pgn_path: Path to PGN file
        time_control_config: Time control settings
        include_clock_data: Whether to extract clock times
        max_games: Maximum number of games to parse (None for all)

    Yields:
        ParsedGame objects
    """
    with open(pgn_path, encoding="utf-8") as f:
        game_count = 0

        while True:
            game = chess.pgn.read_game(f)
            if game is None:
                break

            yield parse_game(game, time_control_config, include_clock_data)

            game_count += 1
            if max_games and game_count >= max_games:
                break


def count_games(pgn_path: Path) -> int:
    """
    Quickly count the number of games in a PGN file.

    Args:
        pgn_path: Path to PGN file

    Returns:
        Number of games
    """
    count = 0
    with open(pgn_path, encoding="utf-8") as f:
        while chess.pgn.read_game(f) is not None:
            count += 1
    return count
