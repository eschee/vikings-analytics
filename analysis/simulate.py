"""Monte Carlo simulation of the rest of a season.

Each iteration plays every unplayed game, adds the results to the records
already on the books, then seeds the playoffs. We record, per iteration:

  * who won each remaining game          -> winners matrix (n_sims x n_games)
  * whether the target team made the playoffs
  * whether it won its division
  * whether it took the conference's #1 seed
  * what draft pick it would hold

Those are everything the impact calculation needs: conditioning any of the
outcome columns on a game's winner column gives "MIN's odds if team X wins".

HOW A GAME IS PLAYED

Two kinds of games, handled differently on purpose:

  * Market-priced games have a real moneyline. Their probability is known, so
    we draw a uniform and compare: home wins if draw < p_home.
  * Ratings-priced games have no line, so their spread is predicted. Instead of
    converting to a probability and drawing, we simulate the MARGIN directly:
        margin = predicted_spread + rating_jitter + N(0, SPREAD_SIGMA)
    and the home team wins when the margin is positive. This is mathematically
    identical to drawing against Phi(margin_mean / sigma) but lets the rating
    jitter enter naturally, and needs no vectorised normal CDF.

RATING UNCERTAINTY (why the jitter exists)

A rating fitted today is wrong by some amount, and it is wrong the SAME way in
every one of that team's remaining games. That correlation is the whole point:
if the model has underrated Detroit, Detroit beats its projection all season,
not in one game. Independent per-game noise cannot produce that, and a model
without it is badly overconfident about a team's final record -- too few 13-win
and 4-win seasons, too many 9-8s.

So each iteration draws one rating offset per team, N(0, JITTER_SD), held fixed
across that iteration's games. The size is derived rather than picked:

    per-game noise     sigma = SPREAD_SIGMA = 12.38  (independent)
    per-team jitter    tau   = RATINGS_SPREAD_RMSE / sqrt(2) = 3.21 (correlated)

Two independent sources, so the variance a single game sees is
sqrt(12.38^2 + 2*3.21^2) = 13.19 -- which is exactly the RATINGS_SIGMA the
backtest calibrated. The jitter therefore redistributes uncertainty that was
already measured, from independent to correlated, without inflating the total.
As a cross-check, refitting 2025's ratings at week 8 versus the full season
moves them by 1.85 points, the same order of magnitude.

OTHER SIMPLIFICATIONS (deliberate for v1):
  * Simulated games never end in ties. Real ties already banked count as half
    a win.
  * Seeding uses total wins rather than win percentage, valid because every
    team finishes 17 games, which we assert.
  * Tiebreaks are random, matching standings.py, implemented as noise below
    1e-6 on each win total.
  * Draft order is by record only: pick 1 to the worst record. The real order
    sends playoff teams to picks 19-32 ordered by elimination round, which this
    ignores.
  * Only the target's conference is seeded. Under win-percentage tiebreakers a
    game between two teams of the other conference cannot affect MIN;
    interconference games can and are simulated.

Usage:
    python analysis/simulate.py --season 2026 --sims 20000
    python analysis/simulate.py --no-ratings      # old coin-flip behaviour
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass

import numpy as np
import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from standings import (
    DIVISION_WINNERS_PER_CONF,
    WILD_CARDS_PER_CONF,
    compute_records,
    connect,
    load_games,
    load_teams,
)
from win_probability import (
    RATINGS_SPREAD_RMSE,
    SPREAD_SIGMA,
    GameProb,
    method_counts,
    remaining_game_probs,
)

GAMES_PER_SEASON = 17
TIEBREAK_NOISE = 1e-6
# Correlated per-team rating error. See the module docstring for the derivation.
JITTER_SD = RATINGS_SPREAD_RMSE / math.sqrt(2.0)

# The four goals a fan might root for. Each maps to a column on SimResult and a
# direction: True means higher is better.
GOALS = {
    "playoffs": ("made_playoffs", True),
    "division": ("won_division", True),
    "top_seed": ("won_top_seed", True),
    "draft": ("draft_pick", False),   # pick 1 is the best outcome
}


@dataclass
class SimResult:
    season: int
    n_sims: int
    target: str
    games: list[GameProb]          # the remaining games, in column order
    home_wins: np.ndarray          # (n_sims, n_games) bool
    made_playoffs: np.ndarray      # (n_sims,) bool
    won_division: np.ndarray       # (n_sims,) bool
    won_top_seed: np.ndarray       # (n_sims,) bool
    draft_pick: np.ndarray         # (n_sims,) int, 1 = first overall
    base_wins: dict[str, float]
    jitter_sd: float
    used_ratings: bool

    @property
    def playoff_odds(self) -> float:
        return float(self.made_playoffs.mean())

    @property
    def division_odds(self) -> float:
        return float(self.won_division.mean())

    @property
    def top_seed_odds(self) -> float:
        return float(self.won_top_seed.mean())

    @property
    def mean_draft_pick(self) -> float:
        return float(self.draft_pick.mean())

    def outcome(self, goal: str) -> np.ndarray:
        return getattr(self, GOALS[goal][0])

    def standard_error(self) -> float:
        p = self.playoff_odds
        return float(np.sqrt(p * (1.0 - p) / self.n_sims))


def simulate(
    conn: psycopg.Connection,
    season: int,
    n_sims: int = 20_000,
    target: str = "MIN",
    seed: int = 20260101,
    use_ratings: bool = True,
    jitter_sd: float | None = None,
) -> SimResult:
    teams = load_teams(conn)
    if target not in teams:
        raise SystemExit(f"unknown team {target!r}")

    fit = None
    if use_ratings:
        from ratings import fit_for_season

        fit = fit_for_season(conn, season)
    if jitter_sd is None:
        jitter_sd = JITTER_SD if use_ratings else 0.0

    all_games = load_games(conn, season)
    remaining = remaining_game_probs(conn, season, fit=fit)

    # --- starting point: records already earned -----------------------------
    records = compute_records(all_games, teams)
    abbrs = sorted(teams)
    idx = {a: i for i, a in enumerate(abbrs)}
    n_teams = len(abbrs)

    base = np.array(
        [records[a].wins + 0.5 * records[a].ties for a in abbrs], dtype=np.float64
    )

    scheduled = np.zeros(n_teams, dtype=np.int32)
    for g in all_games:
        if g.home in idx and g.away in idx:
            scheduled[idx[g.home]] += 1
            scheduled[idx[g.away]] += 1
    if not np.all(scheduled == GAMES_PER_SEASON):
        odd = {
            abbrs[i]: int(scheduled[i])
            for i in np.where(scheduled != GAMES_PER_SEASON)[0]
        }
        raise SystemExit(
            f"seeding assumes every team plays {GAMES_PER_SEASON} games; got {odd}"
        )

    # --- play out the remaining games ---------------------------------------
    rng = np.random.default_rng(seed)
    n_games = len(remaining)
    home_idx = np.array([idx[g.home] for g in remaining], dtype=np.int32)
    away_idx = np.array([idx[g.away] for g in remaining], dtype=np.int32)
    p_home = np.array([g.p_home for g in remaining], dtype=np.float64)
    from_ratings = np.array([g.from_ratings for g in remaining], dtype=bool)
    rating_spread = np.array(
        [g.spread if (g.from_ratings and g.spread is not None) else 0.0
         for g in remaining],
        dtype=np.float64,
    )

    home_wins = np.zeros((n_sims, n_games), dtype=bool)

    # Market-priced games: the probability is known, so draw against it.
    market_cols = np.where(~from_ratings)[0]
    if market_cols.size:
        draws = rng.random((n_sims, market_cols.size))
        home_wins[:, market_cols] = draws < p_home[market_cols]

    # Ratings-priced games: simulate the margin, with one rating offset per
    # team per iteration shared across all that team's games.
    rating_cols = np.where(from_ratings)[0]
    if rating_cols.size:
        if jitter_sd > 0:
            jitter = rng.normal(0.0, jitter_sd, size=(n_sims, n_teams))
        else:
            jitter = np.zeros((n_sims, n_teams))
        h = home_idx[rating_cols]
        a = away_idx[rating_cols]
        margin = (
            rating_spread[rating_cols]           # predicted spread
            + jitter[:, h] - jitter[:, a]        # correlated rating error
            + rng.normal(0.0, SPREAD_SIGMA, size=(n_sims, rating_cols.size))
        )
        home_wins[:, rating_cols] = margin > 0.0

    wins = np.tile(base, (n_sims, 1))
    for j in range(n_games):
        hw = home_wins[:, j]
        wins[hw, home_idx[j]] += 1.0
        wins[~hw, away_idx[j]] += 1.0

    # --- seed the target's conference ---------------------------------------
    score = wins + rng.random((n_sims, n_teams)) * TIEBREAK_NOISE

    conf = teams[target].conf
    conf_divisions: dict[str, list[int]] = {}
    for a, t in teams.items():
        if t.conf == conf:
            conf_divisions.setdefault(t.division, []).append(idx[a])
    if len(conf_divisions) != DIVISION_WINNERS_PER_CONF:
        raise SystemExit(f"{conf}: expected 4 divisions, found {len(conf_divisions)}")

    target_i = idx[target]

    is_div_winner = np.zeros((n_sims, n_teams), dtype=bool)
    for cols in conf_divisions.values():
        cols_arr = np.array(cols, dtype=np.int32)
        best = cols_arr[np.argmax(score[:, cols_arr], axis=1)]
        is_div_winner[np.arange(n_sims), best] = True

    won_division = is_div_winner[:, target_i].copy()

    conf_cols = np.array(
        [idx[a] for a, t in teams.items() if t.conf == conf], dtype=np.int32
    )
    conf_score = score[:, conf_cols]
    conf_is_winner = is_div_winner[:, conf_cols]
    wc_score = np.where(conf_is_winner, -np.inf, conf_score)

    target_pos = int(np.where(conf_cols == target_i)[0][0])
    better = (wc_score > wc_score[:, target_pos : target_pos + 1]).sum(axis=1)
    made_wild_card = (~won_division) & (better < WILD_CARDS_PER_CONF)
    made_playoffs = won_division | made_wild_card

    # #1 seed: the best record among this conference's four division winners.
    winner_score = np.where(conf_is_winner, conf_score, -np.inf)
    top_team = conf_cols[np.argmax(winner_score, axis=1)]
    won_top_seed = top_team == target_i

    # Draft pick by record alone: pick 1 goes to the worst record, so the
    # target's slot is one more than the number of teams finishing below it.
    draft_pick = 1 + (score < score[:, target_i : target_i + 1]).sum(axis=1)

    return SimResult(
        season=season,
        n_sims=n_sims,
        target=target,
        games=remaining,
        home_wins=home_wins,
        made_playoffs=made_playoffs,
        won_division=won_division,
        won_top_seed=won_top_seed,
        draft_pick=draft_pick.astype(np.int16),
        base_wins={a: float(base[idx[a]]) for a in abbrs},
        jitter_sd=jitter_sd,
        used_ratings=use_ratings,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--sims", type=int, default=20_000)
    ap.add_argument("--team", default="MIN")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--no-ratings", action="store_true",
                    help="coin-flip unpriced games (the old v1 behaviour)")
    ap.add_argument("--jitter-sd", type=float,
                    help=f"rating jitter in points (default {JITTER_SD:.2f})")
    args = ap.parse_args()

    with connect() as conn:
        res = simulate(
            conn, args.season, args.sims, args.team, args.seed,
            use_ratings=not args.no_ratings, jitter_sd=args.jitter_sd,
        )
        counts = method_counts(res.games)

    print(f"=== {args.season}: {res.n_sims:,} simulations ===")
    print(f"  remaining games : {len(res.games)}")
    print(f"  pricing         : "
          + ", ".join(f"{m}={c}" for m, c in counts.items() if c))
    print(f"  rating jitter   : {res.jitter_sd:.2f} points"
          + ("" if res.used_ratings else " (ratings off)"))
    print(f"\n  {res.target} playoff odds   : {res.playoff_odds * 100:5.1f}% "
          f"(+/- {res.standard_error() * 100:.2f} pp)")
    print(f"  {res.target} division odds  : {res.division_odds * 100:5.1f}%")
    print(f"  {res.target} #1 seed odds   : {res.top_seed_odds * 100:5.1f}%")
    print(f"  {res.target} mean draft pick: {res.mean_draft_pick:5.1f}")

    wins = res.base_wins[res.target]
    print(f"\n  {res.target} banked wins: {wins:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
