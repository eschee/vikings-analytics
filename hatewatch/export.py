"""Export the latest run for one team as JSON.

Gives the website something real to build against before it talks to the
database. The shape here is the shape the API should eventually return, so the
frontend does not have to be rewritten when the database is wired up.

    python -m hatewatch.export --team MIN
    python -m hatewatch.export --team CHI --out /tmp/chi.json
    python -m hatewatch.export --team MIN --run-id 3

The team argument is checked against the 32 teams in the database and anything
else is refused with the list of valid values, rather than being passed down
into a query or returning an empty file that looks like a real answer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import os
from collections import OrderedDict

from . import PROJECT_ROOT, config
from .store import impacts_for, latest_run_id, run_meta, team_odds_for

DEFAULT_OUT_DIR = os.path.join(PROJECT_ROOT, "web", "sample-data")


def _jsonable(value):
    """Decimals become floats and timestamps ISO strings, so the payload is
    plain JSON the frontend can consume without a custom reviver."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def build_payload(conn, team: str, run_id: int) -> dict:
    meta = run_meta(conn, run_id)
    if meta is None:
        raise SystemExit(f"run {run_id} not found")

    odds_rows = team_odds_for(conn, run_id, team)
    odds = odds_rows[0] if odds_rows else None

    teams_row = conn.execute(
        """
        SELECT team_abbr, team_name, team_conf, team_division
        FROM teams WHERE team_abbr = %s
        """,
        (team,),
    ).fetchone()

    rows = impacts_for(conn, run_id, team)

    # Group by week, then by game, with all four goals under each game. That is
    # how the page reads: pick a week, scan the games, see what to root for.
    weeks: "OrderedDict[int, OrderedDict[str, dict]]" = OrderedDict()
    for r in rows:
        week_games = weeks.setdefault(r["week"], OrderedDict())
        game = week_games.setdefault(
            r["game_id"],
            {
                "game_id": r["game_id"],
                "away": r["away_team"],
                "home": r["home_team"],
                "goals": {},
            },
        )
        game["goals"][r["goal"]] = {
            "root_for": r["root_for"],
            "against": (
                r["home_team"] if r["root_for"] == r["away_team"]
                else r["away_team"]
            ),
            "impact_pts": r["impact_pts"],
            "root_for_win_pct": r["root_for_win_pct"],
            "tier": r["tier"],
            "tier_label": config.TIER_LABELS.get(r["tier"], r["tier"]),
            "reason_code": r["reason_code"],
            "reason_label": config.REASON_LABELS.get(
                r["reason_code"], r["reason_code"]
            ),
        }

    week_list = []
    for week, games in sorted(weeks.items()):
        ordered = sorted(
            games.values(),
            key=lambda g: -g["goals"].get("playoffs", {}).get("impact_pts", 0),
        )
        week_list.append({"week": week, "games": ordered})

    return {
        "run": meta,
        "team": {
            "abbr": teams_row[0] if teams_row else team,
            "name": teams_row[1] if teams_row else None,
            "conference": teams_row[2] if teams_row else None,
            "division": teams_row[3] if teams_row else None,
        },
        "odds": odds,
        "thresholds": {
            "must_win": config.MUST_WIN_THRESHOLD,
            "root_hard": config.ROOT_HARD_THRESHOLD,
            "min_noise_floor": config.MIN_NOISE_FLOOR,
        },
        "tier_labels": config.TIER_LABELS,
        "reason_labels": config.REASON_LABELS,
        "weeks": week_list,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team", default="MIN")
    ap.add_argument("--run-id", type=int, help="default: the most recent run")
    ap.add_argument("--season", type=int, default=config.DEFAULT_SEASON)
    ap.add_argument("--out", help="output path (default: web/sample-data/)")
    args = ap.parse_args()

    from standings import connect

    with connect() as conn:
        # Allowlist check against the real team list.
        valid = [
            r[0] for r in conn.execute(
                "SELECT team_abbr FROM teams WHERE is_current ORDER BY team_abbr"
            ).fetchall()
        ]
        team = args.team.upper()
        if team not in valid:
            raise SystemExit(
                f"unknown team {args.team!r}. Valid: {', '.join(valid)}"
            )

        run_id = args.run_id or latest_run_id(conn, args.season)
        if run_id is None:
            raise SystemExit(
                f"no saved runs for {args.season}; run `python -m hatewatch.run`"
            )

        payload = build_payload(conn, team, run_id)

    out = args.out or os.path.join(DEFAULT_OUT_DIR, f"{team.lower()}-latest.json")
    # A bare filename like --out foo.json has no directory part, and makedirs("")
    # raises rather than treating it as the current directory.
    out_dir = os.path.dirname(out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out, "w") as fh:
        json.dump(payload, fh, indent=2, default=_jsonable)
        fh.write("\n")

    size = os.path.getsize(out)
    n_games = sum(len(w["games"]) for w in payload["weeks"])
    print(f"wrote {out}")
    print(f"  run {run_id}, {team}, {len(payload['weeks'])} weeks, "
          f"{n_games} games, {size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
