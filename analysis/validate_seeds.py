"""Check the tiebreaker code against what actually happened.

HOW THE REAL SEEDS ARE RECOVERED

The games table has no seed column, but the playoff bracket encodes it. In the
current 14-team format each conference sends seven teams, the #1 seed rests in
the wild-card round, and the other six play 2v7, 3v6 and 4v5 with the higher
seed at home. So from the wild-card weekend alone:

  * the three HOME teams are the division winners seeded 2, 3 and 4
  * the three AWAY teams are the wild cards, seeded 5, 6 and 7
  * the team that skips the round and appears in the divisional round is the
    #1 seed, which is also a division winner

That pins down three things without assuming anything about records: which four
teams won divisions, which three got wild cards, and who was #1.

It also pins down the exact ORDER, through the pairings. Seed 2 hosts seed 7,
seed 3 hosts 6, seed 4 hosts 5 -- in every case the two seeds sum to 9. So for
each wild-card game we check that our computed seeds for the home and away
teams add up to 9. Getting all three right in a conference means the full 1-7
ordering matches, and that test never consults a record, so it cannot quietly
agree with our own logic by construction.

Usage:
    python analysis/validate_seeds.py
    python analysis/validate_seeds.py --season 2023 --verbose
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass

import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from standings import (
    build_context,
    connect,
    load_games,
    load_teams,
    seed_conference,
)

SEED_PAIR_SUM = 9   # 2+7, 3+6, 4+5


@dataclass
class ActualField:
    conf: str
    top_seed: str | None
    division_winners: set[str]       # includes the #1 seed
    wild_cards: set[str]
    wc_pairs: list[tuple[str, str]]  # (home, away) per wild-card game


def actual_fields(
    conn: psycopg.Connection, season: int, conf_of: dict[str, str]
) -> dict[str, ActualField]:
    """Recover each conference's real playoff field from the bracket."""
    wc = conn.execute(
        """
        SELECT home_team, away_team FROM games
        WHERE season = %s AND game_type = 'WC' ORDER BY game_id
        """,
        (season,),
    ).fetchall()
    div = conn.execute(
        """
        SELECT home_team, away_team FROM games
        WHERE season = %s AND game_type = 'DIV' ORDER BY game_id
        """,
        (season,),
    ).fetchall()

    out: dict[str, ActualField] = {}
    for conf in ("AFC", "NFC"):
        pairs = [(h, a) for h, a in wc if conf_of.get(h) == conf]
        homes = {h for h, _ in pairs}
        aways = {a for _, a in pairs}
        # Everyone who appeared in the divisional round for this conference.
        div_teams = {
            t for h, a in div for t in (h, a) if conf_of.get(t) == conf
        }
        # The #1 seed is the one that got there without playing in round one.
        bye = div_teams - homes - aways
        top = next(iter(bye)) if len(bye) == 1 else None
        out[conf] = ActualField(
            conf=conf,
            top_seed=top,
            division_winners=homes | bye,
            wild_cards=aways,
            wc_pairs=pairs,
        )
    return out


@dataclass
class Comparison:
    season: int
    conf: str
    ok: bool
    computed: list[str]
    problems: list[str]


def compare(
    season: int,
    conf: str,
    computed,
    actual: ActualField,
) -> Comparison:
    problems: list[str] = []

    if actual.top_seed is None:
        problems.append("could not identify the real #1 seed from the bracket")
    elif computed.seeds[0] != actual.top_seed:
        problems.append(
            f"#1 seed: computed {computed.seeds[0]}, actual {actual.top_seed}"
        )

    comp_dw = set(computed.division_winners)
    if comp_dw != actual.division_winners:
        problems.append(
            f"division winners: computed {sorted(comp_dw)}, "
            f"actual {sorted(actual.division_winners)}"
        )

    comp_wc = set(computed.wild_cards)
    if comp_wc != actual.wild_cards:
        problems.append(
            f"wild cards: computed {sorted(comp_wc)}, "
            f"actual {sorted(actual.wild_cards)}"
        )

    # Ordering test: in every wild-card game the two seeds must sum to 9.
    for home, away in actual.wc_pairs:
        sh, sa = computed.seed_of(home), computed.seed_of(away)
        if sh is None or sa is None:
            problems.append(
                f"{away} @ {home}: one of them is not in our playoff field "
                f"(computed seeds {sa}, {sh})"
            )
        elif sh + sa != SEED_PAIR_SUM:
            problems.append(
                f"{away} @ {home}: computed seeds {sh} and {sa} sum to "
                f"{sh + sa}, not {SEED_PAIR_SUM} -- ordering is off"
            )

    return Comparison(season, conf, not problems, computed.seeds, problems)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", type=int, nargs="+",
                    default=[2022, 2023, 2024, 2025])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true",
                    help="show every tiebreak that was applied")
    args = ap.parse_args()

    results: list[Comparison] = []
    with connect() as conn:
        teams = load_teams(conn)
        conf_of = {a: t.conf for a, t in teams.items()}

        for season in args.seasons:
            games = load_games(conn, season)
            if not games or any(not g.played for g in games):
                print(f"{season}: regular season incomplete, skipping")
                continue
            ctx = build_context(games, teams)
            actual = actual_fields(conn, season, conf_of)

            print(f"\n=== {season} ===")
            for conf in ("AFC", "NFC"):
                rng = random.Random(args.seed)
                computed = seed_conference(ctx, teams, conf, rng)
                cmp_ = compare(season, conf, computed, actual[conf])
                results.append(cmp_)

                mark = "OK " if cmp_.ok else "XX "
                order = "  ".join(
                    f"{i}.{t}" for i, t in enumerate(computed.seeds, start=1)
                )
                print(f"  {mark}{conf}: {order}")
                for p in cmp_.problems:
                    print(f"      - {p}")
                if args.verbose and computed.decisions:
                    seen = set()
                    for d in computed.decisions:
                        key = (tuple(d.group), d.winner, d.step)
                        if key in seen:
                            continue
                        seen.add(key)
                        skip = (f"  [skipped: {', '.join(d.skipped)}]"
                                if d.skipped else "")
                        print(f"      tiebreak {'/'.join(d.group):<18} -> "
                              f"{d.winner:<4} by {d.step}{skip}")

    ok = sum(1 for r in results if r.ok)
    print(f"\n=== {ok}/{len(results)} conference-seasons match the real bracket "
          f"exactly ===")
    for r in results:
        if not r.ok:
            print(f"  mismatch: {r.season} {r.conf}")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
