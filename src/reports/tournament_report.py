"""
Tournament report generator for comprehensive tournament analysis.
Combines standings, results, and time analysis into a unified report.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

from ..parsers.pgn_parser import read_pgn_file, ParsedGame
from ..parsers.clock_parser import format_time, get_initial_time
from ..analysis.time_analysis import (
    find_long_thinks_pct, analyze_time_pressure_pct,
    LongThinkPct, TimePressureStats
)
from ..analysis.prep_analysis import (
    analyze_prep_exits, get_first_to_think_summary,
    PrepStats
)
from ..utils.config import get_config


@dataclass
class PlayerStanding:
    """Standing record for a single player."""
    name: str
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    points: float = 0.0
    # Color-specific
    white_games: int = 0
    white_wins: int = 0
    white_draws: int = 0
    white_losses: int = 0
    black_games: int = 0
    black_wins: int = 0
    black_draws: int = 0
    black_losses: int = 0


@dataclass
class GameResult:
    """Record of a single game result."""
    round_num: str
    date: str
    white: str
    black: str
    result: str
    white_won: bool
    black_won: bool
    is_draw: bool
    move_count: int
    eco: Optional[str] = None


@dataclass
class TournamentReport:
    """Complete tournament analysis report."""
    # Metadata
    event: str
    site: str
    start_date: str
    end_date: str
    rounds_played: int
    total_rounds: int
    games_analyzed: int
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Standings
    standings: List[PlayerStanding] = field(default_factory=list)

    # Results
    results_by_round: Dict[str, List[GameResult]] = field(default_factory=dict)
    decisive_games: int = 0
    drawn_games: int = 0
    white_wins: int = 0
    black_wins: int = 0

    # Time metrics (from existing analysis)
    longest_thinks: List[LongThinkPct] = field(default_factory=list)
    time_pressure_stats: Dict[str, TimePressureStats] = field(default_factory=dict)
    prep_stats: Dict[str, PrepStats] = field(default_factory=dict)
    first_to_think: List[Tuple[str, str, str, int, str]] = field(default_factory=list)


def calculate_standings(games: List[ParsedGame]) -> Dict[str, PlayerStanding]:
    """
    Calculate tournament standings from game results.

    Args:
        games: List of parsed games (only completed games)

    Returns:
        Dictionary of player name -> PlayerStanding
    """
    standings: Dict[str, PlayerStanding] = {}

    for game in games:
        white = game.metadata.white
        black = game.metadata.black
        result = game.metadata.result

        # Skip incomplete games
        if result not in ("1-0", "0-1", "1/2-1/2"):
            continue

        # Initialize players if needed
        if white not in standings:
            standings[white] = PlayerStanding(name=white)
        if black not in standings:
            standings[black] = PlayerStanding(name=black)

        white_standing = standings[white]
        black_standing = standings[black]

        # Update game counts
        white_standing.games += 1
        white_standing.white_games += 1
        black_standing.games += 1
        black_standing.black_games += 1

        # Update results
        if result == "1-0":
            white_standing.wins += 1
            white_standing.white_wins += 1
            white_standing.points += 1.0
            black_standing.losses += 1
            black_standing.black_losses += 1
        elif result == "0-1":
            black_standing.wins += 1
            black_standing.black_wins += 1
            black_standing.points += 1.0
            white_standing.losses += 1
            white_standing.white_losses += 1
        else:  # Draw
            white_standing.draws += 1
            white_standing.white_draws += 1
            white_standing.points += 0.5
            black_standing.draws += 1
            black_standing.black_draws += 1
            black_standing.points += 0.5

    return standings


def extract_results(games: List[ParsedGame]) -> Tuple[Dict[str, List[GameResult]], int, int, int, int]:
    """
    Extract game results organized by round.

    Args:
        games: List of parsed games

    Returns:
        Tuple of (results_by_round, decisive_count, draw_count, white_wins, black_wins)
    """
    results_by_round: Dict[str, List[GameResult]] = defaultdict(list)
    decisive = 0
    draws = 0
    white_wins = 0
    black_wins = 0

    for game in games:
        result = game.metadata.result

        # Skip incomplete games
        if result not in ("1-0", "0-1", "1/2-1/2"):
            continue

        is_white_win = result == "1-0"
        is_black_win = result == "0-1"
        is_draw = result == "1/2-1/2"

        game_result = GameResult(
            round_num=game.metadata.round,
            date=game.metadata.date,
            white=game.metadata.white,
            black=game.metadata.black,
            result=result,
            white_won=is_white_win,
            black_won=is_black_win,
            is_draw=is_draw,
            move_count=len(game.moves),
            eco=game.metadata.eco
        )

        results_by_round[game.metadata.round].append(game_result)

        if is_white_win:
            decisive += 1
            white_wins += 1
        elif is_black_win:
            decisive += 1
            black_wins += 1
        else:
            draws += 1

    return dict(results_by_round), decisive, draws, white_wins, black_wins


def generate_tournament_report(
    pgn_path: Path,
    time_control_config: Optional[Dict] = None,
    completed_rounds: Optional[int] = None,
    total_rounds: Optional[int] = None,
    verbose: bool = True
) -> TournamentReport:
    """
    Generate a comprehensive tournament analysis report.

    Args:
        pgn_path: Path to PGN file
        time_control_config: Time control settings
        completed_rounds: Number of completed rounds (auto-detected if None)
        total_rounds: Total rounds in tournament (for display)
        verbose: Print progress

    Returns:
        TournamentReport with all analysis
    """
    config = get_config()

    if time_control_config is None:
        time_control_config = config.active_time_control

    base_time = get_initial_time(time_control_config)

    if verbose:
        print(f"Reading PGN file: {pgn_path}")

    all_games = list(read_pgn_file(pgn_path, time_control_config))

    # Filter to completed games only
    completed_games = [g for g in all_games if g.metadata.result in ("1-0", "0-1", "1/2-1/2")]

    if verbose:
        print(f"Loaded {len(all_games)} games, {len(completed_games)} completed")

    if not completed_games:
        raise ValueError("No completed games found in PGN")

    # Get tournament metadata
    first_game = completed_games[0]
    event = first_game.metadata.event
    site = first_game.metadata.site

    # Find date range
    dates = sorted(set(g.metadata.date for g in completed_games))
    start_date = dates[0] if dates else "Unknown"
    end_date = dates[-1] if dates else "Unknown"

    # Determine rounds
    completed_round_nums = sorted(set(
        int(g.metadata.round.split('.')[0])
        for g in completed_games
        if g.metadata.round.replace('.', '').isdigit()
    ))
    rounds_played = max(completed_round_nums) if completed_round_nums else 0

    if completed_rounds:
        rounds_played = completed_rounds
    if total_rounds is None:
        total_rounds = rounds_played

    if verbose:
        print(f"\n--- Calculating Standings ---")

    # Calculate standings
    standings_dict = calculate_standings(completed_games)
    standings_list = sorted(
        standings_dict.values(),
        key=lambda x: (-x.points, -x.wins, x.name)
    )

    if verbose:
        print(f"--- Extracting Results ---")

    # Extract results
    results_by_round, decisive, draws, white_wins, black_wins = extract_results(completed_games)

    if verbose:
        print(f"--- Running Time Analysis ---")

    # Thresholds
    long_think_pct = config.get("analysis", "time_thresholds", "long_think_pct") or 0.10
    time_pressure_pct = config.get("analysis", "time_thresholds", "time_pressure_pct") or 0.05
    prep_pct = config.get("analysis", "prep_detection", "percentage_threshold") or 0.05
    prep_abs = config.get("analysis", "prep_detection", "absolute_threshold_minutes") or 10

    # Time analysis (only on completed games with moves)
    games_with_moves = [g for g in completed_games if len(g.moves) > 0]

    _, longest_thinks = find_long_thinks_pct(games_with_moves, long_think_pct, time_control_config)
    time_pressure_stats = analyze_time_pressure_pct(games_with_moves, time_pressure_pct, time_control_config)

    if verbose:
        print(f"--- Running Prep Analysis ---")

    prep_stats = analyze_prep_exits(
        games_with_moves, time_control_config, method="hybrid",
        pct_threshold=prep_pct, absolute_threshold_minutes=prep_abs
    )
    first_to_think = get_first_to_think_summary(
        games_with_moves, time_control_config, method="hybrid",
        pct_threshold=prep_pct, absolute_threshold_minutes=prep_abs
    )

    return TournamentReport(
        event=event,
        site=site,
        start_date=start_date,
        end_date=end_date,
        rounds_played=rounds_played,
        total_rounds=total_rounds,
        games_analyzed=len(completed_games),
        standings=standings_list,
        results_by_round=results_by_round,
        decisive_games=decisive,
        drawn_games=draws,
        white_wins=white_wins,
        black_wins=black_wins,
        longest_thinks=longest_thinks,
        time_pressure_stats=time_pressure_stats,
        prep_stats=prep_stats,
        first_to_think=first_to_think
    )


def export_tournament_report(report: TournamentReport, output_path: Path) -> None:
    """
    Export tournament report to markdown file.

    Args:
        report: TournamentReport to export
        output_path: Path to output file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    # Header
    lines.extend([
        f"# {report.event} - Tournament Report",
        "",
        f"**Rounds {report.rounds_played} of {report.total_rounds}** | {report.site} | {report.start_date.replace('.', '/')} - {report.end_date.replace('.', '/')}",
        "",
        "---",
        "",
        "## Tournament Overview",
        "",
        f"**Games Played:** {report.games_analyzed}",
        f"**Decisive Games:** {report.decisive_games} ({report.decisive_games/report.games_analyzed*100:.1f}%)",
        f"**Draws:** {report.drawn_games} ({report.drawn_games/report.games_analyzed*100:.1f}%)",
        f"**White Wins:** {report.white_wins} ({report.white_wins/report.games_analyzed*100:.1f}%)",
        f"**Black Wins:** {report.black_wins} ({report.black_wins/report.games_analyzed*100:.1f}%)",
        "",
        "---",
        "",
    ])

    # Standings
    lines.extend([
        "## Standings",
        "",
        "| Rank | Player | Score | W | D | L | White | Black |",
        "|:----:|--------|:-----:|:-:|:-:|:-:|:-----:|:-----:|"
    ])

    for i, standing in enumerate(report.standings, 1):
        score = f"{standing.points:.1f}" if standing.points % 1 else f"{int(standing.points)}"
        white_record = f"+{standing.white_wins}={standing.white_draws}-{standing.white_losses}"
        black_record = f"+{standing.black_wins}={standing.black_draws}-{standing.black_losses}"
        lines.append(
            f"| {i} | {standing.name} | **{score}/{standing.games}** | "
            f"{standing.wins} | {standing.draws} | {standing.losses} | {white_record} | {black_record} |"
        )

    lines.extend(["", "---", ""])

    # Round-by-round results
    lines.extend(["## Round-by-Round Results", ""])

    for round_num in sorted(report.results_by_round.keys(), key=lambda x: (int(x.split('.')[0]), x)):
        results = report.results_by_round[round_num]
        if not results:
            continue

        date = results[0].date.replace('.', '/') if results else ""
        lines.extend([
            f"### Round {round_num} - {date}",
            "",
            "| White | Result | Black |",
            "|-------|:------:|-------|"
        ])

        for game in results:
            if game.white_won:
                white_fmt = f"**{game.white}**"
                black_fmt = game.black
                result_fmt = "**1-0**"
            elif game.black_won:
                white_fmt = game.white
                black_fmt = f"**{game.black}**"
                result_fmt = "**0-1**"
            else:
                white_fmt = game.white
                black_fmt = game.black
                result_fmt = "½-½"

            lines.append(f"| {white_fmt} | {result_fmt} | {black_fmt} |")

        lines.extend([""])

    lines.extend(["---", ""])

    # Time Analysis Section
    lines.extend([
        "## Time Management Analysis",
        "",
        "### Long Thinks (>10% of total time on a single move)",
        "",
    ])

    if report.longest_thinks:
        # Player counts
        player_counts = {}
        for think in report.longest_thinks:
            player_counts[think.player] = player_counts.get(think.player, 0) + 1

        lines.extend([
            "| Player | Long Think Count |",
            "|--------|:----------------:|"
        ])
        for player, count in sorted(player_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {player} | {count} |")

        lines.extend([
            "",
            "**Top 10 Longest Thinks:**",
            "",
            "| Player | Time | % Total | Move | Color | vs Opponent | Round |",
            "|--------|:----:|:-------:|:----:|:-----:|-------------|:-----:|"
        ])

        for think in report.longest_thinks[:10]:
            time_str = format_time(think.time_spent, 'MM:SS')
            pct_str = f"{think.pct_of_total*100:.1f}%"
            lines.append(
                f"| {think.player} | {time_str} | {pct_str} | {think.move_number} | "
                f"{think.color} | {think.opponent} | {think.round_num} |"
            )

        lines.append("")
    else:
        lines.extend(["*No long thinks detected*", ""])

    # Time Pressure
    lines.extend([
        "### Time Pressure (<5% time remaining)",
        "",
    ])

    if report.time_pressure_stats:
        lines.extend([
            "| Player | Pressure Moves | Games | Pressure % |",
            "|--------|:--------------:|:-----:|:----------:|"
        ])

        sorted_pressure = sorted(
            report.time_pressure_stats.values(),
            key=lambda x: -x.moves_under_threshold
        )

        for stats in sorted_pressure:
            pct = f"{stats.games_in_pressure/stats.total_games*100:.1f}%" if stats.total_games > 0 else "0%"
            lines.append(
                f"| {stats.player_name} | {stats.moves_under_threshold} | "
                f"{stats.games_in_pressure}/{stats.total_games} | {pct} |"
            )

        lines.append("")
    else:
        lines.extend(["*No time pressure data*", ""])

    # Prep Analysis
    lines.extend([
        "### Opening Preparation",
        "",
    ])

    if report.prep_stats:
        lines.extend([
            "| Player | Avg Prep Exit | Earliest | Latest | First to Think |",
            "|--------|:-------------:|:--------:|:------:|:--------------:|"
        ])

        sorted_prep = sorted(
            report.prep_stats.values(),
            key=lambda x: x.avg_prep_exit_move
        )

        for stats in sorted_prep:
            lines.append(
                f"| {stats.player_name} | Move {stats.avg_prep_exit_move:.1f} | "
                f"Move {stats.earliest_exit} | Move {stats.latest_exit} | {stats.times_first_to_think} |"
            )

        lines.append("")
    else:
        lines.extend(["*No prep data*", ""])

    # Footer
    lines.extend([
        "---",
        "",
        f"*Report generated: {report.generated_at[:10]}*",
        ""
    ])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def print_tournament_report(report: TournamentReport) -> None:
    """Print tournament report to console."""
    print("\n" + "=" * 100)
    print(f"{report.event} - TOURNAMENT REPORT")
    print(f"Rounds {report.rounds_played} of {report.total_rounds} | {report.site}")
    print(f"Games: {report.games_analyzed} | Decisive: {report.decisive_games} | Draws: {report.drawn_games}")
    print("=" * 100)

    print("\n--- STANDINGS ---\n")
    print(f"{'Rank':<5} {'Player':<30} {'Score':<10} {'W':<3} {'D':<3} {'L':<3}")
    print("-" * 60)

    for i, s in enumerate(report.standings, 1):
        score = f"{s.points:.1f}/{s.games}" if s.points % 1 else f"{int(s.points)}/{s.games}"
        print(f"{i:<5} {s.name:<30} {score:<10} {s.wins:<3} {s.draws:<3} {s.losses:<3}")
