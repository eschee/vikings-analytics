"""Who to root for: rank remaining games by how much they swing MIN's playoff odds.

THE IMPACT CALCULATION

One simulation run gives us, for every iteration, who won each remaining game
and whether MIN made the playoffs. To find out what a given game is worth we
split the iterations by that game's winner and compare:

    impact = P(MIN makes playoffs | team A won) - P(MIN makes playoffs | team B won)

This is conditioning, not re-simulation: because the winner of each game varies
across iterations anyway, the same 20,000 seasons answer the question for all
136 games at once. Root for whichever side has the higher conditional
probability; the absolute difference is the swing, in percentage points.

READING THE NUMBERS

Each conditional probability is an average over a subset of iterations, so it
carries Monte Carlo noise. We report a standard error per game and flag swings
that are not distinguishable from zero. Two things make small numbers
untrustworthy:

  * A lopsided game puts few iterations in one arm. A 90% favourite leaves
    only ~2,000 of 20,000 iterations in the upset arm.
  * Games between two teams in the other conference cannot affect MIN under
    win-percentage tiebreakers, so their true impact is exactly zero and
    whatever we measure is noise. They make a useful built-in control: if a
    flagged game ranks near them, it is not real either.

Usage:
    python analysis/hatewatch.py                      # this week, 2026
    python analysis/hatewatch.py --week 12 --sims 50000
    python analysis/hatewatch.py --all-weeks
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulate import SimResult, simulate
from standings import connect, load_teams
from win_probability import method_counts

# Below this many standard errors, a swing is indistinguishable from noise.
# Calibrated against the other-conference control group described above, whose
# true impact is exactly zero: at 2.0 sigma, 3 of those 50 games were wrongly
# flagged as real (about the 5% false-positive rate you would predict); at
# 2.5 and above, none were. 3.0 leaves headroom.
NOISE_SIGMA_THRESHOLD = 3.0


@dataclass
class Impact:
    game_id: str
    week: int
    home: str
    away: str
    p_home_win: float            # market probability the home team wins
    odds_if_home: float          # MIN playoff odds given the home team wins
    odds_if_away: float
    n_home: int                  # iterations in each arm
    n_away: int
    std_error: float             # on the difference, in probability

    @property
    def root_for(self) -> str:
        return self.home if self.odds_if_home >= self.odds_if_away else self.away

    @property
    def against(self) -> str:
        return self.away if self.root_for == self.home else self.home

    @property
    def swing(self) -> float:
        """Absolute swing in MIN's playoff odds, in percentage points."""
        return abs(self.odds_if_home - self.odds_if_away) * 100.0

    @property
    def is_noise(self) -> bool:
        if self.std_error == 0:
            return True
        return self.swing / 100.0 < NOISE_SIGMA_THRESHOLD * self.std_error

    @property
    def involves_min(self) -> bool:
        return "MIN" in (self.home, self.away)


def compute_impacts(res: SimResult, target: str = "MIN") -> list[Impact]:
    """Conditional playoff odds for every remaining game, in one pass."""
    made = res.made_playoffs
    impacts: list[Impact] = []

    for j, g in enumerate(res.games):
        home_won = res.home_wins[:, j]
        n_home = int(home_won.sum())
        n_away = res.n_sims - n_home

        # A game can be effectively decided in every iteration (p_home ~ 1),
        # leaving an empty arm. Nothing to compare, so no impact.
        if n_home == 0 or n_away == 0:
            impacts.append(
                Impact(g.game_id, g.week, g.home, g.away, g.p_home,
                       float(made.mean()), float(made.mean()),
                       n_home, n_away, 0.0)
            )
            continue

        odds_if_home = float(made[home_won].mean())
        odds_if_away = float(made[~home_won].mean())

        # SE of a difference of two independent proportions.
        se = float(
            np.sqrt(
                odds_if_home * (1 - odds_if_home) / n_home
                + odds_if_away * (1 - odds_if_away) / n_away
            )
        )
        impacts.append(
            Impact(g.game_id, g.week, g.home, g.away, g.p_home,
                   odds_if_home, odds_if_away, n_home, n_away, se)
        )
    return impacts


