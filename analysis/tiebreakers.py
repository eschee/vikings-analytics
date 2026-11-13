"""The real NFL tiebreaking procedures, in plain English and in code.

When teams finish with the same record, the NFL does not flip a coin -- it walks
a fixed ladder of comparisons until one team comes out ahead. There are two
ladders: one for teams in the SAME division, one for teams in DIFFERENT
divisions (used for wild cards and for seeding division winners against each
other). This module implements both.

THE DIVISION LADDER (same division)

  1. Head-to-head. Best record in the games the tied teams played against
     each other. Teams in a division always play each other twice, so this
     usually settles it.
  2. Division record. Best record against the other teams in the division.
  3. Common games. Best record against opponents all the tied teams faced.
     Division rivals share most of their schedule, so this set is large.
  4. Conference record. Best record against the rest of the conference.
  5. Strength of victory. Add up the records of every team you BEAT. Beating
     good teams counts for more than beating bad ones.
  6. Strength of schedule. Add up the records of every team you PLAYED,
     win or lose. Rewards having had a harder road.
  7. Combined points ranking within the conference. Rank the conference by
     points scored and again by points allowed; add the two ranks. Lower is
     better, so being 3rd in scoring and 5th in defence (8) beats being 1st
     and 9th (10).
  8. Combined points ranking across the league. Same idea, all 32 teams.
  9. Net points in common games. Points scored minus points allowed, counting
     only the shared opponents from step 3.
 10. Net points in all games.
 11. Net touchdowns in all games. NOT IMPLEMENTED -- see UNAVAILABLE below.
 12. Coin toss.

THE WILD-CARD LADDER (different divisions)

Mostly the same, with three real differences:

  * There is no "division record" step -- comparing a team's record against
    the AFC North to another's against the AFC West would be meaningless.
  * Common games requires a MINIMUM OF FOUR shared opponents. Teams in
    different divisions may barely overlap, and a 1-game sample is noise.
  * With three or more teams, head-to-head only counts as a SWEEP: it applies
    only if one team beat all the others, or lost to all the others. A 1-1
    muddle among three teams tells you nothing, so the NFL skips it.

  1. Head-to-head (sweep only when 3+ teams are tied)
  2. Conference record
  3. Common games (minimum four)
  4. Strength of victory
  5. Strength of schedule
  6. Combined points ranking within the conference
  7. Combined points ranking across the league
  8. Net points in conference games
  9. Net points in all games
 10. Net touchdowns in all games -- NOT IMPLEMENTED
 11. Coin toss

THE DIVISION-FIRST RULE FOR WILD CARDS

This one trips people up. Before comparing wild-card contenders from different
divisions, any tied teams from the SAME division are settled among themselves
first, and only the top one advances to the comparison. So if Minnesota and
Green Bay are tied for a wild card and Minnesota holds the division tiebreak
over Green Bay, Green Bay cannot leapfrog Minnesota via a league-wide step --
it has to wait for the next slot. Without this rule you can produce orderings
the NFL would never print.

REVERTING

If a step eliminates some teams and exactly two remain, the procedure restarts
at step 1 of the two-team ladder. This matters: three teams might be
indistinguishable on head-to-head as a group, but once the third is gone the
remaining two may have a decisive head-to-head record.

UNAVAILABLE STEPS

Net touchdowns (the last step before a coin toss) is not implemented. Touchdown
counts are not in the games table; they would have to come from play-by-play,
which this project loads for 2022-2025 but not 2026, and which simulated
seasons do not produce at all. Reaching this step requires two teams identical
on all eleven prior comparisons, which effectively never happens. When it is
skipped the reason is recorded in the result rather than passed over silently.

Simulated seasons also have no scores, only wins and losses, so steps that need
points are reported unavailable there and the ladder falls through to a coin
toss. In practice the first six steps resolve almost everything.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field


def pct(w: float, l: float, t: float) -> float:
    """NFL winning percentage: a tie is half a win."""
    total = w + l + t
    return (w + 0.5 * t) / total if total else 0.0


@dataclass
class Rec:
    """A won-lost-tied record that can be added to another."""

    w: float = 0.0
    l: float = 0.0
    t: float = 0.0

    def add_result(self, won: bool | None) -> None:
        if won is None:
            self.t += 1
        elif won:
            self.w += 1
        else:
            self.l += 1

    def __iadd__(self, other: "Rec") -> "Rec":
        self.w += other.w
        self.l += other.l
        self.t += other.t
        return self

    @property
    def pct(self) -> float:
        return pct(self.w, self.l, self.t)

    @property
    def games(self) -> int:
        return int(self.w + self.l + self.t)


@dataclass(frozen=True)
class Result:
    """One completed game. Scores may be None for a simulated season."""

    home: str
    away: str
    home_score: int | None = None
    away_score: int | None = None
    home_won: bool | None = None   # set directly when there are no scores

    @property
    def tie(self) -> bool:
        if self.home_score is not None and self.away_score is not None:
            return self.home_score == self.away_score
        return self.home_won is None

    @property
    def winner(self) -> str | None:
        if self.tie:
            return None
        if self.home_score is not None and self.away_score is not None:
            return self.home if self.home_score > self.away_score else self.away
        return self.home if self.home_won else self.away

    @property
    def has_scores(self) -> bool:
        return self.home_score is not None and self.away_score is not None


class SeasonContext:
    """Everything the tiebreakers need from one season, computed once.

    Building this up front matters: the ladder asks the same questions
    repeatedly (what is this team's conference record, who did it beat), and
    recomputing them per comparison would be both slow and easy to get subtly
    inconsistent.
    """

    def __init__(self, results: list[Result], teams: dict[str, object]):
        self.teams = teams
        self.results = results
        self.conf = {a: t.conf for a, t in teams.items()}
        self.div = {a: t.division for a, t in teams.items()}

        self.overall: dict[str, Rec] = {a: Rec() for a in teams}
        self.division: dict[str, Rec] = {a: Rec() for a in teams}
        self.conference: dict[str, Rec] = {a: Rec() for a in teams}
        # head-to-head: h2h[team][opponent]
        self.h2h: dict[str, dict[str, Rec]] = {a: defaultdict(Rec) for a in teams}
        # every opponent faced, with repeats, and every opponent beaten
        self.opponents: dict[str, list[str]] = {a: [] for a in teams}
        self.beaten: dict[str, list[str]] = {a: [] for a in teams}

        self.points_for: dict[str, float] = {a: 0.0 for a in teams}
        self.points_against: dict[str, float] = {a: 0.0 for a in teams}
        self.conf_points_for: dict[str, float] = {a: 0.0 for a in teams}
        self.conf_points_against: dict[str, float] = {a: 0.0 for a in teams}
        # per-opponent points, for net points in common games
        self.pf_vs: dict[str, dict[str, float]] = {a: defaultdict(float) for a in teams}
        self.pa_vs: dict[str, dict[str, float]] = {a: defaultdict(float) for a in teams}

        self.any_scores = False

        for r in results:
            h, a = r.home, r.away
            if h not in teams or a not in teams:
                continue
            same_div = self.div[h] == self.div[a]
            same_conf = self.conf[h] == self.conf[a]
            winner = r.winner
            h_won = None if r.tie else (winner == h)

            self.overall[h].add_result(h_won)
            self.overall[a].add_result(None if h_won is None else not h_won)
            if same_div:
                self.division[h].add_result(h_won)
                self.division[a].add_result(None if h_won is None else not h_won)
            if same_conf:
                self.conference[h].add_result(h_won)
                self.conference[a].add_result(None if h_won is None else not h_won)

            self.h2h[h][a].add_result(h_won)
            self.h2h[a][h].add_result(None if h_won is None else not h_won)

            self.opponents[h].append(a)
            self.opponents[a].append(h)
            if winner is not None:
                self.beaten[winner].append(a if winner == h else h)

            if r.has_scores:
                self.any_scores = True
                self.points_for[h] += r.home_score
                self.points_against[h] += r.away_score
                self.points_for[a] += r.away_score
                self.points_against[a] += r.home_score
                self.pf_vs[h][a] += r.home_score
                self.pa_vs[h][a] += r.away_score
                self.pf_vs[a][h] += r.away_score
                self.pa_vs[a][h] += r.home_score
                if same_conf:
                    self.conf_points_for[h] += r.home_score
                    self.conf_points_against[h] += r.away_score
                    self.conf_points_for[a] += r.away_score
                    self.conf_points_against[a] += r.home_score

        self._points_rank_cache: dict[str, dict[str, int]] = {}

    # --- derived quantities ------------------------------------------------

    def aggregate(self, teams_list: list[str]) -> Rec:
        """Combined record of a list of teams, counting repeats."""
        total = Rec()
        for t in teams_list:
            total += self.overall[t]
        return total

    def strength_of_victory(self, team: str) -> float:
        return self.aggregate(self.beaten[team]).pct

    def strength_of_schedule(self, team: str) -> float:
        return self.aggregate(self.opponents[team]).pct

    def common_opponents(self, group: list[str]) -> set[str]:
        """Opponents every team in the group faced, excluding the group itself."""
        sets = [set(self.opponents[t]) for t in group]
        common = set.intersection(*sets) if sets else set()
        return common - set(group)

    def record_vs(self, team: str, opponents: set[str]) -> Rec:
        total = Rec()
        for opp in opponents:
            total += self.h2h[team][opp]
        return total

    def net_points(self, team: str) -> float:
        return self.points_for[team] - self.points_against[team]

    def net_points_conference(self, team: str) -> float:
        return self.conf_points_for[team] - self.conf_points_against[team]

    def net_points_vs(self, team: str, opponents: set[str]) -> float:
        return sum(
            self.pf_vs[team][o] - self.pa_vs[team][o] for o in opponents
        )

    def combined_points_rank(self, team: str, scope: str) -> int:
        """Rank in points scored plus rank in points allowed. Lower is better.

        scope is "conf" to rank only within the team's conference, or "all".
        """
        key = f"{scope}:{self.conf[team] if scope == 'conf' else 'all'}"
        if key not in self._points_rank_cache:
            pool = [
                a for a in self.teams
                if scope == "all" or self.conf[a] == self.conf[team]
            ]
            # Most points scored is rank 1; fewest points allowed is rank 1.
            by_scored = sorted(pool, key=lambda a: -self.points_for[a])
            by_allowed = sorted(pool, key=lambda a: self.points_against[a])
            scored_rank = {a: i + 1 for i, a in enumerate(by_scored)}
            allowed_rank = {a: i + 1 for i, a in enumerate(by_allowed)}
            self._points_rank_cache[key] = {
                a: scored_rank[a] + allowed_rank[a] for a in pool
            }
        return self._points_rank_cache[key][team]


# ---------------------------------------------------------------------------
# Steps. Each returns {team: score} where HIGHER IS BETTER, or None when the
# step cannot be applied (missing data, or not enough common games).
# ---------------------------------------------------------------------------

@dataclass
class Step:
    name: str
    fn: object
    note: str = ""


def _h2h(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
    """Best record in games among the tied teams."""
    out = {}
    for t in group:
        rec = Rec()
        for o in group:
            if o != t:
                rec += ctx.h2h[t][o]
        if rec.games == 0:
            return None          # they never played; step does not apply
        out[t] = rec.pct
    return out


def _h2h_sweep(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
    """Head-to-head, but only if someone swept or was swept.

    With three or more teams from different divisions, a mixed 1-1 result
    carries no information, so the NFL only uses this step when one team beat
    every other tied team, or lost to every one of them.
    """
    if len(group) == 2:
        return _h2h(group, ctx)

    records = {}
    for t in group:
        rec = Rec()
        for o in group:
            if o != t:
                rec += ctx.h2h[t][o]
        if rec.games == 0:
            return None
        records[t] = rec

    for t, rec in records.items():
        if rec.l == 0 and rec.w > 0:          # beat everyone
            return {x: (1.0 if x == t else 0.0) for x in group}
        if rec.w == 0 and rec.l > 0:          # lost to everyone
            return {x: (0.0 if x == t else 1.0) for x in group}
    return None


def _division_record(group: list[str], ctx: SeasonContext) -> dict[str, float]:
    return {t: ctx.division[t].pct for t in group}


def _conference_record(group: list[str], ctx: SeasonContext) -> dict[str, float]:
    return {t: ctx.conference[t].pct for t in group}


def _common_games(min_games: int):
    """Best record against opponents all the tied teams faced."""

    def step(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
        common = ctx.common_opponents(group)
        if not common:
            return None
        out = {}
        for t in group:
            rec = ctx.record_vs(t, common)
            if rec.games < min_games:
                return None       # too small a sample to mean anything
            out[t] = rec.pct
        return out

    return step


def _sov(group: list[str], ctx: SeasonContext) -> dict[str, float]:
    return {t: ctx.strength_of_victory(t) for t in group}


def _sos(group: list[str], ctx: SeasonContext) -> dict[str, float]:
    return {t: ctx.strength_of_schedule(t) for t in group}


def _points_rank(scope: str):
    def step(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
        if not ctx.any_scores:
            return None          # simulated season: no scores to rank
        # Lower combined rank is better, so negate.
        return {t: -float(ctx.combined_points_rank(t, scope)) for t in group}

    return step


def _net_points_common(min_games: int):
    def step(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
        if not ctx.any_scores:
            return None
        common = ctx.common_opponents(group)
        if not common:
            return None
        for t in group:
            if ctx.record_vs(t, common).games < min_games:
                return None
        return {t: ctx.net_points_vs(t, common) for t in group}

    return step


def _net_points_conference(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
    if not ctx.any_scores:
        return None
    return {t: ctx.net_points_conference(t) for t in group}


def _net_points_all(group: list[str], ctx: SeasonContext) -> dict[str, float] | None:
    if not ctx.any_scores:
        return None
    return {t: ctx.net_points(t) for t in group}


def _net_touchdowns(group: list[str], ctx: SeasonContext) -> None:
    """Step 11. Always unavailable -- see UNAVAILABLE in the module docstring."""
    return None


# The two ladders, in official order.
DIVISION_LADDER = [
    Step("head-to-head", _h2h),
    Step("division record", _division_record),
    Step("common games", _common_games(1)),
    Step("conference record", _conference_record),
    Step("strength of victory", _sov),
    Step("strength of schedule", _sos),
    Step("points rank (conference)", _points_rank("conf")),
    Step("points rank (league)", _points_rank("all")),
    Step("net points, common games", _net_points_common(1)),
    Step("net points, all games", _net_points_all),
    Step("net touchdowns", _net_touchdowns, note="not implemented: no TD data"),
]

WILDCARD_LADDER = [
    Step("head-to-head (sweep)", _h2h_sweep),
    Step("conference record", _conference_record),
    Step("common games (min 4)", _common_games(4)),
    Step("strength of victory", _sov),
    Step("strength of schedule", _sos),
    Step("points rank (conference)", _points_rank("conf")),
    Step("points rank (league)", _points_rank("all")),
    Step("net points, conference games", _net_points_conference),
    Step("net points, all games", _net_points_all),
    Step("net touchdowns", _net_touchdowns, note="not implemented: no TD data"),
]


@dataclass
class Decision:
    """Which team won a tiebreak, and which step decided it."""

    winner: str
    step: str
    group: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _pick_best(
    group: list[str],
    ctx: SeasonContext,
    ladder: list[Step],
    rng: random.Random,
) -> Decision:
    """Walk the ladder until one team is left standing."""
    pool = list(group)
    skipped: list[str] = []
    steps = ladder
    i = 0
    while i < len(steps):
        if len(pool) == 1:
            break
        step = steps[i]
        scores = step.fn(pool, ctx)
        if scores is None:
            skipped.append(step.name)
            i += 1
            continue
        best = max(scores.values())
        top = [t for t in pool if scores[t] == best]
        if len(top) == 1:
            return Decision(top[0], step.name, list(group), skipped)
        if len(top) < len(pool):
            pool = top
            # Down to two: the procedure restarts at the top of the ladder,
            # because a head-to-head that was muddled among three teams can be
            # decisive between two.
            if len(pool) == 2:
                i = 0
                continue
        i += 1

    if len(pool) == 1:
        return Decision(pool[0], "reduced by earlier steps", list(group), skipped)
    # Every step exhausted: the NFL flips a coin, and so do we.
    winner = rng.choice(sorted(pool))
    return Decision(winner, "coin toss", list(group), skipped)


def order_group(
    group: list[str],
    ctx: SeasonContext,
    ladder: list[Step],
    rng: random.Random,
) -> tuple[list[str], list[Decision]]:
    """Rank a tied group by repeatedly pulling out the best team."""
    remaining = list(group)
    order: list[str] = []
    decisions: list[Decision] = []
    while remaining:
        if len(remaining) == 1:
            order.append(remaining[0])
            break
        d = _pick_best(remaining, ctx, ladder, rng)
        decisions.append(d)
        order.append(d.winner)
        remaining = [t for t in remaining if t != d.winner]
    return order, decisions


def rank_teams(
    teams_list: list[str],
    ctx: SeasonContext,
    ladder: list[Step],
    rng: random.Random,
) -> tuple[list[str], list[Decision]]:
    """Order teams by record, breaking any ties with the given ladder."""
    decisions: list[Decision] = []
    order: list[str] = []
    pool = sorted(teams_list, key=lambda t: -ctx.overall[t].pct)
    while pool:
        best = ctx.overall[pool[0]].pct
        tied = [t for t in pool if ctx.overall[t].pct == best]
        if len(tied) == 1:
            order.append(tied[0])
        else:
            sub, ds = order_group(tied, ctx, ladder, rng)
            order.extend(sub)
            decisions.extend(ds)
        pool = [t for t in pool if t not in set(tied)]
    return order, decisions


def rank_wildcards(
    candidates: list[str],
    ctx: SeasonContext,
    rng: random.Random,
) -> tuple[list[str], list[Decision]]:
    """Order wild-card contenders, applying the division-first rule.

    Among teams tied on record, any that share a division are settled by the
    DIVISION ladder first and only the best of them competes for this slot. The
    others wait for the next one. Skipping this lets a team leapfrog a division
    rival it is already behind, which the NFL does not allow.
    """
    decisions: list[Decision] = []
    order: list[str] = []
    pool = list(candidates)

    while pool:
        best = max(ctx.overall[t].pct for t in pool)
        tied = [t for t in pool if ctx.overall[t].pct == best]

        if len(tied) == 1:
            order.append(tied[0])
            pool.remove(tied[0])
            continue

        # Step 1: one representative per division.
        by_div: dict[str, list[str]] = defaultdict(list)
        for t in tied:
            by_div[ctx.div[t]].append(t)

        reps: list[str] = []
        for div, members in sorted(by_div.items()):
            if len(members) == 1:
                reps.append(members[0])
            else:
                d = _pick_best(members, ctx, DIVISION_LADDER, rng)
                decisions.append(d)
                reps.append(d.winner)

        if len(reps) == 1:
            pick = reps[0]
        else:
            d = _pick_best(reps, ctx, WILDCARD_LADDER, rng)
            decisions.append(d)
            pick = d.winner

        order.append(pick)
        pool.remove(pick)

    return order, decisions
