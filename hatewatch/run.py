"""Refresh the data, run the simulation, save a new run.

    python -m hatewatch.run
    python -m hatewatch.run --sims 50000
    python -m hatewatch.run --skip-refresh      # reuse what is in the database

Four steps:

  1. REFRESH. Reload this season's games and betting lines from nflverse. This
     replaces the season in place, so scores that have landed since the last
     run and newly posted lines both come in.
  2. SIMULATE. Fit market-implied ratings, price every remaining game, and play
     the rest of the season many times with the real NFL tiebreakers.
  3. COMPUTE. Build every team's season odds and the full impact grid -- all 32
     teams, every remaining game, all four goals.
  4. SAVE. Insert a new run. Nothing is overwritten: old runs stay so odds can
     be charted over time, which is the whole reason for the run_id key.

The run is written in a single transaction. A failure part-way leaves no
half-saved run behind for the website to read.
"""

from __future__ import annotations

import argparse
import datetime as dt

from . import config
from .impacts import build_rows
from .store import insert_impacts, insert_run, insert_team_odds


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=config.DEFAULT_SEASON)
    ap.add_argument("--sims", type=int, default=config.DEFAULT_SIMS)
    ap.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    ap.add_argument("--skip-refresh", action="store_true",
                    help="do not reload games; use what is already stored")
    args = ap.parse_args()

    # Imported here so the sys.path setup in __init__ has already run.
    import load_data
    from simulate import simulate
    from standings import connect, load_games, load_teams
    from win_probability import method_counts

    season = args.season
    print(f"=== hatewatch run: {season}, {args.sims:,} sims ===")
    print(f"  model version: {config.MODEL_VERSION}\n")

    with connect() as conn:
        # --- 1. refresh -----------------------------------------------------
        load_data.apply_schema(conn)
        if args.skip_refresh:
            row = conn.execute(
                "SELECT max(created_at) FROM sim_runs WHERE season = %s",
                (season,),
            ).fetchone()
            data_as_of = row[0] or dt.datetime.now(dt.timezone.utc)
            print("  refresh skipped; reusing stored games")
        else:
            print("  refreshing games and lines...")
            load_data.load_season_table(conn, load_data.GAMES, [season])
            # The data is as current as the moment we finished pulling it.
            data_as_of = dt.datetime.now(dt.timezone.utc)

        teams = load_teams(conn)
        games = load_games(conn, season)
        remaining = [g for g in games if not g.played]
        if not remaining:
            print(f"\n  {season} regular season is complete; nothing to simulate.")
            return 0
        week = min(g.week for g in remaining)
        print(f"  {len(games) - len(remaining)} played, {len(remaining)} remaining; "
              f"current week {week}")

        # --- 2. simulate ----------------------------------------------------
        print(f"\n  simulating {args.sims:,} seasons...")
        res = simulate(
            conn, season, args.sims, "MIN", args.seed,
            use_ratings=True, real_tiebreakers=True,
        )
        counts = method_counts(res.games)
        print("  pricing: "
              + ", ".join(f"{m} {c}" for m, c in counts.items() if c))
        if res.tiebreaks_resolved:
            print(f"  tiebreaks: {res.tiebreaks_resolved:,} resolved, "
                  f"{res.coin_tosses:,} coin tosses")

        # --- 3. compute -----------------------------------------------------
        print("\n  building impact grid for all 32 teams...")
        odds, rows = build_rows(res, teams)
        print(f"  {len(odds)} team rows, {len(rows):,} impact rows")

        # --- 4. save --------------------------------------------------------
        run_id = insert_run(
            conn,
            season=season,
            week=week,
            n_sims=args.sims,
            data_as_of=data_as_of,
        )
        insert_team_odds(conn, run_id, odds)
        insert_impacts(conn, run_id, rows)
        conn.commit()

        total = conn.execute("SELECT count(*) FROM sim_runs").fetchone()[0]
        print(f"\n  saved run {run_id} ({total} run(s) stored in total)")

        tiers = conn.execute(
            """
            SELECT tier, count(*) FROM game_impacts
            WHERE run_id = %s GROUP BY tier ORDER BY count(*) DESC
            """,
            (run_id,),
        ).fetchall()
        print("\n  tier distribution across all teams and goals")
        for tier, n in tiers:
            label = config.TIER_LABELS.get(tier, tier)
            print(f"    {label:<16} {n:>7,}  ({n / len(rows) * 100:4.1f}%)")

        reasons = conn.execute(
            """
            SELECT reason_code, count(*) FROM game_impacts
            WHERE run_id = %s AND tier <> 'doesnt_matter'
            GROUP BY reason_code ORDER BY count(*) DESC
            """,
            (run_id,),
        ).fetchall()
        if reasons:
            print("\n  reason codes, among rows that DO matter")
            for code, n in reasons:
                label = config.REASON_LABELS.get(code, code)
                print(f"    {label:<22} {n:>7,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
