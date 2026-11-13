"""Turn one simulation into per-team, per-game, per-goal impact rows.

A single run gives every team's numbers, so we compute the whole grid:
32 teams x every remaining game x 4 goals. For 2026 at week 10 that is
32 x 136 x 4 = 17,408 rows, which is cheap to store and means the website
never has to re-run anything to answer "what should a Bears fan want?".

THE MATH, briefly: for each game we split the simulated seasons by who won it
and compare the two halves. The difference in a team's goal between those
halves is the impact. Because every team's outcome is a column of the same
matrix, one split answers the question for all 32 teams at once -- which is why
the whole grid costs barely more than a single team's row.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import (
    GOALS,
    MIN_NOISE_FLOOR,
    MUST_WIN_THRESHOLD,
    ROOT_HARD_THRESHOLD,
    TIER_A_LITTLE,
    TIER_DOESNT_MATTER,
    TIER_MUST_WIN,
    TIER_ROOT_HARD,
)
from .reasons import reason_code

# Direction per goal: True when a higher number is the better outcome. The
# draft is inverted -- pick 1 is the prize, so a LOWER number is better.
HIGHER_IS_BETTER = {
    "playoffs": True,
    "division": True,
    "top_seed": True,
    "draft": False,
}
# Probability goals are reported in percentage points; the draft in picks.
GOAL_SCALE = {"playoffs": 100.0, "division": 100.0, "top_seed": 100.0,
              "draft": 1.0}


@dataclass
class ImpactRow:
    game_id: str
    team: str
    goal: str
    root_for: str
    impact_pts: float
    root_for_win_pct: float
    tier: str
    reason_code: str


@dataclass
class TeamOdds:
    team: str
    playoff_pct: float
    division_pct: float
    top_seed_pct: float
    avg_seed: float | None


def team_odds(res) -> list[TeamOdds]:
    """Season odds for all 32 teams from one run."""
    if not res.has_all_teams:
        raise RuntimeError("per-team odds need the real-tiebreaker path")
    out = []
    for team, col in sorted(res.team_index.items()):
        made = res.team_made_playoffs[:, col]
        seeds = res.team_seed[:, col]
        # Average seed only over the iterations where they actually got in.
        # Averaging zeros for the misses would invent a "#0 seed".
        got_in = seeds[made]
        out.append(
            TeamOdds(
                team=team,
                playoff_pct=float(made.mean()) * 100.0,
                division_pct=float(res.team_won_division[:, col].mean()) * 100.0,
                top_seed_pct=float(res.team_won_top_seed[:, col].mean()) * 100.0,
                avg_seed=float(got_in.mean()) if got_in.size else None,
            )
        )
    return out


def _goal_matrix(res, goal: str) -> np.ndarray:
    """(n_sims, 32) outcome matrix for a goal, as floats."""
    if goal == "draft":
        return res.team_draft_pick.astype(np.float64)
    return {
        "playoffs": res.team_made_playoffs,
        "division": res.team_won_division,
        "top_seed": res.team_won_top_seed,
    }[goal].astype(np.float64)


def _conditional_means(
    matrix: np.ndarray, home_won: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int, int]:
    """Mean of every team's column, split by who won one game."""
    n_home = int(home_won.sum())
    n_away = matrix.shape[0] - n_home
    if n_home == 0 or n_away == 0:
        flat = matrix.mean(axis=0)
        return flat, flat, n_home, n_away
    return (
        matrix[home_won].mean(axis=0),
        matrix[~home_won].mean(axis=0),
        n_home,
        n_away,
    )


