"""Report data coverage for a season: what's played, what's left, and which
remaining games have betting lines.

Usage:
    python etl/coverage_report.py              # 2026
    python etl/coverage_report.py --season 2025

The win-probability model needs a moneyline or a spread per remaining game and
falls back to a coin flip without either, so this report says up front how much
of the schedule is actually priced.
"""

from __future__ import annotations

import argparse
import os

import psycopg
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    args = ap.parse_args()

    load_dotenv(os.path.join(HERE, "..", ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (expected in .env)")

    with psycopg.connect(url) as conn:
        # A game counts as completed once it has a home score.
        total, played, remaining = conn.execute(
            """
            SELECT count(*),
                   count(*) FILTER (WHERE home_score IS NOT NULL),
                   count(*) FILTER (WHERE home_score IS NULL)
            FROM games WHERE season = %s
            """,
            (args.season,),
        ).fetchone()

        print(f"=== {args.season} season coverage ===\n")
        if total == 0:
            print("No games loaded for this season.")
            return 1
        print(f"  games in schedule : {total}")
        print(f"  completed         : {played}")
        print(f"  remaining         : {remaining}")

        if remaining == 0:
            print("\nSeason complete, nothing left to simulate.")
            return 0

        # Which pricing source each remaining game has. A game needs BOTH
        # moneylines to de-vig, so "has moneyline" means both are present.
        rows = conn.execute(
            """
            SELECT week,
                   count(*) AS remaining,
                   count(*) FILTER (
                       WHERE home_moneyline IS NOT NULL
                         AND away_moneyline IS NOT NULL) AS has_ml,
                   count(*) FILTER (WHERE spread_line IS NOT NULL) AS has_spread,
                   count(*) FILTER (
                       WHERE (home_moneyline IS NULL OR away_moneyline IS NULL)
                         AND spread_line IS NULL) AS has_neither
            FROM games
            WHERE season = %s AND home_score IS NULL
            GROUP BY week ORDER BY week
            """,
            (args.season,),
        ).fetchall()

        print(f"\n  Remaining games by week and available pricing")
        print(f"  {'week':>4}  {'games':>6}  {'moneyline':>9}  {'spread':>7}  {'neither':>8}")
        print("  " + "-" * 42)
        for week, rem, ml, spread, neither in rows:
            print(f"  {week:>4}  {rem:>6}  {ml:>9}  {spread:>7}  {neither:>8}")
        print("  " + "-" * 42)
        tot_ml = sum(r[2] for r in rows)
        tot_sp = sum(r[3] for r in rows)
        tot_ne = sum(r[4] for r in rows)
        print(f"  {'all':>4}  {remaining:>6}  {tot_ml:>9}  {tot_sp:>7}  {tot_ne:>8}")

        pct = 100.0 * tot_ne / remaining
        print(
            f"\n  {tot_ml} remaining games are priced with a moneyline, "
            f"{tot_sp} with a spread."
        )
        print(
            f"  {tot_ne} ({pct:.0f}%) have neither and will fall back to 50/50."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
