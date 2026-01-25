#!/usr/bin/env python3
"""
Generate a comprehensive tournament analysis report.

Usage:
    python generate_tournament_report.py --pgn path/to/tournament.pgn
    python generate_tournament_report.py --pgn tournament.pgn --rounds 7 --total-rounds 13
    python generate_tournament_report.py --pgn tournament.pgn --output report.md
    python generate_tournament_report.py --pgn tournament.pgn --time-control tata_steel_2026
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.reports.tournament_report import (
    generate_tournament_report,
    export_tournament_report,
    print_tournament_report
)


# Common time controls for easy reference
TIME_CONTROLS = {
    "tata_steel": {
        "name": "Tata Steel Masters",
        "base_time": 7200,  # 120 minutes
        "increment_type": "delay_bonus",
        "increment_start_move": 41,
        "increment_seconds": 30,
        "bonus_time": 1800,  # 30 minutes after move 40
        "has_increment_before_bonus": False
    },
    "candidates": {
        "name": "FIDE Candidates",
        "base_time": 7200,
        "increment_type": "delay_bonus",
        "increment_start_move": 41,
        "increment_seconds": 30,
        "bonus_time": 1800,
        "has_increment_before_bonus": False
    },
    "rapid_25_10": {
        "name": "Rapid 25+10",
        "base_time": 1500,
        "increment_type": "fischer",
        "increment_start_move": 1,
        "increment_seconds": 10,
        "bonus_time": 0,
        "has_increment_before_bonus": False
    },
    "classical_90_30": {
        "name": "Classical 90+30",
        "base_time": 5400,
        "increment_type": "fischer",
        "increment_start_move": 1,
        "increment_seconds": 30,
        "bonus_time": 0,
        "has_increment_before_bonus": True
    }
}


def main():
    parser = argparse.ArgumentParser(
        description="Generate a comprehensive tournament analysis report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available time controls:
  tata_steel     - 120min + 30min after move 40, 30sec increment from move 41
  candidates     - Same as tata_steel (FIDE Candidates format)
  rapid_25_10    - 25 minutes + 10 second Fischer increment
  classical_90_30 - 90 minutes + 30 second Fischer increment

Examples:
  python generate_tournament_report.py --pgn tournament.pgn
  python generate_tournament_report.py --pgn tournament.pgn --time-control tata_steel
  python generate_tournament_report.py --pgn tournament.pgn --rounds 7 --total-rounds 13
        """
    )

    parser.add_argument(
        "--pgn", "-p",
        type=str,
        required=True,
        help="Path to PGN file"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path for markdown report"
    )
    parser.add_argument(
        "--rounds", "-r",
        type=int,
        help="Number of completed rounds (auto-detected if not specified)"
    )
    parser.add_argument(
        "--total-rounds", "-t",
        type=int,
        help="Total rounds in tournament (for display purposes)"
    )
    parser.add_argument(
        "--time-control", "-tc",
        type=str,
        choices=list(TIME_CONTROLS.keys()),
        default="tata_steel",
        help="Time control preset (default: tata_steel)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Don't export to file, only print to console"
    )

    args = parser.parse_args()

    # Validate PGN path
    pgn_path = Path(args.pgn)
    if not pgn_path.exists():
        # Try relative to data/raw
        config = get_config()
        alt_path = Path(config.data_raw_path) / args.pgn
        if alt_path.exists():
            pgn_path = alt_path
        else:
            print(f"Error: PGN file not found: {pgn_path}")
            sys.exit(1)

    # Get time control config
    time_control_config = TIME_CONTROLS[args.time_control]

    verbose = not args.quiet

    if verbose:
        print(f"\n{'='*60}")
        print("TOURNAMENT REPORT GENERATOR")
        print(f"{'='*60}")
        print(f"PGN: {pgn_path}")
        print(f"Time Control: {time_control_config['name']}")
        if args.rounds:
            print(f"Completed Rounds: {args.rounds}")
        if args.total_rounds:
            print(f"Total Rounds: {args.total_rounds}")
        print(f"{'='*60}\n")

    # Generate report
    try:
        report = generate_tournament_report(
            pgn_path=pgn_path,
            time_control_config=time_control_config,
            completed_rounds=args.rounds,
            total_rounds=args.total_rounds,
            verbose=verbose
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating report: {e}")
        raise

    # Print to console
    print_tournament_report(report)

    # Export to file
    if not args.no_export:
        if args.output:
            output_path = Path(args.output)
        else:
            # Auto-generate output path
            config = get_config()
            event_slug = report.event.lower().replace(" ", "-").replace(".", "")
            output_path = Path(config.reports_path) / f"{event_slug}-report.md"

        export_tournament_report(report, output_path)
        print(f"\nReport exported to: {output_path}")


if __name__ == "__main__":
    main()