def noise_floor(
    swings: dict[str, np.ndarray],
    games,
    conf: dict[str, str],
    team: str,
    team_col: int,
    goal: str,
) -> float:
    """Largest swing this team saw on games that cannot really affect it.

    Games between two teams of the other conference reach this team only
    through strength of victory and strength of schedule, so their true impact
    is a hair above nothing. Whatever we measure on them is therefore mostly
    simulation noise, and anything smaller cannot be distinguished from it.

    The draft goal has no such control group -- it ranks all 32 teams, so every
    result moves it -- and falls back to the configured minimum.
    """
    if goal == "draft":
        return MIN_NOISE_FLOOR
    subj_conf = conf[team]
    control = [
        abs(float(swings[g.game_id][team_col]))
        for g in games
        if conf.get(g.home) != subj_conf and conf.get(g.away) != subj_conf
    ]
    if not control:
        return MIN_NOISE_FLOOR
    return max(max(control), MIN_NOISE_FLOOR)


def assign_tier(swing: float, floor: float) -> str:
    """Bucket a swing. Thresholds come from config; the floor is per-run.

    The noise floor GATES the whole ladder rather than sitting at the bottom of
    it. Checking the fixed cutoffs first looks equivalent but is not: with few
    simulations the floor rises above 2 points, and a game that is pure noise
    can swing 2-3 points by luck alone. Tested in descending order it would
    come back "Root hard" -- the model confidently telling a fan to care about
    an AFC game that cannot touch them. Gating first means nothing is ever
    promoted above "doesn't matter" unless it outranks this run's own noise.
    """
    if swing < floor:
        return TIER_DOESNT_MATTER
    if swing >= MUST_WIN_THRESHOLD:
        return TIER_MUST_WIN
    if swing >= ROOT_HARD_THRESHOLD:
        return TIER_ROOT_HARD
    return TIER_A_LITTLE


def build_rows(res, teams) -> tuple[list[TeamOdds], list[ImpactRow]]:
    """Compute the full grid of impact rows plus every team's season odds."""
    odds = team_odds(res)
    playoff_pct = {o.team: o.playoff_pct for o in odds}
    top_seed_pct = {o.team: o.top_seed_pct for o in odds}
    conf = {a: t.conf for a, t in teams.items()}
    division = {a: t.division for a, t in teams.items()}
    index = res.team_index
    inv = {col: abbr for abbr, col in index.items()}

    rows: list[ImpactRow] = []
    for goal in GOALS:
        matrix = _goal_matrix(res, goal)
        scale = GOAL_SCALE[goal]
        higher_better = HIGHER_IS_BETTER[goal]

        # Pass one: the signed swing per game per team, so the noise floor can
        # be measured before anything is tiered.
        signed: dict[str, np.ndarray] = {}
        home_arm: dict[str, np.ndarray] = {}
        away_arm: dict[str, np.ndarray] = {}
        for j, g in enumerate(res.games):
            hw = res.home_wins[:, j]
            v_home, v_away, _, _ = _conditional_means(matrix, hw)
            signed[g.game_id] = (v_home - v_away) * scale
            home_arm[g.game_id] = v_home
            away_arm[g.game_id] = v_away

        # Pass two: tier and classify.
        floors = {
            abbr: noise_floor(signed, res.games, conf, abbr, col, goal)
            for abbr, col in index.items()
        }
        for g in res.games:
            diff = signed[g.game_id]
            for abbr, col in index.items():
                d = float(diff[col])
                # Which side does this team want? For the draft, the better
                # outcome is the SMALLER number.
                home_is_better = d > 0 if higher_better else d < 0
                root_for = g.home if home_is_better else g.away
                swing = abs(d)
                rows.append(
                    ImpactRow(
                        game_id=g.game_id,
                        team=abbr,
                        goal=goal,
                        root_for=root_for,
                        impact_pts=swing,
                        root_for_win_pct=(
                            g.p_home if root_for == g.home else 1.0 - g.p_home
                        ) * 100.0,
                        tier=assign_tier(swing, floors[abbr]),
                        reason_code=reason_code(
                            abbr, g.home, g.away, goal, conf, division,
                            playoff_pct, top_seed_pct,
                        ),
                    )
                )
    return odds, rows
