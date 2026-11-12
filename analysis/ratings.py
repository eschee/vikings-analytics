"""Market-implied team ratings, fitted from betting spreads.

THE METHOD

A point spread is the market's estimate of a game's margin. If each team has a
single number measuring its strength in points, the spread for a game should be
roughly:

    spread ~= home_rating - away_rating + home_field_advantage

Every game with a spread gives us one such equation. With 163 priced 2026 games
and 33 unknowns (32 ratings plus one home-field term), that is a heavily
over-determined linear system, so we solve it by least squares: find the ratings
that collectively miss the observed spreads by as little as possible. The result
is the market's implicit power ranking, extracted from lines rather than scores.

Working from spreads rather than from game results is deliberate. A spread is a
forecast made by people with money at stake, already adjusted for injuries,
rest and weather; a final score is one noisy sample of what happened. Scores
would also reward blowouts, which the market does not treat as proportionally
meaningful.

RECENCY WEIGHTING

A Week 1 line reflects a team that may no longer exist -- different starters,
different form. So each game is weighted by exponential decay on its age:

    weight = 0.5 ** (weeks_old / half_life)

With the default six-week half-life, a game six weeks old counts half as much
as this week's, twelve weeks old a quarter, and so on. Unplayed games with a
line (weeks 10-11 here) are the freshest information available and get full
weight. HALF_LIFE_WEEKS was chosen by backtest, not by taste -- see
analysis/backtest.py.

IDENTIFIABILITY AND RIDGE

Only rating *differences* are identified: adding 5 to every team changes no
prediction, so the system is singular without a constraint. A small ridge
penalty on the ratings resolves it by preferring the smallest set of ratings
that fits, which also shrinks weakly-evidenced teams toward average. The
home-field term is deliberately left unpenalised -- there is no reason to pull
it toward zero. Ratings are then re-centred to mean zero so each reads directly
as "points better than a league-average team".

Usage:
    python analysis/ratings.py --season 2026
    python analysis/ratings.py --season 2025 --through-week 8
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np
import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from standings import connect, load_teams

# Chosen by backtest over the 2025 season; see analysis/backtest.py.
HALF_LIFE_WEEKS = 6.0
# Ridge strength. Small enough not to distort a well-observed team, large
# enough to make the system solvable and tame a barely-observed one.
RIDGE_LAMBDA = 2.0


@dataclass
class RatingFit:
    ratings: dict[str, float]      # points better than league average
    hfa: float                     # home-field advantage, in points
    n_games: int
    half_life: float
    ridge: float
    ref_week: int
    residual_sigma: float          # how well the fit reproduces the spreads

    def predict_spread(self, home: str, away: str) -> float:
        """The spread this fit implies: positive favours the home team."""
        return self.ratings[home] - self.ratings[away] + self.hfa

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.ratings.items(), key=lambda kv: -kv[1])


def load_spread_games(
    conn: psycopg.Connection, season: int, through_week: int | None = None
) -> list[tuple[int, str, str, float]]:
    """(week, home, away, spread_line) for priced regular-season games.

    Includes games that have not been played: an unplayed game with a line is
    the most current read on both teams available.
    """
    sql = """
        SELECT week, home_team, away_team, spread_line
        FROM games
        WHERE season = %s AND game_type = 'REG' AND spread_line IS NOT NULL
    """
    params: list = [season]
    if through_week is not None:
        sql += " AND week <= %s"
        params.append(through_week)
    sql += " ORDER BY week, game_id"
    return [
        (int(w), h, a, float(s))
        for w, h, a, s in conn.execute(sql, params).fetchall()
    ]


def fit_ratings(
    games: list[tuple[int, str, str, float]],
    team_abbrs: list[str],
    ref_week: int | None = None,
    half_life: float = HALF_LIFE_WEEKS,
    ridge: float = RIDGE_LAMBDA,
) -> RatingFit:
    """Weighted ridge least squares for ratings + home-field advantage."""
    if not games:
        raise SystemExit("no priced games to fit ratings from")

    idx = {a: i for i, a in enumerate(team_abbrs)}
    n_teams = len(team_abbrs)
    n_params = n_teams + 1          # ratings, then HFA
    hfa_col = n_teams

    if ref_week is None:
        ref_week = max(w for w, _, _, _ in games)

    X = np.zeros((len(games), n_params), dtype=np.float64)
    y = np.zeros(len(games), dtype=np.float64)
    w = np.zeros(len(games), dtype=np.float64)

    for i, (week, home, away, spread) in enumerate(games):
        if home not in idx or away not in idx:
            continue
        X[i, idx[home]] = 1.0
        X[i, idx[away]] = -1.0
        X[i, hfa_col] = 1.0
        y[i] = spread
        # Future games are current information, so they are never discounted.
        weeks_old = max(0, ref_week - week)
        w[i] = 0.5 ** (weeks_old / half_life)

    # Normal equations with a ridge penalty on ratings only.
    W = X * w[:, None]
    A = X.T @ W
    b = W.T @ y
    penalty = np.eye(n_params) * ridge
    penalty[hfa_col, hfa_col] = 0.0     # never shrink home-field advantage
    beta = np.linalg.solve(A + penalty, b)

    ratings_arr = beta[:n_teams]
    hfa = float(beta[hfa_col])
    # Re-centre: only differences matter, so this makes ratings readable as
    # "points better than average" without changing any prediction.
    ratings_arr = ratings_arr - ratings_arr.mean()
    ratings = {a: float(ratings_arr[idx[a]]) for a in team_abbrs}

    pred = X[:, :n_teams] @ ratings_arr + hfa
    resid = y - pred
    # Weighted residual spread: how closely the ratings reproduce the lines.
    sigma = float(np.sqrt(np.average(resid**2, weights=w)))

    return RatingFit(
        ratings=ratings,
        hfa=hfa,
        n_games=len(games),
        half_life=half_life,
        ridge=ridge,
        ref_week=ref_week,
        residual_sigma=sigma,
    )


def fit_for_season(
    conn: psycopg.Connection,
    season: int,
    through_week: int | None = None,
    half_life: float = HALF_LIFE_WEEKS,
    ridge: float = RIDGE_LAMBDA,
    ref_week: int | None = None,
) -> RatingFit:
    teams = load_teams(conn)
    games = load_spread_games(conn, season, through_week)
    return fit_ratings(games, sorted(teams), ref_week, half_life, ridge)


def rating_drift(
    conn: psycopg.Connection, season: int, split_week: int = 8
) -> tuple[float, int]:
    """How far mid-season ratings end up from full-season ratings.

    This is the empirical basis for the rating jitter in the simulator: it
    measures how wrong a rating fitted today turns out to be by season's end,
    which is exactly the uncertainty the simulation should carry. Returns
    (standard deviation in points, number of teams).
    """
    early = fit_for_season(conn, season, through_week=split_week)
    final = fit_for_season(conn, season, through_week=None)
    diffs = [final.ratings[t] - early.ratings[t] for t in early.ratings]
    arr = np.array(diffs)
    return float(arr.std(ddof=1)), len(diffs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--through-week", type=int)
    ap.add_argument("--half-life", type=float, default=HALF_LIFE_WEEKS)
    ap.add_argument("--ridge", type=float, default=RIDGE_LAMBDA)
    ap.add_argument("--drift", action="store_true", help="measure rating drift")
    args = ap.parse_args()

    with connect() as conn:
        if args.drift:
            sd, n = rating_drift(conn, args.season)
            print(f"{args.season}: ratings fitted through week 8 vs full season")
            print(f"  drift standard deviation: {sd:.2f} points across {n} teams")
            return 0

        fit = fit_for_season(
            conn, args.season, args.through_week, args.half_life, args.ridge
        )

    print(f"=== {args.season} market-implied ratings ===")
    print(f"  fitted on {fit.n_games} priced games"
          + (f" through week {args.through_week}" if args.through_week else ""))
    print(f"  half-life {fit.half_life:g} weeks, ridge {fit.ridge:g}, "
          f"reference week {fit.ref_week}")
    print(f"  home-field advantage: {fit.hfa:+.2f} points")
    print(f"  residual sigma vs the lines: {fit.residual_sigma:.2f} points")
    print(f"\n  {'rank':>4}  {'team':<5} {'rating':>7}")
    print("  " + "-" * 22)
    for rank, (team, r) in enumerate(fit.ranked(), start=1):
        print(f"  {rank:>4}  {team:<5} {r:>+7.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
