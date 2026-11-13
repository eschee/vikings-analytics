"""Write and read simulation results.

Every statement here is either a static string or uses psycopg parameter
placeholders. No SQL is built by joining strings, including the table names --
they are literals in the query text.

Writes go through the write database user (the refresh job). The website reads
these tables through a read-only user.
"""

from __future__ import annotations

import datetime as dt

import psycopg

from .config import MODEL_VERSION
from .impacts import ImpactRow, TeamOdds


def insert_run(
    conn: psycopg.Connection,
    *,
    season: int,
    week: int,
    n_sims: int,
    data_as_of: dt.datetime,
    model_version: str = MODEL_VERSION,
) -> int:
    """Create a run row and return its id."""
    row = conn.execute(
        """
        INSERT INTO sim_runs (season, week, n_sims, data_as_of, model_version)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING run_id
        """,
        (season, week, n_sims, data_as_of, model_version),
    ).fetchone()
    return int(row[0])


def insert_team_odds(
    conn: psycopg.Connection, run_id: int, odds: list[TeamOdds]
) -> int:
    """COPY the per-team odds in. 32 rows, but COPY keeps it uniform with the
    much larger impacts write below."""
    with conn.cursor() as cur:
        with cur.copy(
            "COPY team_odds (run_id, team, playoff_pct, division_pct, "
            "top_seed_pct, avg_seed) FROM STDIN"
        ) as cp:
            for o in odds:
                cp.write_row(
                    (run_id, o.team, round(o.playoff_pct, 3),
                     round(o.division_pct, 3), round(o.top_seed_pct, 3),
                     None if o.avg_seed is None else round(o.avg_seed, 3))
                )
    return len(odds)


def insert_impacts(
    conn: psycopg.Connection, run_id: int, rows: list[ImpactRow]
) -> int:
    """COPY the impact grid in -- roughly 17k rows per run."""
    with conn.cursor() as cur:
        with cur.copy(
            "COPY game_impacts (run_id, game_id, team, goal, root_for, "
            "impact_pts, root_for_win_pct, tier, reason_code) FROM STDIN"
        ) as cp:
            for r in rows:
                cp.write_row(
                    (run_id, r.game_id, r.team, r.goal, r.root_for,
                     round(r.impact_pts, 3), round(r.root_for_win_pct, 3),
                     r.tier, r.reason_code)
                )
    return len(rows)


def latest_run_id(
    conn: psycopg.Connection, season: int | None = None
) -> int | None:
    """Most recent run, optionally restricted to one season."""
    if season is None:
        row = conn.execute(
            "SELECT run_id FROM sim_runs ORDER BY created_at DESC, run_id DESC"
            " LIMIT 1"
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT run_id FROM sim_runs WHERE season = %s"
            " ORDER BY created_at DESC, run_id DESC LIMIT 1",
            (season,),
        ).fetchone()
    return int(row[0]) if row else None


def run_meta(conn: psycopg.Connection, run_id: int) -> dict | None:
    row = conn.execute(
        """
        SELECT run_id, created_at, season, week, n_sims, data_as_of,
               model_version
        FROM sim_runs WHERE run_id = %s
        """,
        (run_id,),
    ).fetchone()
    if not row:
        return None
    keys = ("run_id", "created_at", "season", "week", "n_sims", "data_as_of",
            "model_version")
    return dict(zip(keys, row))


def team_odds_for(
    conn: psycopg.Connection, run_id: int, team: str | None = None
) -> list[dict]:
    if team is None:
        rows = conn.execute(
            """
            SELECT team, playoff_pct, division_pct, top_seed_pct, avg_seed
            FROM team_odds WHERE run_id = %s ORDER BY playoff_pct DESC, team
            """,
            (run_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT team, playoff_pct, division_pct, top_seed_pct, avg_seed
            FROM team_odds WHERE run_id = %s AND team = %s
            """,
            (run_id, team),
        ).fetchall()
    keys = ("team", "playoff_pct", "division_pct", "top_seed_pct", "avg_seed")
    return [dict(zip(keys, r)) for r in rows]


def impacts_for(
    conn: psycopg.Connection,
    run_id: int,
    team: str,
    goal: str | None = None,
    week: int | None = None,
) -> list[dict]:
    """Impact rows for one team, joined to the game for display fields.

    The optional clauses append FIXED query text, never caller data -- every
    value still travels as a bound parameter.
    """
    sql = """
        SELECT i.game_id, g.week, g.away_team, g.home_team, i.goal,
               i.root_for, i.impact_pts, i.root_for_win_pct, i.tier,
               i.reason_code
        FROM game_impacts i
        JOIN games g ON g.game_id = i.game_id
        WHERE i.run_id = %s AND i.team = %s
    """
    params: list = [run_id, team]
    if goal is not None:
        sql += " AND i.goal = %s"
        params.append(goal)
    if week is not None:
        sql += " AND g.week = %s"
        params.append(week)
    sql += " ORDER BY g.week, i.impact_pts DESC"
    rows = conn.execute(sql, params).fetchall()
    keys = ("game_id", "week", "away_team", "home_team", "goal", "root_for",
            "impact_pts", "root_for_win_pct", "tier", "reason_code")
    return [dict(zip(keys, r)) for r in rows]