def noise_floor(impacts: list[Impact], other_conf_games: set[str]) -> tuple[int, float]:
    """Observed spread of impacts among games that cannot matter.

    Games between two teams in the other conference have a true impact of
    exactly zero under win-percentage tiebreakers, so whatever swing we measure
    for them is the simulation's noise floor. Anything below it is not signal.
    """
    control = [i.swing for i in impacts if i.game_id in other_conf_games]
    if not control:
        return 0, 0.0
    return len(control), max(control)


def print_table(impacts: list[Impact], title: str, limit: int | None = None) -> None:
    ranked = sorted(impacts, key=lambda i: -i.swing)
    if limit:
        ranked = ranked[:limit]

    print(f"\n{title}")
    print(f"  {'matchup':<14} {'root for':>8} {'against':>8} {'swing':>7} "
          f"{'if home':>8} {'if away':>8}  note")
    print("  " + "-" * 74)
    for i in ranked:
        matchup = f"{i.away} @ {i.home}"
        note = []
        if i.involves_min:
            note.append("MIN plays")
        if i.is_noise:
            note.append("~noise")
        print(
            f"  {matchup:<14} {i.root_for:>8} {i.against:>8} "
            f"{i.swing:>6.2f}p {i.odds_if_home * 100:>7.1f}% "
            f"{i.odds_if_away * 100:>7.1f}%  {', '.join(note)}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--team", default="MIN")
    ap.add_argument("--sims", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--week", type=int, help="default: the earliest unplayed week")
    ap.add_argument("--all-weeks", action="store_true")
    args = ap.parse_args()

    with connect() as conn:
        teams = load_teams(conn)
        res = simulate(conn, args.season, args.sims, args.team, args.seed)

    if not res.games:
        print(f"{args.season}: no remaining games.")
        return 0

    counts = method_counts(res.games)
    team = teams[args.team]

    print(f"=== {args.team} hatewatch guide, {args.season} ===")
    print(f"  {team.name}, {team.division}")
    print(f"  {res.n_sims:,} simulated seasons, {len(res.games)} games remaining")
    print(f"  win probabilities from: "
          + ", ".join(f"{m} {c}" for m, c in counts.items() if c))

    se = res.standard_error() * 100
    print(f"\n  {args.team} playoff odds   {res.playoff_odds * 100:5.1f}%  (+/- {se:.2f} pp)")
    print(f"  {args.team} division odds  {res.division_odds * 100:5.1f}%")

    if counts.get("coin_flip"):
        pct = 100 * counts["coin_flip"] / len(res.games)
        print(f"\n  CAVEAT: {counts['coin_flip']} of {len(res.games)} remaining games "
              f"({pct:.0f}%) have no betting")
        print(f"  market yet and are modelled as 50/50. Those odds ignore team "
              f"quality, so the")
        print(f"  numbers below are directionally useful but not a real forecast.")

    impacts = compute_impacts(res, args.team)

    # Empirical noise floor from games that cannot possibly affect the target.
    other_conf = {
        g.game_id for g in res.games
        if teams[g.home].conf != team.conf and teams[g.away].conf != team.conf
    }
    n_ctrl, floor = noise_floor(impacts, other_conf)
    if n_ctrl:
        print(f"\n  Noise floor: {n_ctrl} remaining games are {team.conf}-irrelevant "
              f"(both teams in the other")
        print(f"  conference, so their true impact is zero). The largest swing measured "
              f"for any")
        print(f"  of them is {floor:.2f} pp -- treat that as the resolution limit.")

    if args.all_weeks:
        print_table(impacts, f"All {len(impacts)} remaining games by impact", limit=25)
    else:
        week = args.week or min(g.week for g in res.games)
        this_week = [i for i in impacts if i.week == week]
        if not this_week:
            print(f"\nNo remaining games in week {week}.")
            return 1
        print_table(
            this_week,
            f"Week {week}: {len(this_week)} games ranked by impact on "
            f"{args.team}'s playoff odds",
        )

        real = [i for i in this_week if not i.is_noise]
        print(f"\n  {len(real)} of {len(this_week)} games show a swing above "
              f"simulation noise.")
        if real:
            top = max(real, key=lambda i: i.swing)
            print(f"  Biggest: root for {top.root_for} over {top.against} "
                  f"({top.swing:.2f} pp).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
