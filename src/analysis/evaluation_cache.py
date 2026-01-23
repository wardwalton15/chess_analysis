"""
Evaluation caching system for Stockfish analysis.
Caches position evaluations to avoid recomputing expensive engine analysis.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class CachedEvaluation:
    """Cached evaluation for a single position."""
    score_cp: int  # Centipawns from white's perspective
    best_move: str  # UCI format
    depth: int
    is_mate: bool
    mate_in: Optional[int] = None  # Moves to mate (positive = white wins)


class EvaluationCache:
    """
    Manages caching of position evaluations.

    Cache key format: FEN (without move counters) + depth
    This allows positions to be reused across different games.
    """

    def __init__(self, cache_path: Path):
        """
        Initialize cache.

        Args:
            cache_path: Path to cache directory
        """
        self.cache_path = cache_path
        self.cache_file = cache_path / "evaluations.json"
        self._cache: Dict[str, Dict] = {}
        self._dirty = False

        # Ensure cache directory exists
        cache_path.mkdir(parents=True, exist_ok=True)

        # Load existing cache
        self._load()

    def _normalize_fen(self, fen: str) -> str:
        """
        Normalize FEN for caching by removing halfmove and fullmove counters.
        This allows the same position to be cached regardless of when it occurred.

        Args:
            fen: Full FEN string

        Returns:
            Normalized FEN (first 4 parts only)
        """
        parts = fen.split()
        # Keep: piece placement, active color, castling, en passant
        # Remove: halfmove clock, fullmove number
        return " ".join(parts[:4])

    def _make_key(self, fen: str, depth: int) -> str:
        """Create cache key from FEN and depth."""
        normalized = self._normalize_fen(fen)
        return f"{normalized}|d{depth}"

    def _load(self) -> None:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                # Start fresh if cache is corrupted
                self._cache = {}

    def save(self) -> None:
        """Save cache to disk if modified."""
        if self._dirty:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2)
            self._dirty = False

    def get(self, fen: str, depth: int) -> Optional[CachedEvaluation]:
        """
        Get cached evaluation for a position.

        Args:
            fen: Position FEN
            depth: Search depth

        Returns:
            CachedEvaluation if found, None otherwise
        """
        key = self._make_key(fen, depth)
        if key in self._cache:
            data = self._cache[key]
            return CachedEvaluation(
                score_cp=data['score_cp'],
                best_move=data['best_move'],
                depth=data['depth'],
                is_mate=data['is_mate'],
                mate_in=data.get('mate_in')
            )
        return None

    def put(self, fen: str, evaluation: CachedEvaluation) -> None:
        """
        Store evaluation in cache.

        Args:
            fen: Position FEN
            evaluation: Evaluation to cache
        """
        key = self._make_key(fen, evaluation.depth)
        self._cache[key] = asdict(evaluation)
        self._dirty = True

    def has(self, fen: str, depth: int) -> bool:
        """Check if position is cached at given depth."""
        key = self._make_key(fen, depth)
        return key in self._cache

    @property
    def size(self) -> int:
        """Number of cached positions."""
        return len(self._cache)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache = {}
        self._dirty = True

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - auto-save."""
        self.save()
        return False
