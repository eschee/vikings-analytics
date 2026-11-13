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
from zoneinfo import ZoneInfo

from . import PROJECT_ROOT, config
from .store import impacts_for, latest_run_id, run_meta, team_odds_for

DEFAULT_OUT_DIR = os.path.join(PROJECT_ROOT, "web", "sample-data")

# nflverse publishes kickoff times in US Eastern. The site shows Central,
# which is where the Vikings play, so we convert once here and ship a
# preformatted string. Doing it server-side keeps the rendered time identical
# everywhere instead of varying with the reader's browser timezone.
KICKOFF_SOURCE_TZ = ZoneInfo("America/New_York")
KICKOFF_DISPLAY_TZ = ZoneInfo("America/Chicago")
KICKOFF_TZ_LABEL = "CT"


def format_kickoff(gameday, weekday: str | None, gametime: str | None) -> dict:
    """Build the kickoff strings the page shows. Never raises on odd input."""
    out = {
        "iso": None,
        "day": (weekday or "")[:3],
        "time": None,
        "label": (weekday or "")[:3],
        "tz": KICKOFF_TZ_LABEL,
    }
    if gameday is None or not gametime:
        return out
    try:
        hour, minute = (int(p) for p in str(gametime).split(":")[:2])
    except (ValueError, TypeError):
        return out
    eastern = dt.datetime(
        gameday.year, gameday.month, gameday.day, hour, minute,
        tzinfo=KICKOFF_SOURCE_TZ,
    )
    local = eastern.astimezone(KICKOFF_DISPLAY_TZ)
    day = local.strftime("%a")
    # %-I is "1" not "01"; strftime on macOS and Linux both accept it.
    clock = local.strftime("%-I:%M %p")
    out.update(
        {"iso": local.isoformat(), "day": day, "time": clock,
         "label": f"{day} {clock}"}
    )
    return out


def _jsonable(value):
    """Decimals become floats and timestamps ISO strings, so the payload is
    plain JSON the frontend can consume without a custom reviver."""
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def team_record(conn, season: int, team: str) -> dict:
    """The team's W-L-T so far, reusing the validated standings code rather
    than counting games again here."""
    from standings import compute_records, load_games, load_teams

    teams = load_teams(conn)
    games = load_games(conn, season)
    rec = compute_records(games, teams)[team]
    text = f"{rec.wins}-{rec.losses}" + (f"-{rec.ties}" if rec.ties else "")
    return {
        "wins": rec.wins,
        "losses": rec.losses,
        "ties": rec.ties,
        "text": text,
    }


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

    # Nicknames for every team, so the page can say "Cardinals" rather than
    # "ARI" without shipping a hardcoded map to the frontend.
    nicknames = {
        r[0]: r[1] for r in conn.execute(
            "SELECT team_abbr, team_nick FROM teams WHERE is_current"
        ).fetchall()
    }

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
        if "kickoff" not in game:
            game["kickoff"] = format_kickoff(
                r["gameday"], r["weekday"], r["gametime"]
            )
        game["goals"][r["goal"]] = {
            "root_for": r["root_for"],
            "against": (
                r["home_team"] if r["root_for"] == r["away_team"]
                else r["away_team"]
            ),
            "impact_pts": r["impact_pts"],
            "root_for_win_pct": r["root_for_win_pct"],
            "value_if_root_for_wins": r["value_if_root_for_wins"],
            "value_if_root_for_loses": r["value_if_root_for_loses"],
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
            "nick": nicknames.get(team),
            "conference": teams_row[2] if teams_row else None,
            "division": teams_row[3] if teams_row else None,
            "record": team_record(conn, meta["season"], team),
        },
        "nicknames": nicknames,
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
