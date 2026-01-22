"""
Clock and time control parsing utilities for chess games.
Handles different time control formats (Fischer, delay/bonus, etc.)
"""

from typing import Optional, Tuple


def parse_clock_time(clk_str: str) -> int:
    """
    Convert clock string like '1:59:58' or '59:58' to seconds.

    Args:
        clk_str: Clock time string in format HH:MM:SS or MM:SS

    Returns:
        Time in seconds
    """
    parts = clk_str.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        return hours * 3600 + minutes * 60 + seconds
    elif len(parts) == 2:
        minutes, seconds = map(int, parts)
        return minutes * 60 + seconds
    return 0


def format_time(seconds: int, format_type: str = "HH:MM:SS") -> str:
    """
    Convert seconds to human-readable time format.

    Args:
        seconds: Time in seconds
        format_type: Output format - "HH:MM:SS", "MM:SS", or "hours" (decimal)

    Returns:
        Formatted time string
    """
    if format_type == "HH:MM:SS":
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    elif format_type == "MM:SS":
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"
    elif format_type == "hours":
        return f"{seconds / 3600:.2f}h"
    else:
        raise ValueError(f"Unknown format_type: {format_type}")


def calculate_time_spent(
    previous_clock: int,
    current_clock: int,
    move_number: int,
    time_control_config: dict
) -> int:
    """
    Calculate time spent on a move, accounting for increments and bonuses.

    Args:
        previous_clock: Time remaining before the move (seconds)
        current_clock: Time remaining after the move (seconds)
        move_number: The move number for this player (1-indexed)
        time_control_config: Dict with time control settings

    Returns:
        Time spent on this move in seconds
    """
    increment_type = time_control_config.get("increment_type", "none")
    increment_start = time_control_config.get("increment_start_move", 1)
    increment_seconds = time_control_config.get("increment_seconds", 0)

    # Basic calculation
    time_spent = previous_clock - current_clock

    # Handle increments
    if increment_type == "fischer" and move_number >= increment_start:
        # Fischer increment: added to clock after move is made
        # So current_clock already includes the increment
        time_spent -= increment_seconds

    elif increment_type == "delay_bonus" and move_number > increment_start - 1:
        # Delay/bonus: increment added after a specific move
        # The increment is added AFTER move 40, so it appears in the clock for move 41
        # We need to subtract it when calculating time spent on move 41+
        if move_number > increment_start:
            time_spent -= increment_seconds

    # Ensure we don't return negative time spent (can happen with rounding/increments)
    return max(0, time_spent)


def get_initial_time(time_control_config: dict) -> int:
    """
    Get the initial time for a game based on time control.

    Args:
        time_control_config: Dict with time control settings

    Returns:
        Initial time in seconds
    """
    return time_control_config.get("base_time", 7200)


def extract_clock_from_comment(comment: str) -> Optional[int]:
    """
    Extract clock time from a PGN comment containing [%clk H:MM:SS].

    Args:
        comment: PGN comment string

    Returns:
        Clock time in seconds, or None if no clock found
    """
    if not comment or '%clk' not in comment:
        return None

    clk_start = comment.find('[%clk ') + 6
    clk_end = comment.find(']', clk_start)

    if clk_start > 5 and clk_end > clk_start:
        clock_str = comment[clk_start:clk_end]
        return parse_clock_time(clock_str)

    return None


class TimeTracker:
    """
    Tracks time usage throughout a game, handling different time controls.
    """

    def __init__(self, time_control_config: dict):
        """
        Initialize time tracker with specific time control.

        Args:
            time_control_config: Dict with time control settings
        """
        self.config = time_control_config
        self.initial_time = get_initial_time(time_control_config)
        self.white_clock = self.initial_time
        self.black_clock = self.initial_time
        self.white_move_num = 0
        self.black_move_num = 0

        # Track time spent per move
        self.white_times = []
        self.black_times = []

    def update(self, is_white_move: bool, current_clock: int) -> Tuple[int, int]:
        """
        Update the tracker with a new move's clock time.

        Args:
            is_white_move: True if white just moved
            current_clock: Clock time after the move

        Returns:
            Tuple of (time_spent, move_number) for this move
        """
        if is_white_move:
            self.white_move_num += 1
            time_spent = calculate_time_spent(
                self.white_clock,
                current_clock,
                self.white_move_num,
                self.config
            )
            self.white_times.append(time_spent)
            self.white_clock = current_clock
            return time_spent, self.white_move_num
        else:
            self.black_move_num += 1
            time_spent = calculate_time_spent(
                self.black_clock,
                current_clock,
                self.black_move_num,
                self.config
            )
            self.black_times.append(time_spent)
            self.black_clock = current_clock
            return time_spent, self.black_move_num

    def get_total_time_spent(self, is_white: bool) -> int:
        """Get total time spent by a player."""
        return sum(self.white_times if is_white else self.black_times)

    def get_time_for_moves(self, is_white: bool, start_move: int, end_move: int) -> int:
        """
        Get total time spent for a range of moves.

        Args:
            is_white: True for white, False for black
            start_move: Starting move number (1-indexed, inclusive)
            end_move: Ending move number (1-indexed, inclusive)

        Returns:
            Total time spent in that range
        """
        times = self.white_times if is_white else self.black_times
        # Convert to 0-indexed for list slicing
        return sum(times[start_move-1:end_move])
