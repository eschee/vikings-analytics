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
  * Playoff seeding uses the real NFL tiebreakers (tiebreakers.py), the same
    code validated against the 2022-2025 brackets. Because a simulated season
    produces wins and losses but no scores, the points-based rungs report
    themselves unavailable and the ladder falls through to a coin toss if the
    first six cannot separate the teams. Scores are stripped from the ALREADY
    PLAYED games too, so those rungs are uniformly unavailable rather than
    being decided on a half-season of points.
  * Draft order (draft_order): non-playoff teams pick first, worst record
    first, ties broken by strength of schedule -- the weaker schedule picks
    earlier, as in the NFL -- then at random. The NFL's further rungs
    (division and conference tiebreakers) are not implemented; they decide
    few ties once strength of schedule has been applied. Playoff teams take
    picks 19-32 by record, whereas the NFL orders them by the round they were
    knocked out in -- the playoffs themselves are not simulated.
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
import random
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
    seed_conference,
)
from tiebreakers import Result, SeasonContext
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

# SEASON MODEL SETTINGS -- chosen by season_backtest.py, not by taste.
#
# Replaying 2023-2025 from weeks 6, 10 and 14 showed the previous settings
# (6-week half-life, full predicted spreads, jitter as derived above) were
# overconfident: teams given ~87% to win their division did it 71% of the
# time, and calling every unpriced game a coin flip scored about as well.
# The three changes below beat those settings on playoff Brier score in every
# season tested, and cut the average division calibration gap from 7.6 to 4.4
# points:
#
#   * a 2-week half-life: ratings follow the most recent lines, so they move
#     as fast as the market's view of a team does. (ratings.py keeps 6 weeks
#     for single-game prediction, where its own backtest chose it.)
#   * spreads for unpriced games scaled to 75%: a game a month away is less
#     predictable than its rating-implied spread suggests.
#   * 1.5x the derived jitter: more "we may be wrong about this team" -- the
#     derivation above captures rating error, not the injuries and form swings
#     that also accumulate over the rest of a season.
#
# Change any of these only with a new backtest, and bump MODEL_VERSION in
# hatewatch/config.py when you do.
SEASON_HALF_LIFE_WEEKS = 2.0
SEASON_RATING_SCALE = 0.75
SEASON_JITTER_SD = 1.5 * JITTER_SD

# The four goals a fan might root for. Each maps to a column on SimResult and a
# direction: True means higher is better.
GOALS = {
    "playoffs": ("made_playoffs", True),
    "division": ("won_division", True),
    "top_seed": ("won_top_seed", True),
    "draft": ("draft_pick", False),   # pick 1 is the best outcome
    "top_pick": ("top_pick", True),   # holds the #1 overall pick
}


@dataclass
class PairedImpact:
    """One game replayed both ways inside the same simulated seasons.

    Arrays are (5, n_teams), one row per goal (see PAIRED_GOAL_ROW): for
    playoffs, division, #1 seed and #1 pick, the share of seasons (0-1) in
    which each team reached it; for the draft, the average pick number.
    """
    n: int                    # seasons replayed
    home_mean: np.ndarray     # with the home team forced to win
    away_mean: np.ndarray     # with the away team forced to win
    diff_mean: np.ndarray     # mean of per-season (home - away)
    diff_se: np.ndarray       # standard error of diff_mean


PAIRED_GOAL_ROW = {"playoffs": 0, "division": 1, "top_seed": 2,
                   "top_pick": 3, "draft": 4}


