"""Every tunable number for the saved results, in one place.

Anything the website renders as a label or a threshold is defined here rather
than inline, so changing a cutoff is one edit and the stored data can always be
traced back to a known configuration.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Model version
#
# Stamped on every run so rows from different model generations are never
# silently compared on a chart. Bump it whenever a change would move the
# numbers: the win-probability method, the ratings fit, the jitter, the
# tiebreakers, or the simulation itself.
# ---------------------------------------------------------------------------
MODEL_VERSION = "v5.3-tank-mode"   # v5.2 + NFL draft order (SOS tiebreak, playoff teams last), tank goals

DEFAULT_SEASON = 2026
# 100,000 rather than 20,000. At 20k the noise floor for a team sat near
# 1.9 points, which is just under the 2.0 "root hard" cutoff -- so a game whose
# true impact was around 2 points flipped between "Root hard" and "Doesn't
# matter" from one run to the next purely on noise. At 100k the floor drops to
# about 1.3 and that band stops being a coin toss. Costs about 60 seconds.
#
# 200k (Nov 2026): games are now judged against their own sampling error
# (SIGNIFICANCE_Z), which shrinks with more seasons -- doubling them makes
# effects about 30% smaller measurable, so smaller real games can be shown.
# Costs about two minutes.
DEFAULT_SIMS = 200_000

# Seasons replayed both ways for each of this week's games (simulate's paired
# replays). Each replay costs a re-seeding, so this is far fewer than
# DEFAULT_SIMS -- but a paired difference is so much less noisy than comparing
# different seasons that 40,000 still measures this week's games more
# precisely than all 200,000 can by conditioning. About 4 extra minutes
# (measured: 345 s for simulate + replays vs 108 s without, Nov 2026).
PAIRED_SIMS = 40_000
DEFAULT_SEED = 20260101

# Retention.
#
# sim_runs and team_odds are kept forever: 32 rows and about 22 kB per run, so
# a whole season of three-a-week refreshes costs roughly a megabyte, and that
# history is what any "odds over time" chart is built from.
#
# game_impacts is the opposite: 17,408 rows and about 3.65 MB per run, which
# would reach ~200 MB over a season. The site only ever renders the newest run,
# so older impact grids are dead weight. Keeping the last few means a bad run
# can still be compared against its predecessors before being replaced.
IMPACT_RETENTION_RUNS = 3

# ---------------------------------------------------------------------------
# Tiers
#
# How much a single game matters, in the units of the goal: percentage points
# for the probability goals, draft picks for the draft goal.
#
# The bottom cutoff is not a constant. "A little" means the swing is at least
# SIGNIFICANCE_Z of that game's own standard errors (impacts.significance_
# floor). Below that we cannot tell the number -- or even its direction --
# from simulation noise, so the stored label is "doesn't matter"; the site
# then splits those into "too close to call" (involves your conference) and
# "can't really affect you" (both teams in the other conference).
# The tank goals (draft position, #1 pick) are judged the same way, but with
# no conference split -- the draft ranks all 32 teams together -- and draft
# position, being in picks, has its own cutoffs (DRAFT_* below).
# ---------------------------------------------------------------------------
TIER_MUST_WIN = "must_win"
TIER_ROOT_HARD = "root_hard"
TIER_A_LITTLE = "a_little"
TIER_DOESNT_MATTER = "doesnt_matter"

MUST_WIN_THRESHOLD = 10.0       # >= 10 points of swing
ROOT_HARD_THRESHOLD = 2.0       # >= 2 points of swing
# "a_little" floor is per-game and per-team; see impacts.significance_floor().

# The draft goal is measured in PICKS, not percentage points, so it needs its
# own cutoffs. Set from the week-10 dry run (Nov 2026, 200k + 40k paired):
# a team's own game moved its average pick by 1.7-3.6 places (more for
# teams near the playoff line, where a loss also costs a playoff spot and so
# drops them into the non-playoff picks). Other games topped out at 0.34
# places, and 95% were under 0.19. So "must win" is in practice a team's own
# game, and "root hard" is roughly the top 5% of everything else.
DRAFT_MUST_WIN_PICKS = 1.0
DRAFT_ROOT_HARD_PICKS = 0.2
# The smallest swing in picks ever called real, however precisely measured.
DRAFT_MIN_FLOOR = 0.02

TIER_LABELS = {
    TIER_MUST_WIN: "Must win",
    TIER_ROOT_HARD: "Root hard",
    TIER_A_LITTLE: "A little",
    TIER_DOESNT_MATTER: "Doesn't matter",
}

# A floor below which we never claim a game matters, however precisely it is
# measured: a tenth of a percentage point. It was 0.25 while every game was
# measured by conditioning (errors ~0.2); paired replays measure this week's
# games to ~0.05, so real effects of 0.1-0.25 points -- which fans asked to see
# as tiebreakers -- would otherwise be hidden by the floor alone.
MIN_NOISE_FLOOR = 0.1

# How many of its own standard errors a game's swing must reach to count as
# real (see impacts.significance_floor). 2.5 means a game with no true effect
# is wrongly called real about 1% of the time, so a "root for X" on a small
# game points the right way. With 200,000 sims a typical current-week game's
# error is about 0.2 points, so effects from roughly 0.5 points up show.
SIGNIFICANCE_Z = 2.5

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------
REASON_OWN_GAME = "own_game"
REASON_DIVISION_RIVAL = "division_rival"
REASON_WILDCARD_COMPETITOR = "wildcard_competitor"
REASON_TOP_SEED_RACE = "top_seed_race"
REASON_TIEBREAKER_EFFECT = "tiebreaker_effect"
REASON_OTHER = "other"
REASON_DRAFT_RIVAL = "draft_rival"

REASON_LABELS = {
    REASON_OWN_GAME: "Your own game",
    REASON_DIVISION_RIVAL: "Division rival",
    REASON_WILDCARD_COMPETITOR: "Wild-card competitor",
    REASON_TOP_SEED_RACE: "#1 seed race",
    REASON_TIEBREAKER_EFFECT: "Tiebreaker effect",
    REASON_OTHER: "Other",
    REASON_DRAFT_RIVAL: "Draft rival",
}

# Tank mode: another team is a "draft rival" when its average projected pick
# is within this many places of yours -- close enough that either of you
# could end up ahead of the other.
DRAFT_RIVAL_PICKS = 4.0

# A team counts as "in the race" when its own playoff odds are neither close to
# locked nor close to dead. Outside this band its games stop being interesting
# to anyone else, because the standings barely move either way.
IN_RACE_MIN_PCT = 5.0
IN_RACE_MAX_PCT = 95.0

# A team is a #1-seed contender at or above this probability.
TOP_SEED_CONTENDER_PCT = 5.0

# The last two are tank mode: "draft" is the average pick (lower is better),
# "top_pick" the chance of holding the #1 overall pick.
GOALS = ("playoffs", "division", "top_seed", "draft", "top_pick")
TANK_GOALS = ("draft", "top_pick")
