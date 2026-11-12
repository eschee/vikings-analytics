"""Load nflverse data into Postgres.

Usage:
    python etl/load_data.py                      # all tables, seasons 2022-2025
    python etl/load_data.py --seasons 2025       # just one season
    python etl/load_data.py --tables games plays # just some tables

Re-runnable by design. Season-scoped tables (games, plays) delete the seasons
being loaded before inserting them, so reloading 2025 replaces 2025 and leaves
the other seasons alone. The snapshot tables (players, contracts) have no
season column upstream, so each load fully replaces them.
"""

from __future__ import annotations

import argparse
import os
import sys

import nflreadpy as nfl
import polars as pl
import psycopg
from dotenv import load_dotenv

DEFAULT_SEASONS = [2022, 2023, 2024, 2025]
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "..", "sql", "001_create_tables.sql")


# ---------------------------------------------------------------------------
# Column specs
#
# Each spec says which upstream columns to keep and how to type them. Anything
# not listed is dropped. `rename` handles the two upstream names that collide
# with SQL reserved words ("desc") or read ambiguously ("pass"/"rush").
#
# nflverse returns most numeric play-by-play columns as Float64 even when they
# are logically integers or flags (down, qtr, shotgun...), so we cast here
# rather than letting Postgres reject them.
# ---------------------------------------------------------------------------

GAMES = {
    "table": "games",
    "scope": "season",
    "columns": [
        "game_id", "season", "game_type", "week", "gameday", "weekday", "gametime",
        "away_team", "home_team", "away_score", "home_score", "result", "total",
        "overtime", "location", "div_game",
        "spread_line", "total_line", "away_moneyline", "home_moneyline",
        "away_spread_odds", "home_spread_odds", "under_odds", "over_odds",
        "roof", "surface", "temp", "wind", "stadium", "stadium_id",
        "away_qb_id", "home_qb_id", "away_qb_name", "home_qb_name",
        "away_coach", "home_coach", "referee",
        "away_rest", "home_rest", "old_game_id",
    ],
    "bools": ["overtime", "div_game"],
    "dates": ["gameday"],
    "ints": [
        "season", "week", "away_score", "home_score", "result", "total",
        "temp", "wind", "away_rest", "home_rest",
        "away_moneyline", "home_moneyline", "away_spread_odds",
        "home_spread_odds", "under_odds", "over_odds",
    ],
    "floats": ["spread_line", "total_line"],
    "rename": {},
}

# 46 columns kept out of the 372 nflverse ships.
PLAYS = {
    "table": "plays",
    "scope": "season",
    "columns": [
        # identity / context
        "game_id", "play_id", "season", "week", "season_type", "game_date",
        "home_team", "away_team", "posteam", "defteam",
        # situation
        "qtr", "down", "ydstogo", "yardline_100", "goal_to_go", "drive",
        "game_seconds_remaining",
        # what happened
        "play_type", "desc", "yards_gained", "shotgun", "no_huddle",
        "pass", "rush", "air_yards", "yards_after_catch",
        "pass_length", "pass_location", "run_location", "run_gap",
        # efficiency
        "epa", "qb_epa", "cpoe", "success", "wp", "wpa",
        # score state
        "posteam_score", "defteam_score", "score_differential",
        # outcomes
        "first_down", "touchdown", "interception", "fumble_lost", "penalty",
        # players
        "passer_player_id", "passer_player_name",
        "rusher_player_id", "rusher_player_name",
        "receiver_player_id", "receiver_player_name",
    ],
    "rename": {"desc": "play_desc", "pass": "pass_play", "rush": "rush_play"},
    "bools": [
        "goal_to_go", "shotgun", "no_huddle", "pass_play", "rush_play",
        "success", "first_down", "touchdown", "interception", "fumble_lost",
        "penalty",
    ],
    "dates": ["game_date"],
    "ints": [
        "play_id", "season", "week", "qtr", "down", "ydstogo", "yardline_100",
        "drive", "game_seconds_remaining", "yards_gained", "air_yards",
        "yards_after_catch", "posteam_score", "defteam_score",
        "score_differential",
    ],
    "floats": ["epa", "qb_epa", "cpoe", "wp", "wpa"],
}

PLAYERS = {
    "table": "players",
    "scope": "snapshot",
    "columns": [
        "gsis_id", "display_name", "first_name", "last_name", "football_name",
        "birth_date", "position", "position_group", "height", "weight",
        "jersey_number", "college_name", "college_conference", "rookie_season",
        "last_season", "years_of_experience", "latest_team", "status",
        "draft_year", "draft_round", "draft_pick", "draft_team", "headshot",
        "esb_id", "pfr_id", "pff_id", "otc_id", "espn_id", "smart_id",
    ],
    "rename": {},
    "bools": [],
    "dates": ["birth_date"],
    "ints": [
        "height", "weight", "rookie_season", "last_season",
        "years_of_experience", "draft_year", "draft_round", "draft_pick",
    ],
    "floats": [],
}

CONTRACTS = {
    "table": "contracts",
    "scope": "snapshot",
    # contract_id is a Postgres IDENTITY column, so it is not loaded.
    # season_history / contract_history are nested List(Struct) upstream and
    # are deliberately skipped.
    "columns": [
        "player", "gsis_id", "otc_id", "position", "team", "is_active",
        "year_signed", "years", "value", "apy", "guaranteed", "apy_cap_pct",
        "inflated_value", "inflated_apy", "inflated_guaranteed",
        "draft_year", "draft_round", "draft_overall", "draft_team",
        "college", "date_of_birth", "player_page",
    ],
    "rename": {},
    "bools": ["is_active"],
    "dates": ["date_of_birth"],
    "ints": [
        "otc_id", "year_signed", "years", "draft_year", "draft_round",
        "draft_overall",
    ],
    "floats": [
        "value", "apy", "guaranteed", "apy_cap_pct", "inflated_value",
        "inflated_apy", "inflated_guaranteed",
    ],
}