def draft_order(
    wins: np.ndarray,
    made_playoffs: np.ndarray,
    opponents: np.ndarray,
    tie_noise: np.ndarray,
) -> np.ndarray:
    """Every team's draft pick (1 = first overall) in every simulated season.

    `wins` and `made_playoffs` are (n_seasons, n_teams); `opponents` is the
    (n_teams, n_teams) count of games each pair plays all season; `tie_noise`
    is (n_seasons, n_teams) uniform noise for the last-resort random rung.

    The order, earliest pick first:
      1. Teams that missed the playoffs before teams that made them.
      2. Fewer wins (a tie counts half).
      3. Weaker strength of schedule: the combined record of all 17
         opponents. This is the NFL's first draft tiebreaker, and at the top
         of the draft -- where two 3-14 teams are common -- it often decides
         the #1 pick.
      4. Random.

    np.lexsort sorts by the LAST key first, so the keys are listed from the
    least to the most important. Sorting each season's row gives the teams in
    pick order; argsort of that turns it into each team's pick number.
    """
    # Opponents' combined wins over their combined games (17 each).
    sos = (wins @ opponents.T) / (opponents.sum(axis=1) * GAMES_PER_SEASON)
    order = np.lexsort((tie_noise, sos, wins, made_playoffs), axis=-1)
    return (np.argsort(order, axis=-1) + 1).astype(np.int16)


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
    # Per-team outcomes, (n_sims, 32). Filled only on the real-tiebreaker
    # path, which seeds both conferences; None under --simple-tiebreakers.
    team_index: dict[str, int] | None = None
    team_made_playoffs: np.ndarray | None = None
    team_won_division: np.ndarray | None = None
    team_won_top_seed: np.ndarray | None = None
    team_seed: np.ndarray | None = None       # 1-7, or 0 when out
    team_draft_pick: np.ndarray | None = None  # (n_sims, 32), 1 = first overall
    # game_id -> PairedImpact, for the games named by `paired_week`.
    paired: dict | None = None
    real_tiebreakers: bool = True
    coin_tosses: int = 0           # iterations where the ladder ran out
    tiebreaks_resolved: int = 0    # tied groups the ladder had to separate

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
    def top_pick(self) -> np.ndarray:
        """(n_sims,) bool: the target holds the #1 overall pick."""
        return self.draft_pick == 1

    @property
    def mean_draft_pick(self) -> float:
        return float(self.draft_pick.mean())

    def outcome(self, goal: str) -> np.ndarray:
        return getattr(self, GOALS[goal][0])

    @property
    def has_all_teams(self) -> bool:
        return self.team_index is not None

    def team_outcome(self, goal: str, team: str) -> np.ndarray:
        """One team's column of the goal matrix."""
        if not self.has_all_teams:
            raise RuntimeError(
                "per-team outcomes need the real-tiebreaker path"
            )
        col = self.team_index[team]
        if goal == "draft":
            return self.team_draft_pick[:, col].astype(np.float64)
        if goal == "top_pick":
            return self.team_draft_pick[:, col] == 1
        matrix = {
            "playoffs": self.team_made_playoffs,
            "division": self.team_won_division,
            "top_seed": self.team_won_top_seed,
        }[goal]
        return matrix[:, col]

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
    real_tiebreakers: bool = True,
    force: dict[str, str] | None = None,
    as_of_week: int | None = None,
    half_life: float | None = None,
    rating_scale: float | None = None,
    paired_week: int | None = None,
    paired_sims: int = 40_000,
) -> SimResult:
    """Simulate the rest of a season.

    `force` pins specific games to a winner: {game_id: winning_team}. Every
    other game is still drawn normally. This is an INTERVENTION, not a filter:
    it overrides the result without touching the rating draw that produced it,
    which is what makes it a clean check on the conditioning method used for
    impacts.

    `as_of_week` replays a finished season as it stood before that week, for
    backtesting (see season_backtest.py). The model then sees only results
    before that week and betting lines for that week and the next -- the two
    weeks of lines production has on a typical refresh -- and fits its ratings
    from those lines alone. None (the default) is production: the database's
    real played/unplayed state and every line it holds.

    `half_life`, `rating_scale` and `jitter_sd` override the season model
    settings (SEASON_* above) -- for backtesting alternatives. `rating_scale`
    multiplies the predicted spread of every ratings-priced game (weeks with
    no betting line yet); below 1 it pulls those games toward a coin flip.
    Left as None, each takes its production value.

    PAIRED REPLAYS. `paired_week` names a week (production: the current one)
    whose games are also measured by replaying: in the first `paired_sims`
    seasons, each such game's result is flipped and that season re-seeded, so
    every game is seen both ways in otherwise identical seasons. The
    difference is what that game alone does. Because nearly every season comes
    out the same both ways, this is far more precise than comparing different
    seasons (conditioning), and it gives even small effects a reliable
    direction. Results land in SimResult.paired. Only the conferences of the
    game's two teams are re-seeded; the other conference cannot be ranked for
    that game anyway (hatewatch.impacts._other_conference). Requires the real
    tiebreakers.
    """
    teams = load_teams(conn)
    if target not in teams:
        raise SystemExit(f"unknown team {target!r}")

    lines_through = None if as_of_week is None else as_of_week + 1

    fit = None
    if use_ratings:
        from ratings import fit_for_season

        fit = fit_for_season(
            conn,
            season,
            through_week=lines_through,
            half_life=SEASON_HALF_LIFE_WEEKS if half_life is None else half_life,
        )
    if jitter_sd is None:
        jitter_sd = SEASON_JITTER_SD if use_ratings else 0.0
    if rating_scale is None:
        rating_scale = SEASON_RATING_SCALE

    all_games = load_games(conn, season, as_of_week=as_of_week)
    remaining = remaining_game_probs(
        conn,
        season,
        fit=fit,
        as_of_week=as_of_week,
        lines_through_week=lines_through,
    )

    # --- starting point: records already earned -----------------------------
    records = compute_records(all_games, teams)
    abbrs = sorted(teams)
    idx = {a: i for i, a in enumerate(abbrs)}
    n_teams = len(abbrs)

    base = np.array(
        [records[a].wins + 0.5 * records[a].ties for a in abbrs], dtype=np.float64
    )

    scheduled = np.zeros(n_teams, dtype=np.int32)
    # How many times each pair of teams meets this season (division rivals
    # twice), for the draft's strength-of-schedule tiebreaker.
    opponents = np.zeros((n_teams, n_teams), dtype=np.float64)
    for g in all_games:
        if g.home in idx and g.away in idx:
            scheduled[idx[g.home]] += 1
            scheduled[idx[g.away]] += 1
            opponents[idx[g.home], idx[g.away]] += 1
            opponents[idx[g.away], idx[g.home]] += 1
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
            rating_scale * rating_spread[rating_cols]   # predicted spread
            + jitter[:, h] - jitter[:, a]        # correlated rating error
            + rng.normal(0.0, SPREAD_SIGMA, size=(n_sims, rating_cols.size))
        )
        home_wins[:, rating_cols] = margin > 0.0

    # Pin any forced outcomes AFTER the normal draw, so everything else keeps
    # its ordinary distribution.
    if force:
        by_id = {g.game_id: j for j, g in enumerate(remaining)}
        for game_id, winner in force.items():
            if game_id not in by_id:
                raise SystemExit(f"{game_id} is not an unplayed game")
            j = by_id[game_id]
            g = remaining[j]
            if winner not in (g.home, g.away):
                raise SystemExit(
                    f"{winner} does not play in {game_id} ({g.away} at {g.home})"
                )
            home_wins[:, j] = winner == g.home

    wins = np.tile(base, (n_sims, 1))
    for j in range(n_games):
        hw = home_wins[:, j]
        wins[hw, home_idx[j]] += 1.0
        wins[~hw, away_idx[j]] += 1.0

    # --- seed the target's conference ---------------------------------------
    conf = teams[target].conf
    target_i = idx[target]

    # Random tiebreak noise: the simple-tiebreaker path below ranks on
    # `score`, and draft_order uses the same noise as its last rung. Drawn
    # here, in the same place in the random stream as before, so adding the
    # draft's strength-of-schedule rung changes no other result.
    tie_noise = rng.random((n_sims, n_teams))
    score = wins + tie_noise * TIEBREAK_NOISE

    won_division = np.zeros(n_sims, dtype=bool)
    made_playoffs = np.zeros(n_sims, dtype=bool)
    won_top_seed = np.zeros(n_sims, dtype=bool)
    coin_tosses = 0
    tiebreaks_resolved = 0
    paired = None
    team_made = None
    team_div = None
    team_top = None
    team_seed_arr = None

    if real_tiebreakers:
        # Scores are dropped from the played games as well, so every
        # points-based rung is uniformly unavailable instead of being settled
        # on a partial season. home_won carries the result instead.
        played_results = [
            Result(g.home, g.away, home_won=(g.winner == g.home))
            for g in all_games
            if g.played and g.winner is not None
        ]
        played_ties = [
            Result(g.home, g.away, home_won=None)
            for g in all_games
            if g.played and g.winner is None
        ]
        fixed = played_results + played_ties
        rem_home = [g.home for g in remaining]
        rem_away = [g.away for g in remaining]

        # One random stream per (season, conference) for tiebreak coin tosses,
        # rather than one stream for the whole run. A paired replay re-seeds a
        # season with the same stream, so a coin toss that the flipped game
        # did not touch lands the same way both times instead of adding noise.
        def conf_rng(s_i: int, c: str) -> random.Random:
            return random.Random((seed * 1_000_003 + s_i) * 2 + (c == "NFC"))

        conf_cols = {
            c: np.array(
                [idx[a] for a, t in teams.items() if t.conf == c], dtype=np.int32
            )
            for c in ("AFC", "NFC")
        }
        pair_cols = (
            [j for j, g in enumerate(remaining) if g.week == paired_week]
            if paired_week is not None
            else []
        )
        n_pair = min(n_sims, paired_sims) if pair_cols else 0
        # Per paired game: sums of home-forced outcome, away-forced outcome,
        # their difference, and the difference squared -- (5, n_teams) each,
        # rows as in PAIRED_GOAL_ROW.
        pair_acc = {
            j: [np.zeros((5, n_teams)) for _ in range(4)] for j in pair_cols
        }

        # Both conferences, so a single run produces all 32 teams' numbers.
        team_made = np.zeros((n_sims, n_teams), dtype=bool)
        team_div = np.zeros((n_sims, n_teams), dtype=bool)
        team_top = np.zeros((n_sims, n_teams), dtype=bool)
        team_seed_arr = np.zeros((n_sims, n_teams), dtype=np.int8)

        for s_i in range(n_sims):
            hw = home_wins[s_i]
            sim_results = [
                Result(h, a, home_won=bool(w))
                for h, a, w in zip(rem_home, rem_away, hw)
            ]
            ctx = SeasonContext(fixed + sim_results, teams)
            for c in ("AFC", "NFC"):
                seeding = seed_conference(ctx, teams, c, conf_rng(s_i, c))
                for pos, abbr in enumerate(seeding.seeds, start=1):
                    col = idx[abbr]
                    team_made[s_i, col] = True
                    team_seed_arr[s_i, col] = pos
                for abbr in seeding.division_winners:
                    team_div[s_i, idx[abbr]] = True
                team_top[s_i, idx[seeding.seeds[0]]] = True
                for d in seeding.decisions:
                    tiebreaks_resolved += 1
                    if d.step == "coin toss":
                        coin_tosses += 1

            if s_i >= n_pair:
                continue
            # Paired replays: this season again with one game flipped.
            pick = draft_order(
                wins[s_i : s_i + 1], team_made[s_i : s_i + 1], opponents,
                tie_noise[s_i : s_i + 1],
            )[0]
            real_out = np.stack(
                [team_made[s_i], team_div[s_i], team_top[s_i], pick == 1, pick]
            ).astype(np.float64)
            for j in pair_cols:
                flipped = list(sim_results)
                flipped[j] = Result(rem_home[j], rem_away[j], home_won=not hw[j])
                ctx2 = SeasonContext(fixed + flipped, teams)
                alt = real_out.copy()
                for c in {teams[rem_home[j]].conf, teams[rem_away[j]].conf}:
                    alt[:3, conf_cols[c]] = 0
                    seeding = seed_conference(ctx2, teams, c, conf_rng(s_i, c))
                    for abbr in seeding.seeds:
                        alt[0, idx[abbr]] = 1
                    for abbr in seeding.division_winners:
                        alt[1, idx[abbr]] = 1
                    alt[2, idx[seeding.seeds[0]]] = 1
                # The draft: move the flipped game's win to the other team and
                # re-order with the replayed playoff field. Same tie noise, so
                # only what the game changed can move a pick.
                alt_wins = wins[s_i].copy()
                winner, loser = (
                    (home_idx[j], away_idx[j]) if hw[j]
                    else (away_idx[j], home_idx[j])
                )
                alt_wins[winner] -= 1.0
                alt_wins[loser] += 1.0
                alt_pick = draft_order(
                    alt_wins[None, :], alt[0:1].astype(bool), opponents,
                    tie_noise[s_i : s_i + 1],
                )[0]
                alt[3] = alt_pick == 1
                alt[4] = alt_pick
                home_out, away_out = (real_out, alt) if hw[j] else (alt, real_out)
                d = home_out - away_out
                acc = pair_acc[j]
                acc[0] += home_out
                acc[1] += away_out
                acc[2] += d
                acc[3] += d * d

        if n_pair:
            paired = {}
            for j in pair_cols:
                h_sum, a_sum, d_sum, d_sq = pair_acc[j]
                mean = d_sum / n_pair
                var = np.maximum(d_sq - n_pair * mean**2, 0.0) / max(n_pair - 1, 1)
                paired[remaining[j].game_id] = PairedImpact(
                    n=n_pair,
                    home_mean=h_sum / n_pair,
                    away_mean=a_sum / n_pair,
                    diff_mean=mean,
                    diff_se=np.sqrt(var / n_pair),
                )

        made_playoffs = team_made[:, target_i].copy()
        won_division = team_div[:, target_i].copy()
        won_top_seed = team_top[:, target_i].copy()
    else:
        # The old behaviour: win total, then random.
        conf_divisions: dict[str, list[int]] = {}
        for a, t in teams.items():
            if t.conf == conf:
                conf_divisions.setdefault(t.division, []).append(idx[a])
        if len(conf_divisions) != DIVISION_WINNERS_PER_CONF:
            raise SystemExit(
                f"{conf}: expected 4 divisions, found {len(conf_divisions)}"
            )

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

        winner_score = np.where(conf_is_winner, conf_score, -np.inf)
        top_team = conf_cols[np.argmax(winner_score, axis=1)]
        won_top_seed = top_team == target_i

    # --- draft order ----------------------------------------------------------
    # After seeding, because playoff teams pick last. The simple-tiebreaker
    # path only seeds one conference, so there it falls back to record alone.
    all_draft_picks = draft_order(
        wins,
        team_made if team_made is not None
        else np.zeros((n_sims, n_teams), dtype=bool),
        opponents,
        tie_noise,
    )
    draft_pick = all_draft_picks[:, target_i]

    result = SimResult(
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
        real_tiebreakers=real_tiebreakers,
        coin_tosses=coin_tosses,
        tiebreaks_resolved=tiebreaks_resolved,
        team_index=dict(idx) if team_made is not None else None,
        team_made_playoffs=team_made,
        team_won_division=team_div,
        team_won_top_seed=team_top,
        team_seed=team_seed_arr,
        team_draft_pick=all_draft_picks if team_made is not None else None,
        paired=paired,
    )
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--sims", type=int, default=20_000)
    ap.add_argument("--team", default="MIN")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--no-ratings", action="store_true",
                    help="coin-flip unpriced games (the old v1 behaviour)")
    ap.add_argument("--jitter-sd", type=float,
                    help=f"rating jitter in points (default {SEASON_JITTER_SD:.2f})")
    ap.add_argument("--simple-tiebreakers", action="store_true",
                    help="win total then random, instead of the NFL ladder")
    args = ap.parse_args()

    with connect() as conn:
        res = simulate(
            conn, args.season, args.sims, args.team, args.seed,
            use_ratings=not args.no_ratings, jitter_sd=args.jitter_sd,
            real_tiebreakers=not args.simple_tiebreakers,
        )
        counts = method_counts(res.games)

    print(f"=== {args.season}: {res.n_sims:,} simulations ===")
    print(f"  remaining games : {len(res.games)}")
    print(f"  pricing         : "
          + ", ".join(f"{m}={c}" for m, c in counts.items() if c))
    print(f"  rating jitter   : {res.jitter_sd:.2f} points"
          + ("" if res.used_ratings else " (ratings off)"))
    print(f"  tiebreakers     : "
          + ("real NFL ladder" if res.real_tiebreakers else "simple (win%, random)"))
    if res.real_tiebreakers and res.tiebreaks_resolved:
        pct = 100.0 * res.coin_tosses / res.tiebreaks_resolved
        print(f"  tiebreaks       : {res.tiebreaks_resolved:,} resolved, "
              f"{res.coin_tosses:,} needed a coin toss ({pct:.1f}%)")
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
