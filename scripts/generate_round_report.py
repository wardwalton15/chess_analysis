#!/usr/bin/env python3
"""
Generate a comprehensive analysis report for a tournament round.

Usage:
    python generate_round_report.py --round 1
    python generate_round_report.py --round 1 --no-engine
    python generate_round_report.py --round 1 --export markdown
    python generate_round_report.py --pgn path/to/file.pgn --round 2
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config import get_config
from src.reports.round_report import (
    generate_round_report,
    print_round_report,
    export_round_report
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a comprehensive tournament round analysis report"
    )
    parser.add_argument(
        "--round", "-r",
        type=str,
        help="Round number to analyze (e.g., '1', '2.1'). If not specified, analyzes all games."
    )
    parser.add_argument(
        "--pgn", "-p",
        type=str,
        help="Path to PGN file. If not specified, uses active tournament from config."
    )
    parser.add_argument(
        "--no-engine",
        action="store_true",
        help="Skip engine analysis (faster, but no accuracy/comeback/dynamics metrics)"
    )
    parser.add_argument(
        "--depth", "-d",
        type=int,
        default=20,
        help="Engine search depth (default: 20)"
    )
    parser.add_argument(
        "--export", "-e",
        type=str,
        choices=["markdown", "json"],
        help="Export report to file (markdown or json)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path for export (default: outputs/reports/round_X_report.md)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Load config
    config = get_config()

    # Determine PGN path
    if args.pgn:
        pgn_path = Path(args.pgn)
    else:
        pgn_file = config.get("active_tournament", "pgn_file")
        pgn_path = Path(config.data_raw_path) / pgn_file

    if not pgn_path.exists():
        print(f"Error: PGN file not found: {pgn_path}")
        sys.exit(1)

    verbose = not args.quiet

    if verbose:
        print(f"\n{'='*60}")
        print("TOURNAMENT ROUND REPORT GENERATOR")
        print(f"{'='*60}")
        print(f"PGN: {pgn_path}")
        print(f"Round: {args.round or 'all'}")
        print(f"Engine analysis: {'disabled' if args.no_engine else f'enabled (depth {args.depth})'}")
        print(f"{'='*60}\n")

    # Generate report
    try:
        report = generate_round_report(
            pgn_path=pgn_path,
            round_filter=args.round,
            run_engine_analysis=not args.no_engine,
            engine_depth=args.depth,
            verbose=verbose
        )
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error generating report: {e}")
        raise

    # Print report
    print_round_report(report)

    # Export if requested
    if args.export:
        if args.output:
            output_path = Path(args.output)
        else:
            round_str = args.round or "all"
            ext = "md" if args.export == "markdown" else "json"
            output_path = Path(config.reports_path) / f"round_{round_str}_report.{ext}"

        export_round_report(report, output_path, args.export)
        print(f"\nReport exported to: {output_path}")


if __name__ == "__main__":
    main()
