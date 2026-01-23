"""
Round report generator for comprehensive tournament round analysis.
Combines all analysis metrics into a unified report.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..parsers.pgn_parser import read_pgn_file, ParsedGame
from ..parsers.clock_parser import format_time, get_initial_time
from ..analysis.time_analysis import (
    find_long_thinks_pct, analyze_time_pressure_pct,
    LongThinkPct, TimePressureStats,
    print_long_thinks_pct_report, print_time_pressure_pct_report
)
from ..analysis.prep_analysis import (
    analyze_prep_exits, get_first_to_think_summary,
    PrepStats, print_prep_analysis_report
)
from ..analysis.accuracy_analysis import (
    calculate_player_accuracy, find_comebacks, find_blown_leads,
    calculate_time_pressure_accuracy, calculate_long_think_accuracy,
    PlayerAccuracyStats, ComebackRecord, BlownLeadRecord,
    TimePressureAccuracy, LongThinkAccuracy,
    print_accuracy_report, print_comeback_report, print_blown_lead_report,
    print_time_pressure_accuracy_report, print_long_think_accuracy_report
)
from ..analysis.game_dynamics import (
    analyze_dominance, analyze_resilience,
    DominanceMetrics, ResilienceMetrics,
    print_dominance_report, print_resilience_report
)
from ..analysis.engine_analysis import (
    analyze_games, GameEvaluation
)
from ..utils.config import get_config


@dataclass
class RoundReport:
    """Complete analysis report for a tournament round."""
    # Metadata
    round_num: str
    event: str
    games_analyzed: int
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Time metrics
    longest_thinks: List[LongThinkPct] = field(default_factory=list)
    long_think_accuracy: Dict[str, LongThinkAccuracy] = field(default_factory=dict)
    time_pressure_stats: Dict[str, TimePressureStats] = field(default_factory=dict)
    time_pressure_accuracy: Dict[str, TimePressureAccuracy] = field(default_factory=dict)

    # Prep analysis
    prep_stats: Dict[str, PrepStats] = field(default_factory=dict)
    first_to_think: List[Tuple[str, str, str, int, str]] = field(default_factory=list)

    # Accuracy
    player_accuracy: Dict[str, PlayerAccuracyStats] = field(default_factory=dict)

    # Performance
    comebacks: List[ComebackRecord] = field(default_factory=list)
    blown_leads: List[BlownLeadRecord] = field(default_factory=list)

    # Dynamics
    dominance: Dict[str, DominanceMetrics] = field(default_factory=dict)
    resilience: Dict[str, ResilienceMetrics] = field(default_factory=dict)


def generate_round_report(
    pgn_path: Path,
    round_filter: Optional[str] = None,
    time_control_config: Optional[Dict] = None,
    run_engine_analysis: bool = True,
    engine_path: Optional[str] = None,
    engine_depth: int = 20,
    cache_path: Optional[Path] = None,
    verbose: bool = True
) -> RoundReport:
    """
    Generate a comprehensive analysis report for a tournament round.

    Args:
        pgn_path: Path to PGN file
        round_filter: Filter to specific round (e.g., "1", "2.1")
        time_control_config: Time control settings
        run_engine_analysis: Whether to run Stockfish analysis
        engine_path: Path to Stockfish binary
        engine_depth: Search depth for engine
        cache_path: Path for evaluation cache
        verbose: Print progress

    Returns:
        RoundReport with all analysis metrics
    """
    config = get_config()

    # Use config values if not provided
    if time_control_config is None:
        time_control_config = config.active_time_control

    if engine_path is None:
        engine_path = config.engine_path

    if cache_path is None:
        cache_path = config.cache_path

    base_time = get_initial_time(time_control_config)

    # Parse games
    if verbose:
        print(f"Reading PGN file: {pgn_path}")

    all_games = list(read_pgn_file(pgn_path, time_control_config))

    # Filter by round if specified
    if round_filter:
        games = [g for g in all_games if g.metadata.round == round_filter]
        if verbose:
            print(f"Filtered to round {round_filter}: {len(games)} games")
    else:
        games = all_games
        if verbose:
            print(f"Loaded {len(games)} games")

    if not games:
        raise ValueError(f"No games found for round {round_filter}")

    # Get event name and round from first game
    event = games[0].metadata.event
    round_num = round_filter or "all"

    # Thresholds from config
    long_think_pct = config.get("analysis", "time_thresholds", "long_think_pct") or 0.10
    time_pressure_pct = config.get("analysis", "time_thresholds", "time_pressure_pct") or 0.05
    prep_pct = config.get("analysis", "prep_detection", "percentage_threshold") or 0.05
    prep_abs = config.get("analysis", "prep_detection", "absolute_threshold_minutes") or 10

    if verbose:
        print("\n--- Running Time Analysis ---")

    # Time analysis
    _, longest_thinks = find_long_thinks_pct(games, long_think_pct, time_control_config)
    time_pressure_stats = analyze_time_pressure_pct(games, time_pressure_pct, time_control_config)

    if verbose:
        print("--- Running Prep Analysis ---")

    # Prep analysis
    prep_stats = analyze_prep_exits(
        games, time_control_config, method="hybrid",
        pct_threshold=prep_pct, absolute_threshold_minutes=prep_abs
    )
    first_to_think = get_first_to_think_summary(
        games, time_control_config, method="hybrid",
        pct_threshold=prep_pct, absolute_threshold_minutes=prep_abs
    )

    # Engine analysis (if enabled)
    game_evals = []
    player_accuracy = {}
    comebacks = []
    blown_leads = []
    time_pressure_accuracy = {}
    long_think_accuracy = {}
    dominance = {}
    resilience = {}

    if run_engine_analysis:
        if verbose:
            print("\n--- Running Engine Analysis ---")

        game_evals = analyze_games(
            games=games,
            engine_path=engine_path,
            depth=engine_depth,
            skip_opening_moves=config.get("analysis", "engine", "skip_opening_moves") or 8,
            threads=config.get("analysis", "engine", "threads") or 4,
            hash_mb=config.get("analysis", "engine", "hash_mb") or 1024,
            cache_path=cache_path,
            verbose=verbose
        )

        if verbose:
            print("\n--- Calculating Accuracy Metrics ---")

        # Accuracy analysis
        player_accuracy = calculate_player_accuracy(game_evals)
        comebacks = find_comebacks(game_evals)
        blown_leads = find_blown_leads(game_evals)

        # Accuracy correlations
        time_pressure_accuracy = calculate_time_pressure_accuracy(
            game_evals, games, time_pressure_pct, base_time
        )
        long_think_accuracy = calculate_long_think_accuracy(
            game_evals, long_think_pct, base_time
        )

        if verbose:
            print("--- Calculating Game Dynamics ---")

        # Game dynamics
        dominance = analyze_dominance(game_evals)
        resilience = analyze_resilience(game_evals)

    return RoundReport(
        round_num=round_num,
        event=event,
        games_analyzed=len(games),
        longest_thinks=longest_thinks,
        long_think_accuracy=long_think_accuracy,
        time_pressure_stats=time_pressure_stats,
        time_pressure_accuracy=time_pressure_accuracy,
        prep_stats=prep_stats,
        first_to_think=first_to_think,
        player_accuracy=player_accuracy,
        comebacks=comebacks,
        blown_leads=blown_leads,
        dominance=dominance,
        resilience=resilience
    )


def print_round_report(report: RoundReport) -> None:
    """
    Print a formatted round report to console.

    Args:
        report: RoundReport to print
    """
    print("\n" + "=" * 100)
    print(f"ROUND {report.round_num} ANALYSIS REPORT")
    print(f"Event: {report.event}")
    print(f"Games Analyzed: {report.games_analyzed}")
    print(f"Generated: {report.generated_at}")
    print("=" * 100)

    # Long thinks
    if report.longest_thinks:
        player_counts = {}
        for think in report.longest_thinks:
            player_counts[think.player] = player_counts.get(think.player, 0) + 1
        print_long_thinks_pct_report(player_counts, report.longest_thinks)

    # Long think accuracy
    if report.long_think_accuracy:
        print_long_think_accuracy_report(report.long_think_accuracy)

    # Time pressure
    if report.time_pressure_stats:
        print_time_pressure_pct_report(report.time_pressure_stats)

    # Time pressure accuracy
    if report.time_pressure_accuracy:
        print_time_pressure_accuracy_report(report.time_pressure_accuracy)

    # Prep analysis
    if report.prep_stats:
        print_prep_analysis_report(report.prep_stats, report.first_to_think)

    # Player accuracy
    if report.player_accuracy:
        print_accuracy_report(report.player_accuracy)

    # Comebacks and blown leads
    if report.comebacks:
        print_comeback_report(report.comebacks)

    if report.blown_leads:
        print_blown_lead_report(report.blown_leads)

    # Dominance and resilience
    if report.dominance:
        print_dominance_report(report.dominance)

    if report.resilience:
        print_resilience_report(report.resilience)


def export_round_report(
    report: RoundReport,
    output_path: Path,
    format: str = "markdown"
) -> None:
    """
    Export round report to a file.

    Args:
        report: RoundReport to export
        output_path: Path to output file
        format: Output format - "markdown" or "json"
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        _export_json(report, output_path)
    elif format == "markdown":
        _export_markdown(report, output_path)
    else:
        raise ValueError(f"Unknown format: {format}")


