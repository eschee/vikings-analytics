"""Backtest the SEASON odds: are our playoff/division/#1-seed numbers honest?

backtest.py checks single games. This checks what the site actually shows:
"74% to make the playoffs". If the model is honest, teams we call 70% should
make it about 70% of the time, across many teams and seasons.

THE TEST

For each finished season (2023-2025) and each cutoff week (6, 10, 14), the
season is rewound to the Monday before that week (simulate's `as_of_week`):

  * results before the cutoff count; later results are hidden
  * betting lines exist for the cutoff week and the next one only -- the two
    weeks of lines a production refresh typically has -- and the ratings are
    fitted from those lines alone

Then the rest of the season is simulated and every team's predicted odds are
compared with what really happened, which comes from seeding the real
results with the same tiebreaker code validated against the real brackets.

VARIANTS (same seed, so differences are the model, not luck)

  lines+coin  lines for two weeks, coin flips after: the pre-ratings model,
              a floor any real model must beat
  hl2 / hl4   ratings weighted toward recent lines (half-life 2 or 4 weeks)
  hl6         PRODUCTION: half-life 6 weeks, with rating jitter
  hl6-nojit   production without the per-team rating uncertainty
  hl10        ratings that move more slowly than production

METRICS

  * Brier score: mean squared error of a probability against the 0/1 outcome.
    Lower is better. Always guessing the league base rate scores about
    p(1-p): ~0.24 for playoffs (14 of 32 make it).
  * Log loss: punishes confident misses hard -- e.g. "1%" for a team that
    then makes the playoffs.
  * Calibration: teams bucketed by predicted probability; in each bucket the
    share that actually made it should sit close to the average prediction.

CAVEATS

  * nflverse stores CLOSING lines. A real refresh sees the next week's line
    days before kickoff, slightly less informed. That makes the backtest a
    little flattering for the two lined weeks; it does not affect weeks 3+.
  * 3 seasons x 3 cutoffs x 32 teams = 288 forecasts per goal, and teams in
    one season are not independent. Differences of a few thousandths in Brier
    are noise; the bootstrap interval says which are not.
  * 2022 is left out. Buffalo-Cincinnati was cancelled after Damar Hamlin's
    cardiac arrest, so those two teams played 16 games, and the simulator
    seeds by total wins -- valid only when every team plays 17, which it
    asserts. Seeding by win percentage would lift that; not worth it for one
    season.
  * No market futures are included: we have no historical futures prices.

Usage:
    python analysis/season_backtest.py                  # everything, 10k sims
    python analysis/season_backtest.py --sims 2000      # quick look
    python analysis/season_backtest.py --out results.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
import time
from dataclasses import dataclass

import numpy as np

from simulate import simulate
from standings import build_context, load_games, load_teams, seed_conference
from win_probability import connect

SEASONS = [2023, 2024, 2025]   # 2022: see CAVEATS
CUTOFFS = [6, 10, 14]
GOALS = ("playoffs", "division", "top_seed")

# name -> keyword arguments for simulate()
VARIANTS: dict[str, dict] = {
    "lines+coin": {"use_ratings": False},
    "hl2": {"half_life": 2.0},
    "hl4": {"half_life": 4.0},
    "hl6": {},                                   # production
    "hl6-nojit": {"jitter_sd": 0.0},
    "hl10": {"half_life": 10.0},
}
PRODUCTION = "hl6"

# Log loss of a probability of exactly 0 or 1 is infinite; clip like any
# forecaster scored this way would have to.
EPS = 1e-3


@dataclass
class Forecast:
    variant: str
    season: int
    cutoff: int
    team: str
    goal: str
    p: float
    actual: int


def actual_outcomes(conn, season: int, teams) -> dict[str, dict[str, int]]:
    """What really happened: playoffs / division / #1 seed for every team."""
    games = load_games(conn, season)
    unplayed = [g for g in games if not g.played]
    if unplayed:
        raise SystemExit(
            f"{season}: {len(unplayed)} regular-season games have no result"
        )
    ctx = build_context(games, teams)
    out = {a: {"playoffs": 0, "division": 0, "top_seed": 0} for a in teams}
    for conf in ("AFC", "NFC"):
        seeding = seed_conference(ctx, teams, conf, random.Random(0))
        for abbr in seeding.seeds:
            out[abbr]["playoffs"] = 1
        for abbr in seeding.division_winners:
            out[abbr]["division"] = 1
        out[seeding.seeds[0]]["top_seed"] = 1
    return out


def brier(fs: list[Forecast]) -> float:
    return float(np.mean([(f.p - f.actual) ** 2 for f in fs]))


def log_loss(fs: list[Forecast]) -> float:
    return float(
        np.mean(
            [
                -math.log(min(max(f.p, EPS), 1 - EPS))
                if f.actual
                else -math.log(1 - min(max(f.p, EPS), 1 - EPS))
                for f in fs
            ]
        )
    )