SPECS = {s["table"]: s for s in (GAMES, PLAYS, PLAYERS, CONTRACTS)}


def prepare(df: pl.DataFrame, spec: dict) -> pl.DataFrame:
    """Select the columns we want and coerce them to database-friendly types."""
    missing = [c for c in spec["columns"] if c not in df.columns]
    if missing:
        raise SystemExit(f"{spec['table']}: upstream data is missing {missing}")

    df = df.select(spec["columns"])

    # Rename before casting: the type lists below use the final column names.
    if spec["rename"]:
        df = df.rename(spec["rename"])

    casts = []
    for col in spec["bools"]:
        # nflverse flags arrive as 0.0/1.0/null floats
        casts.append(pl.col(col).cast(pl.Boolean, strict=False).alias(col))
    for col in spec["ints"]:
        casts.append(pl.col(col).cast(pl.Int32, strict=False).alias(col))
    for col in spec["floats"]:
        # NaN and NULL are different in Postgres; we want NULL for both
        casts.append(
            pl.col(col).cast(pl.Float64, strict=False).fill_nan(None).alias(col)
        )
    for col in spec["dates"]:
        casts.append(
            pl.col(col).cast(pl.Utf8).str.to_date(strict=False).alias(col)
        )
    if casts:
        df = df.with_columns(casts)
    return df


def copy_into(conn: psycopg.Connection, table: str, df: pl.DataFrame) -> int:
    """Stream a DataFrame into Postgres with COPY (much faster than INSERTs)."""
    cols = ", ".join(f'"{c}"' for c in df.columns)
    with conn.cursor() as cur:
        with cur.copy(f"COPY {table} ({cols}) FROM STDIN") as cp:
            for row in df.iter_rows():
                cp.write_row(row)
    return df.height


def apply_schema(conn: psycopg.Connection) -> None:
    """Run the schema file. Every statement is IF NOT EXISTS, so this is safe
    to run on every load."""
    with open(os.path.abspath(SCHEMA_FILE)) as fh:
        conn.execute(fh.read())
    conn.commit()
    print("schema applied")


def load_season_table(conn: psycopg.Connection, spec: dict, seasons: list[int]) -> None:
    """Load a season-scoped table one season at a time, replacing each season."""
    table = spec["table"]
    loader = nfl.load_schedules if table == "games" else nfl.load_pbp

    for season in seasons:
        raw = loader(seasons=[season])
        # load_schedules ignores unknown seasons rather than erroring, and pbp
        # for an unplayed season comes back empty — guard both.
        if raw.height == 0:
            print(f"  {table} {season}: no upstream data, skipped")
            continue
        df = prepare(raw, spec)

        # DELETE + COPY inside one transaction: a failure rolls back and leaves
        # the previously loaded season intact rather than half-deleted.
        deleted = conn.execute(
            f"DELETE FROM {table} WHERE season = %s", (season,)
        ).rowcount
        inserted = copy_into(conn, table, df)
        conn.commit()
        print(f"  {table} {season}: -{deleted} +{inserted}")


def load_snapshot_table(conn: psycopg.Connection, spec: dict) -> None:
    """Fully replace a table that has no season dimension upstream."""
    table = spec["table"]
    loader = nfl.load_players if table == "players" else nfl.load_contracts
    df = prepare(loader(), spec)

    conn.execute(f"TRUNCATE {table} RESTART IDENTITY")
    inserted = copy_into(conn, table, df)
    conn.commit()
    print(f"  {table}: replaced, +{inserted}")


def analyze(conn: psycopg.Connection, tables: list[str]) -> None:
    """COPY does not update planner statistics, and autovacuum may not have run
    yet. Without this the planner misjudges selectivity on a freshly loaded
    table and ignores the composite indexes."""
    for table in tables:
        conn.execute(f"ANALYZE {table}")
    conn.commit()
    print("analyzed")


def row_counts(conn: psycopg.Connection) -> None:
    print("\nRow counts")
    print("-" * 46)
    for table in SPECS:
        total = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<12} {total:>10,}")
    print("-" * 46)
    print("\nPer season")
    for table in ("games", "plays"):
        rows = conn.execute(
            f"SELECT season, count(*) FROM {table} GROUP BY season ORDER BY season"
        ).fetchall()
        detail = "  ".join(f"{s}: {c:,}" for s, c in rows)
        print(f"  {table:<7} {detail}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", type=int, nargs="+", default=DEFAULT_SEASONS)
    ap.add_argument(
        "--tables", nargs="+", choices=list(SPECS), default=list(SPECS)
    )
    args = ap.parse_args()

    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (expected in .env)")

    print(f"seasons: {args.seasons}")
    print(f"tables:  {args.tables}\n")

    with psycopg.connect(url) as conn:
        apply_schema(conn)
        for table in args.tables:
            spec = SPECS[table]
            if spec["scope"] == "season":
                load_season_table(conn, spec, args.seasons)
            else:
                load_snapshot_table(conn, spec)
        analyze(conn, args.tables)
        row_counts(conn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