def _export_json(report: RoundReport, output_path: Path) -> None:
    """Export report as JSON."""
    # Convert dataclasses to dicts (simplified)
    data = {
        "round_num": report.round_num,
        "event": report.event,
        "games_analyzed": report.games_analyzed,
        "generated_at": report.generated_at,
        "longest_thinks": [
            {
                "player": t.player,
                "opponent": t.opponent,
                "time_spent": t.time_spent,
                "pct_of_total": t.pct_of_total,
                "move_number": t.move_number,
                "color": t.color,
                "round_num": t.round_num
            }
            for t in report.longest_thinks[:20]
        ],
        "first_to_think": report.first_to_think,
        "comebacks": [
            {
                "player": c.player,
                "opponent": c.opponent,
                "worst_eval": c.worst_eval,
                "result": c.result
            }
            for c in report.comebacks
        ],
        "blown_leads": [
            {
                "player": b.player,
                "opponent": b.opponent,
                "best_eval": b.best_eval,
                "result": b.result
            }
            for b in report.blown_leads
        ]
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def _export_markdown(report: RoundReport, output_path: Path) -> None:
    """Export report as Markdown."""
    lines = [
        f"# Round {report.round_num} Analysis Report",
        f"",
        f"**Event:** {report.event}",
        f"**Games Analyzed:** {report.games_analyzed}",
        f"**Generated:** {report.generated_at}",
        "",
        "---",
        ""
    ]

    # Longest Thinks
    if report.longest_thinks:
        lines.extend([
            "## Longest Thinks",
            "",
            "| Player | Time | % of Total | Move | Color | vs Opponent |",
            "|--------|------|------------|------|-------|-------------|"
        ])
        for think in report.longest_thinks[:10]:
            time_str = format_time(think.time_spent, 'MM:SS')
            pct_str = f"{think.pct_of_total*100:.1f}%"
            lines.append(f"| {think.player} | {time_str} | {pct_str} | {think.move_number} | {think.color} | {think.opponent} |")
        lines.append("")

    # Who Thought First
    if report.first_to_think:
        lines.extend([
            "## Who Thought First (Prep Detection)",
            "",
            "| Round | White | Black | First Thinker | Move |",
            "|-------|-------|-------|---------------|------|"
        ])
        for round_num, white, black, exit_move, color in report.first_to_think:
            first = white if color == "White" else black
            lines.append(f"| {round_num} | {white} | {black} | {first} | {exit_move} |")
        lines.append("")

    # Comebacks
    if report.comebacks:
        lines.extend([
            "## Biggest Comebacks",
            "",
            "| Player | Worst Eval | Result | Opponent |",
            "|--------|------------|--------|----------|"
        ])
        for comeback in report.comebacks[:5]:
            eval_str = f"{comeback.worst_eval/100:+.2f}"
            lines.append(f"| {comeback.player} | {eval_str} | {comeback.result} | {comeback.opponent} |")
        lines.append("")

    # Blown Leads
    if report.blown_leads:
        lines.extend([
            "## Biggest Blown Leads",
            "",
            "| Player | Best Eval | Result | Opponent |",
            "|--------|-----------|--------|----------|"
        ])
        for blown in report.blown_leads[:5]:
            eval_str = f"{blown.best_eval/100:+.2f}"
            lines.append(f"| {blown.player} | {eval_str} | {blown.result} | {blown.opponent} |")
        lines.append("")

    # Dominance
    if report.dominance:
        lines.extend([
            "## Dominance Metrics",
            "",
            "| Player | Avg Score | Games Dominated | Moves Ahead |",
            "|--------|-----------|-----------------|-------------|"
        ])
        sorted_dom = sorted(report.dominance.values(), key=lambda x: x.avg_dominance_score, reverse=True)
        for d in sorted_dom:
            lines.append(f"| {d.player_name} | {d.avg_dominance_score:.1f} | {d.games_dominated}/{d.games_analyzed} | {d.total_moves_with_advantage} |")
        lines.append("")

    # Resilience
    if report.resilience:
        lines.extend([
            "## Resilience Metrics",
            "",
            "| Player | Avg Score | Defense Rate | Collapse Rate |",
            "|--------|-----------|--------------|---------------|"
        ])
        sorted_res = sorted(report.resilience.values(), key=lambda x: x.avg_resilience_score, reverse=True)
        for r in sorted_res:
            lines.append(f"| {r.player_name} | {r.avg_resilience_score:.1f} | {r.defense_rate:.1f}% | {r.collapse_rate:.1f}% |")
        lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
