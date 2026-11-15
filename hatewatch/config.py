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
MODEL_VERSION = "v5.1-per-game-significance"   # v5 model + per-game tiering, Nov 2026

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
# The draft goal is not yes/no, so it keeps the older control-group floor
# (impacts.noise_floor).
# ---------------------------------------------------------------------------
TIER_MUST_WIN = "must_win"
TIER_ROOT_HARD = "root_hard"
TIER_A_LITTLE = "a_little"
TIER_DOESNT_MATTER = "doesnt_matter"

MUST_WIN_THRESHOLD = 10.0       # >= 10 points of swing
ROOT_HARD_THRESHOLD = 2.0       # >= 2 points of swing
# "a_little" floor is per-game and per-team; see impacts.significance_floor().

TIER_LABELS = {
    TIER_MUST_WIN: "Must win",
    TIER_ROOT_HARD: "Root hard",
    TIER_A_LITTLE: "A little",
    TIER_DOESNT_MATTER: "Doesn't matter",
}

# A floor below which we never claim a game matters, even if a run's measured
# noise floor comes out smaller than this. Guards against a lucky run reporting
# a tiny control-group maximum and then promoting pure noise to "a little".
MIN_NOISE_FLOOR = 0.25

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

REASON_LABELS = {
    REASON_OWN_GAME: "Your own game",
    REASON_DIVISION_RIVAL: "Division rival",
    REASON_WILDCARD_COMPETITOR: "Wild-card competitor",
    REASON_TOP_SEED_RACE: "#1 seed race",
    REASON_TIEBREAKER_EFFECT: "Tiebreaker effect",
    REASON_OTHER: "Other",
}

# A team counts as "in the race" when its own playoff odds are neither close to
# locked nor close to dead. Outside this band its games stop being interesting
# to anyone else, because the standings barely move either way.
IN_RACE_MIN_PCT = 5.0
IN_RACE_MAX_PCT = 95.0

# A team is a #1-seed contender at or above this probability.
TOP_SEED_CONTENDER_PCT = 5.0

GOALS = ("playoffs", "division", "top_seed", "draft")
