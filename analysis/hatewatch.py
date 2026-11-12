"""Who to root for: rank remaining games by how much they swing MIN's season.

THE IMPACT CALCULATION

One simulation run gives us, for every iteration, who won each remaining game
and how MIN's season ended. To value a game we split the iterations by that
game's winner and compare:

    impact = outcome(MIN | team A won) - outcome(MIN | team B won)

This is conditioning, not re-simulation: because each game's winner already
varies across iterations, the same 20,000 seasons answer the question for all
136 remaining games at once.

FOUR GOALS, WHICH DO NOT AGREE

  playoffs  P(make the playoffs)        higher is better
  division  P(win the NFC North)        higher is better
  top_seed  P(the #1 seed)              higher is better
  draft     expected draft pick         LOWER is better

The last one points the other way on purpose. A fan who has given up on the
season wants a high pick, i.e. a low pick NUMBER, which usually means rooting
for the opposite result. Note that this follows from how draft order works:
MIN's slot is one more than the number of teams finishing below it, so when
some other team wins, it can climb past MIN and pull MIN's pick EARLIER. The
draft goal therefore tends to favour everyone else winning -- the reverse of
the playoff goal, which wants rivals to lose. Games where the goals disagree
get called out at the end.

READING THE NUMBERS

Each conditional is an average over a subset of iterations, so it carries Monte
Carlo noise, and we report a standard error per game and flag swings that are
not distinguishable from zero. Two things make small numbers untrustworthy:

  * A lopsided game puts few iterations in one arm. A 90% favourite leaves only
    about 2,000 of 20,000 iterations in the upset arm.
  * Games between two teams in the other conference cannot affect MIN's
    playoff, division or seed odds at all, so their true impact there is
    exactly zero. They make a built-in control: the report prints the largest
    swing measured across them as the resolution limit. (They CAN affect the
    draft pick, since that ranks all 32 teams.)

Usage:
    python analysis/hatewatch.py                 # this week
    python analysis/hatewatch.py --compare       # before/after ratings
    python analysis/hatewatch.py --goal draft
    python analysis/hatewatch.py --week 14 --sims 50000
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulate import GOALS, SimResult, simulate
from standings import connect, load_teams
from win_probability import method_counts

# Calibrated against the other-conference control group, whose true impact on
# the playoff goal is exactly zero: at 2.0 sigma, 3 of those 50 games were
# wrongly flagged real (about the 5% false-positive rate you would predict);
# at 2.5 and above, none were. 3.0 leaves headroom.
NOISE_SIGMA_THRESHOLD = 3.0

GOAL_UNITS = {
    "playoffs": "pp",
    "division": "pp",
    "top_seed": "pp",
    "draft": "picks",
}


@dataclass
class Impact:
    game_id: str
    week: int
    home: str
    away: str
    goal: str
    value_if_home: float       # goal value when the home team wins
    value_if_away: float
    n_home: int
    n_away: int
    std_error: float
    higher_is_better: bool

    @property
    def root_for(self) -> str:
        home_better = (
            self.value_if_home > self.value_if_away
            if self.higher_is_better
            else self.value_if_home < self.value_if_away
        )
        return self.home if home_better else self.away

    @property
    def against(self) -> str:
        return self.away if self.root_for == self.home else self.home

    @property
    def raw_swing(self) -> float:
        return abs(self.value_if_home - self.value_if_away)

    @property
    def swing(self) -> float:
        """Swing in display units: percentage points, or draft picks."""
        scale = 100.0 if GOAL_UNITS[self.goal] == "pp" else 1.0
        return self.raw_swing * scale

    @property
    def is_noise(self) -> bool:
        if self.std_error == 0:
            return True
        return self.raw_swing < NOISE_SIGMA_THRESHOLD * self.std_error

    @property
    def involves(self) -> tuple[str, str]:
        return self.home, self.away


def compute_impacts(res: SimResult, goal: str) -> list[Impact]:
    """Conditional goal value for every remaining game, in one pass."""
    column, higher_is_better = GOALS[goal]
    outcome = getattr(res, column).astype(np.float64)
    overall = float(outcome.mean())

    impacts: list[Impact] = []
    for j, g in enumerate(res.games):
        home_won = res.home_wins[:, j]
        n_home = int(home_won.sum())
        n_away = res.n_sims - n_home

        # A game can be decided in every iteration, leaving an empty arm.
        if n_home == 0 or n_away == 0:
            impacts.append(
                Impact(g.game_id, g.week, g.home, g.away, goal, overall, overall,
                       n_home, n_away, 0.0, higher_is_better)
            )
            continue

        h = outcome[home_won]
        a = outcome[~home_won]
        v_home, v_away = float(h.mean()), float(a.mean())
        # SE of a difference of two independent means. For a 0/1 column this
        # reduces to the usual sqrt(p(1-p)/n) form.
        se = float(np.sqrt(h.var() / n_home + a.var() / n_away))

        impacts.append(
            Impact(g.game_id, g.week, g.home, g.away, goal, v_home, v_away,
                   n_home, n_away, se, higher_is_better)
        )
    return impacts


def noise_floor(impacts: list[Impact], control_ids: set[str]) -> tuple[int, float]:
    """Largest swing among games that cannot matter -- the resolution limit."""
    control = [i.swing for i in impacts if i.game_id in control_ids]
    if not control:
        return 0, 0.0
    return len(control), max(control)


def print_table(impacts: list[Impact], title: str, target: str,
                limit: int | None = None) -> None:
    ranked = sorted(impacts, key=lambda i: -i.swing)
    if limit:
        ranked = ranked[:limit]
    unit = GOAL_UNITS[impacts[0].goal] if impacts else "pp"
    fmt = "{:>7.1f}%" if unit == "pp" else "{:>8.1f}"

    print(f"\n{title}")
    print(f"  {'matchup':<14} {'root for':>8} {'against':>8} {'swing':>9} "
          f"{'if home':>8} {'if away':>8}  note")
    print("  " + "-" * 76)
    for i in ranked:
        matchup = f"{i.away} @ {i.home}"
        note = []
        if target in i.involves:
            note.append(f"{target} plays")
        if i.is_noise:
            note.append("~noise")
        vh = fmt.format(i.value_if_home * (100 if unit == "pp" else 1))
        va = fmt.format(i.value_if_away * (100 if unit == "pp" else 1))
        print(f"  {matchup:<14} {i.root_for:>8} {i.against:>8} "
              f"{i.swing:>6.2f} {unit:<2} {vh:>8} {va:>8}  {', '.join(note)}")


def find_disagreements(
    res: SimResult, week: int
) -> list[tuple[str, dict[str, Impact]]]:
    """Games where the four goals do not all point at the same team.

    Only goals whose swing clears the noise threshold get a vote -- otherwise
    random noise in a goal that barely cares would manufacture disagreement.
    """
    per_goal = {goal: compute_impacts(res, goal) for goal in GOALS}
    by_game: dict[str, dict[str, Impact]] = {}
    for goal, impacts in per_goal.items():
        for i in impacts:
            if i.week != week:
                continue
            by_game.setdefault(i.game_id, {})[goal] = i

    out = []
    for game_id, goals in by_game.items():
        voting = {g: i for g, i in goals.items() if not i.is_noise}
        if len(voting) < 2:
            continue
        if len({i.root_for for i in voting.values()}) > 1:
            out.append((game_id, goals))
    return out


def print_summary(res: SimResult, label: str) -> None:
    print(f"  {label:<10} playoffs {res.playoff_odds * 100:5.1f}%   "
          f"division {res.division_odds * 100:5.1f}%   "
          f"#1 seed {res.top_seed_odds * 100:5.1f}%   "
          f"mean draft pick {res.mean_draft_pick:4.1f}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--team", default="MIN")
    ap.add_argument("--sims", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--week", type=int, help="default: the earliest unplayed week")
    ap.add_argument("--goal", default="playoffs", choices=list(GOALS))
    ap.add_argument("--all-weeks", action="store_true")
    ap.add_argument("--compare", action="store_true",
                    help="also run without ratings, to show before/after")
    ap.add_argument("--no-ratings", action="store_true")
    args = ap.parse_args()

    with connect() as conn:
        teams = load_teams(conn)
        res = simulate(conn, args.season, args.sims, args.team, args.seed,
                       use_ratings=not args.no_ratings)
        before = None
        if args.compare:
            before = simulate(conn, args.season, args.sims, args.team, args.seed,
                              use_ratings=False)

    if not res.games:
        print(f"{args.season}: no remaining games.")
        return 0

    counts = method_counts(res.games)
    team = teams[args.team]
    week = args.week or min(g.week for g in res.games)

    print(f"=== {args.team} hatewatch guide, {args.season} ===")
    print(f"  {team.name}, {team.division}")
    print(f"  {res.n_sims:,} simulated seasons, {len(res.games)} games remaining")
    print(f"  pricing: " + ", ".join(f"{m} {c}" for m, c in counts.items() if c))
    print(f"  rating jitter: {res.jitter_sd:.2f} points\n")

    if before is not None:
        print("  BEFORE/AFTER (same seed, same 20,000 draws)")
        print_summary(before, "before")
        print_summary(res, "after")
        print(f"  {'':<10} before = unpriced games as 50/50; "
              f"after = market-implied ratings")
    else:
        print_summary(res, "odds")
    print(f"\n  playoff odds standard error: "
          f"+/- {res.standard_error() * 100:.2f} pp")

    impacts = compute_impacts(res, args.goal)

    # Control group: games that cannot affect the playoff/division/seed goals.
    control_ids = {
        g.game_id for g in res.games
        if teams[g.home].conf != team.conf and teams[g.away].conf != team.conf
    }
    if args.goal != "draft":
        n_ctrl, floor = noise_floor(impacts, control_ids)
        if n_ctrl:
            print(f"\n  Noise floor: {n_ctrl} remaining games are "
                  f"{team.conf}-irrelevant, so their true impact")
            print(f"  on '{args.goal}' is zero. Largest measured: "
                  f"{floor:.2f} {GOAL_UNITS[args.goal]} -- the resolution limit.")

    if args.all_weeks:
        print_table(impacts, f"All {len(impacts)} remaining games "
                    f"by '{args.goal}' impact", args.team, limit=25)
        return 0

    this_week = [i for i in impacts if i.week == week]
    if not this_week:
        print(f"\nNo remaining games in week {week}.")
        return 1

    print_table(this_week, f"Week {week}: {len(this_week)} games ranked by "
                f"'{args.goal}' impact", args.team)

    real = [i for i in this_week if not i.is_noise]
    print(f"\n  {len(real)} of {len(this_week)} games clear the noise threshold.")
    if real:
        top = max(real, key=lambda i: i.swing)
        print(f"  Biggest: root for {top.root_for} over {top.against} "
              f"({top.swing:.2f} {GOAL_UNITS[args.goal]}).")

    if before is not None:
        b_imp = [i for i in compute_impacts(before, args.goal) if i.week == week]
        print_table(b_imp, f"Week {week} BEFORE (unpriced games as 50/50), "
                    f"for comparison", args.team)

    # --- where the goals disagree -------------------------------------------
    disagreements = find_disagreements(res, week)
    print(f"\n  GOALS IN CONFLICT -- week {week}")
    print("  " + "-" * 76)
    if not disagreements:
        print("  None: every goal with a measurable swing agrees this week.")
    else:
        print(f"  {len(disagreements)} of {len(this_week)} games split the four "
              f"goals.\n")
        order = sorted(
            disagreements,
            key=lambda kv: -max(i.swing for i in kv[1].values() if not i.is_noise),
        )
        for game_id, goals in order:
            any_i = next(iter(goals.values()))
            print(f"  {any_i.away} @ {any_i.home}")
            for goal in GOALS:
                i = goals[goal]
                tag = "  (noise, no vote)" if i.is_noise else ""
                print(f"     {goal:<9} root for {i.root_for:<4} "
                      f"swing {i.swing:5.2f} {GOAL_UNITS[goal]:<6}{tag}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
