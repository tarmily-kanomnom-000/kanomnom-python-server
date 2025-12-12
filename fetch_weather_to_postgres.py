#!/usr/bin/env python3
"""CLI entrypoint for fetching hourly weather into PostgreSQL."""

from __future__ import annotations

import argparse

from src.services.weather.config import DEFAULT_DATABASE_CONFIG, DEFAULT_LOCATIONS
from src.services.weather.documentation import describe_metric_table
from src.services.weather.job import WeatherIngestJob, determine_date_range


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch hourly weather from Open-Meteo and store in PostgreSQL.",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Default: same as start-date.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print data without writing to database.",
    )
    parser.add_argument(
        "--describe-table",
        type=str,
        help=("Print column documentation for either 'weather_hourly' or " "'weather_window_metrics' and exit."),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.describe_table:
        describe_metric_table(args.describe_table)
        return

    start_date, end_date = determine_date_range(args.start_date, args.end_date)
    job = WeatherIngestJob(
        db_config=DEFAULT_DATABASE_CONFIG,
        locations=DEFAULT_LOCATIONS,
    )
    job.run(start_date=start_date, end_date=end_date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
