"""
Configuration management for chess analysis project.
Loads settings from config.yaml and provides easy access.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """
    Manages project configuration loaded from YAML file.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml. If None, looks in project root.
        """
        if config_path is None:
            # Assume config.yaml is in project root (2 levels up from this file)
            config_path = Path(__file__).parent.parent.parent / "config.yaml"

        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)

    def get(self, *keys: str, default=None) -> Any:
        """
        Get a config value using dot notation.

        Args:
            *keys: Keys to traverse (e.g., "analysis", "time_thresholds", "opening_moves")
            default: Default value if key not found

        Returns:
            Config value or default

        Example:
            config.get("analysis", "time_thresholds", "opening_moves")
        """
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    @property
    def active_time_control(self) -> Dict[str, Any]:
        """Get the active tournament's time control configuration."""
        tc_name = self.get("active_tournament", "time_control")
        return self.get("time_controls", tc_name, default={})

    @property
    def active_pgn_file(self) -> str:
        """Get the active tournament's PGN filename."""
        return self.get("active_tournament", "pgn_file", default="")

    @property
    def data_raw_path(self) -> Path:
        """Get path to raw data directory."""
        return Path(self.get("paths", "data_raw", default="data/raw"))

    @property
    def data_processed_path(self) -> Path:
        """Get path to processed data directory."""
        return Path(self.get("paths", "data_processed", default="data/processed"))

    @property
    def cache_path(self) -> Path:
        """Get path to cache directory."""
        return Path(self.get("paths", "cache", default="data/cache"))

    @property
    def outputs_path(self) -> Path:
        """Get path to outputs directory."""
        return Path(self.get("paths", "outputs", default="outputs/graphs"))

    @property
    def reports_path(self) -> Path:
        """Get path to reports directory."""
        return Path(self.get("paths", "reports", default="outputs/reports"))

    # Analysis settings shortcuts
    @property
    def opening_moves(self) -> int:
        """Number of opening moves to analyze."""
        return self.get("analysis", "time_thresholds", "opening_moves", default=10)

    @property
    def long_think_seconds(self) -> int:
        """Threshold for long think in seconds."""
        minutes = self.get("analysis", "time_thresholds", "long_think_minutes", default=20)
        return minutes * 60

    @property
    def prep_exit_threshold_pct(self) -> float:
        """Percentage threshold for prep exit detection."""
        return self.get("analysis", "prep_detection", "percentage_threshold", default=0.05)

    @property
    def prep_exit_threshold_minutes(self) -> int:
        """Absolute time threshold for prep exit (in minutes)."""
        return self.get("analysis", "prep_detection", "absolute_threshold_minutes", default=10)

    # Engine analysis settings
    @property
    def engine_path(self) -> str:
        """Path to Stockfish binary."""
        return self.get("analysis", "engine", "path", default="stockfish")

    @property
    def engine_depth(self) -> int:
        """Search depth for engine analysis."""
        return self.get("analysis", "engine", "depth", default=20)

    @property
    def engine_threads(self) -> int:
        """Number of CPU threads for engine."""
        return self.get("analysis", "engine", "threads", default=4)

    @property
    def engine_hash_mb(self) -> int:
        """Hash table size in MB."""
        return self.get("analysis", "engine", "hash_mb", default=1024)

    @property
    def skip_opening_moves(self) -> int:
        """Number of opening moves to skip in engine analysis."""
        return self.get("analysis", "engine", "skip_opening_moves", default=8)

    @property
    def comeback_threshold(self) -> int:
        """Centipawn threshold for comeback detection."""
        return self.get("analysis", "performance", "comeback_threshold", default=200)

    @property
    def blown_lead_threshold(self) -> int:
        """Centipawn threshold for blown lead detection."""
        return self.get("analysis", "performance", "blown_lead_threshold", default=200)

    # Visualization settings
    @property
    def viz_colors(self) -> Dict[str, str]:
        """Get visualization color scheme."""
        return self.get("visualization", "colors", default={})

    @property
    def viz_format_portrait(self) -> Dict[str, int]:
        """Get portrait format settings."""
        return self.get("visualization", "output_formats", "portrait", default={})

    @property
    def viz_format_square(self) -> Dict[str, int]:
        """Get square format settings."""
        return self.get("visualization", "output_formats", "square", default={})

    def __repr__(self) -> str:
        active_tc = self.get("active_tournament", "time_control")
        active_pgn = self.active_pgn_file
        return f"Config(active_tc='{active_tc}', pgn='{active_pgn}')"


# Global config instance (lazy loaded)
_global_config: Optional[Config] = None


def get_config(config_path: Optional[Path] = None) -> Config:
    """
    Get the global config instance.

    Args:
        config_path: Optional path to config file (only used on first call)

    Returns:
        Config instance
    """
    global _global_config
    if _global_config is None:
        _global_config = Config(config_path)
    return _global_config