def bootstrap_diff(a: list[Forecast], b: list[Forecast], n: int = 2000):
    """95% interval for Brier(a) - Brier(b), resampling whole season-cutoffs.

    Teams in one season-cutoff share a schedule and outcomes, so they are
    resampled together rather than as 384 independent points.
    """
    key = lambda f: (f.season, f.cutoff, f.team, f.goal)  # noqa: E731
    bm = {key(f): f for f in b}
    pairs: dict[tuple[int, int], list[float]] = {}
    for f in a:
        g = bm[key(f)]
        pairs.setdefault((f.season, f.cutoff), []).append(
            (f.p - f.actual) ** 2 - (g.p - g.actual) ** 2
        )
    groups = list(pairs.values())
    rng = np.random.default_rng(0)
    stats = []
    for _ in range(n):
        pick = rng.integers(0, len(groups), len(groups))
        stats.append(np.mean(np.concatenate([groups[i] for i in pick])))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def calibration(fs: list[Forecast]) -> list[tuple[str, int, float, float]]:
    edges = [0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0001]
    rows = []
    for lo, hi in zip(edges, edges[1:]):
        bucket = [f for f in fs if lo <= f.p < hi]
        if bucket:
            rows.append(
                (
                    f"{lo:.0%}-{min(hi, 1):.0%}",
                    len(bucket),
                    float(np.mean([f.p for f in bucket])),
                    float(np.mean([f.actual for f in bucket])),
                )
            )
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sims", type=int, default=10_000)
    ap.add_argument("--seasons", type=int, nargs="+", default=SEASONS)
    ap.add_argument("--cutoffs", type=int, nargs="+", default=CUTOFFS)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--out", help="write every forecast to this CSV")
    args = ap.parse_args()

    forecasts: list[Forecast] = []
    started = time.time()
    with connect() as conn:
        teams = load_teams(conn)
        for season in args.seasons:
            actual = actual_outcomes(conn, season, teams)
            for cutoff in args.cutoffs:
                for name in args.variants:
                    res = simulate(
                        conn,
                        season,
                        n_sims=args.sims,
                        seed=season * 100 + cutoff,   # same draws per variant
                        as_of_week=cutoff,
                        **VARIANTS[name],
                    )
                    for team, col in res.team_index.items():
                        for goal, mat in (
                            ("playoffs", res.team_made_playoffs),
                            ("division", res.team_won_division),
                            ("top_seed", res.team_won_top_seed),
                        ):
                            forecasts.append(
                                Forecast(
                                    name, season, cutoff, team, goal,
                                    float(mat[:, col].mean()),
                                    actual[team][goal],
                                )
                            )
                print(
                    f"  {season} week {cutoff:>2}: done "
                    f"({time.time() - started:.0f}s)",
                    file=sys.stderr,
                )

    if args.out:
        with open(args.out, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["variant", "season", "cutoff", "team", "goal", "p", "actual"])
            for f in forecasts:
                w.writerow([f.variant, f.season, f.cutoff, f.team, f.goal,
                            f"{f.p:.4f}", f.actual])

    def sel(variant=None, goal=None, cutoff=None):
        return [
            f for f in forecasts
            if (variant is None or f.variant == variant)
            and (goal is None or f.goal == goal)
            and (cutoff is None or f.cutoff == cutoff)
        ]

    n_cases = len(args.seasons) * len(args.cutoffs)
    print(f"\n=== Season-odds backtest: {args.seasons}, cutoffs {args.cutoffs}, "
          f"{args.sims:,} sims, {n_cases * 32} forecasts per goal ===")

    print("\nBrier score (lower is better)  [log loss for playoffs]")
    print(f"  {'variant':<11}" + "".join(f"{g:>11}" for g in GOALS) + f"{'logloss':>10}")
    for name in args.variants:
        row = "".join(f"{brier(sel(name, g)):>11.4f}" for g in GOALS)
        print(f"  {name:<11}{row}{log_loss(sel(name, 'playoffs')):>10.4f}")

    if PRODUCTION in args.variants:
        print(f"\nDifference vs production ({PRODUCTION}), playoffs Brier, "
              "95% bootstrap interval (negative = better than production)")
        prod = sel(PRODUCTION, "playoffs")
        for name in args.variants:
            if name == PRODUCTION:
                continue
            other = sel(name, "playoffs")
            d = brier(other) - brier(prod)
            lo, hi = bootstrap_diff(other, prod)
            flag = "  <- real" if (hi < 0 or lo > 0) else ""
            print(f"  {name:<11}{d:+.4f}  [{lo:+.4f}, {hi:+.4f}]{flag}")

        print(f"\nProduction ({PRODUCTION}) playoffs Brier by cutoff week")
        for c in args.cutoffs:
            print(f"  week {c:>2}: {brier(sel(PRODUCTION, 'playoffs', c)):.4f}")

        for goal in GOALS:
            print(f"\nCalibration, production, {goal}")
            print(f"  {'predicted':<10}{'teams':>6}{'avg forecast':>14}{'actually did':>14}")
            for label, n, mp, ma in calibration(sel(PRODUCTION, goal)):
                print(f"  {label:<10}{n:>6}{mp:>14.1%}{ma:>14.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
