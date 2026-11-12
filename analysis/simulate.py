"""Monte Carlo simulation of the rest of a season.

Each iteration plays every unplayed game as a weighted coin flip using the
probabilities from win_probability.py, adds the results to the records already
on the books, then seeds the playoffs. We record, per iteration:

  * who won each remaining game          -> winners matrix (n_sims x n_games)
  * whether the target team made the playoffs
  * whether it won its division

Those three are everything the impact calculation needs: conditioning the
playoff column on a game's winner column gives "MIN's odds if team X wins".

WHY THIS IS VECTORISED: the simulation runs on numpy arrays of shape
(n_sims, n_teams) rather than looping over Python objects, so 20,000 seasons
take well under a second. The standings module stays the readable reference
implementation for a single season; this is the fast path for many.

SIMPLIFICATIONS (all deliberate for v1):
  * Simulated games never end in ties. Real ties are rare (1 in 2026 so far)
    and they ARE counted in the starting records as half a win.
  * Seeding uses total wins rather than win percentage. That is equivalent
    here because every team finishes a 17-game season, which we assert.
  * Tiebreaks are random, matching standings.py. Implemented by adding a tiny
    random number (< 1e-6, far below the 0.5 granularity of a win) to each
    team's win total, so argmax/argsort break ties uniformly at random.
  * Playoff seeding only resolves the target team's conference. Under
    win-percentage tiebreaking, games between two teams of the other
    conference cannot affect MIN, so their measured impact is pure noise.
    Interconference games DO matter and are simulated.

Usage:
    python analysis/simulate.py --season 2026 --sims 20000
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np
import psycopg

# Allow running as "python analysis/simulate.py" from the project root as well
# as from inside analysis/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from standings import (
    DIVISION_WINNERS_PER_CONF,
    WILD_CARDS_PER_CONF,
    Team,
    compute_records,
    connect,
    load_games,
    load_teams,
)
from win_probability import GameProb, method_counts, remaining_game_probs

GAMES_PER_SEASON = 17
TIEBREAK_NOISE = 1e-6


@dataclass
class SimResult:
    season: int
    n_sims: int
    target: str
    games: list[GameProb]          # the remaining games, in column order
    home_wins: np.ndarray          # (n_sims, n_games) bool: did the home team win
    made_playoffs: np.ndarray      # (n_sims,) bool
    won_division: np.ndarray       # (n_sims,) bool
    base_wins: dict[str, float]    # win "points" already banked (ties = 0.5)

    @property
    def playoff_odds(self) -> float:
        return float(self.made_playoffs.mean())

    @property
    def division_odds(self) -> float:
        return float(self.won_division.mean())

    def standard_error(self) -> float:
        """Monte Carlo standard error on the playoff odds, in probability."""
        p = self.playoff_odds
        return float(np.sqrt(p * (1.0 - p) / self.n_sims))


def simulate(
    conn: psycopg.Connection,
    season: int,
    n_sims: int = 20_000,
    target: str = "MIN",
    seed: int = 20260101,
) -> SimResult:
    teams = load_teams(conn)
    if target not in teams:
        raise SystemExit(f"unknown team {target!r}")

    all_games = load_games(conn, season)
    remaining = remaining_game_probs(conn, season)

    # --- starting point: records already earned -----------------------------
    records = compute_records(all_games, teams)
    abbrs = sorted(teams)
    idx = {a: i for i, a in enumerate(abbrs)}
    n_teams = len(abbrs)

    # A tie is half a win, which is why this is a float.
    base = np.array(
        [records[a].wins + 0.5 * records[a].ties for a in abbrs], dtype=np.float64
    )

    # Seeding by total wins is only valid if everyone plays the same number of
    # games. Check it rather than assume it.
    scheduled = np.zeros(n_teams, dtype=np.int32)
    for g in all_games:
        if g.home in idx and g.away in idx:
            scheduled[idx[g.home]] += 1
            scheduled[idx[g.away]] += 1
    if not np.all(scheduled == GAMES_PER_SEASON):
        odd = {abbrs[i]: int(scheduled[i]) for i in np.where(scheduled != GAMES_PER_SEASON)[0]}
        raise SystemExit(
            f"seeding assumes every team plays {GAMES_PER_SEASON} games; got {odd}"
        )

    # --- play out the remaining games ---------------------------------------
    rng = np.random.default_rng(seed)
    n_games = len(remaining)
    home_idx = np.array([idx[g.home] for g in remaining], dtype=np.int32)
    away_idx = np.array([idx[g.away] for g in remaining], dtype=np.int32)
    p_home = np.array([g.p_home for g in remaining], dtype=np.float64)

    # One uniform draw per (simulation, game). Home wins when the draw lands
    # under its win probability.
    draws = rng.random((n_sims, n_games))
    home_wins = draws < p_home  # broadcasts p_home across rows

    wins = np.tile(base, (n_sims, 1))
    for j in range(n_games):
        hw = home_wins[:, j]
        wins[hw, home_idx[j]] += 1.0
        wins[~hw, away_idx[j]] += 1.0

    # --- seed the target's conference ---------------------------------------
    # Tiny noise = uniformly random tiebreaks (see module docstring).
    score = wins + rng.random((n_sims, n_teams)) * TIEBREAK_NOISE

    conf = teams[target].conf
    conf_divisions: dict[str, list[int]] = {}
    for a, t in teams.items():
        if t.conf == conf:
            conf_divisions.setdefault(t.division, []).append(idx[a])
    if len(conf_divisions) != DIVISION_WINNERS_PER_CONF:
        raise SystemExit(f"{conf}: expected 4 divisions, found {len(conf_divisions)}")

    target_div = teams[target].division
    target_i = idx[target]

    # Division winners: best noisy score inside each division.
    is_div_winner = np.zeros((n_sims, n_teams), dtype=bool)
    for cols in conf_divisions.values():
        cols_arr = np.array(cols, dtype=np.int32)
        best = cols_arr[np.argmax(score[:, cols_arr], axis=1)]
        is_div_winner[np.arange(n_sims), best] = True

    won_division = is_div_winner[:, target_i].copy()

    # Wild cards: the best non-winners in the conference. Instead of a full
    # sort we just count how many non-winners outrank the target -- fewer than
    # three means it holds a wild-card slot.
    conf_cols = np.array(
        [idx[a] for a, t in teams.items() if t.conf == conf], dtype=np.int32
    )
    conf_score = score[:, conf_cols]
    conf_is_winner = is_div_winner[:, conf_cols]
    # Division winners are out of the wild-card pool.
    wc_score = np.where(conf_is_winner, -np.inf, conf_score)

    target_pos = int(np.where(conf_cols == target_i)[0][0])
    target_wc = wc_score[:, target_pos : target_pos + 1]
    better = (wc_score > target_wc).sum(axis=1)
    made_wild_card = (~won_division) & (better < WILD_CARDS_PER_CONF)

    made_playoffs = won_division | made_wild_card

    assert target_div in conf_divisions, f"{target} division {target_div} not in {conf}"

    return SimResult(
        season=season,
        n_sims=n_sims,
        target=target,
        games=remaining,
        home_wins=home_wins,
        made_playoffs=made_playoffs,
        won_division=won_division,
        base_wins={a: float(base[idx[a]]) for a in abbrs},
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--sims", type=int, default=20_000)
    ap.add_argument("--team", default="MIN")
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()

    with connect() as conn:
        res = simulate(conn, args.season, args.sims, args.team, args.seed)
        counts = method_counts(res.games)

    print(f"=== {args.season}: {res.n_sims:,} simulations ===")
    print(f"  remaining games : {len(res.games)}")
    print(f"  pricing         : " + ", ".join(f"{m}={c}" for m, c in counts.items()))
    print(f"\n  {res.target} playoff odds  : {res.playoff_odds * 100:5.1f}% "
          f"(+/- {res.standard_error() * 100:.2f} pp)")
    print(f"  {res.target} division odds : {res.division_odds * 100:5.1f}%")

    wins_now = res.base_wins[res.target]
    print(f"\n  {res.target} banked wins: {wins_now:g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
