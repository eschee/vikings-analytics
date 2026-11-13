"""Records and standings for any season.

Computes overall, division and conference records from the games table, then
orders teams into division standings and playoff seeds.

TIEBREAKERS: the real NFL procedures, implemented in tiebreakers.py. Teams
tied on record are separated by head-to-head, division record, common games,
conference record, strength of victory, strength of schedule and the
points-based steps, with a coin toss only if all of them come out level.
Seeding among division winners and among wild-card contenders uses the
different-divisions ladder, including the rule that division rivals are
settled between themselves before either can compete for a wild card.

The old behaviour (win percentage, then random) is kept behind
--simple-tiebreakers for comparison.

Usage:
    python analysis/standings.py --season 2026
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from dataclasses import dataclass, field

import psycopg
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tiebreakers import (
    DIVISION_LADDER,
    WILDCARD_LADDER,
    Decision,
    Result,
    SeasonContext,
    rank_teams,
    rank_wildcards,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# A conference sends 4 division winners plus 3 wild cards to the playoffs.
DIVISION_WINNERS_PER_CONF = 4
WILD_CARDS_PER_CONF = 3
PLAYOFF_TEAMS_PER_CONF = DIVISION_WINNERS_PER_CONF + WILD_CARDS_PER_CONF


@dataclass(frozen=True)
class Team:
    abbr: str
    name: str
    conf: str
    division: str


@dataclass(frozen=True)
class Game:
    game_id: str
    week: int
    home: str
    away: str
    home_score: int | None
    away_score: int | None

    @property
    def played(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def winner(self) -> str | None:
        """Winning team abbreviation, or None for a tie or an unplayed game."""
        if not self.played or self.home_score == self.away_score:
            return None
        return self.home if self.home_score > self.away_score else self.away


@dataclass
class Record:
    """Win/loss/tie splits for one team."""

    team: str
    wins: int = 0
    losses: int = 0
    ties: int = 0
    div_wins: int = 0
    div_losses: int = 0
    div_ties: int = 0
    conf_wins: int = 0
    conf_losses: int = 0
    conf_ties: int = 0

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.ties

    @staticmethod
    def _pct(w: int, l: int, t: int) -> float:
        """NFL win percentage counts a tie as half a win."""
        total = w + l + t
        return (w + 0.5 * t) / total if total else 0.0

    @property
    def win_pct(self) -> float:
        return self._pct(self.wins, self.losses, self.ties)

    @property
    def div_pct(self) -> float:
        return self._pct(self.div_wins, self.div_losses, self.div_ties)

    @property
    def conf_pct(self) -> float:
        return self._pct(self.conf_wins, self.conf_losses, self.conf_ties)

    def __str__(self) -> str:
        rec = f"{self.wins}-{self.losses}" + (f"-{self.ties}" if self.ties else "")
        return f"{self.team} {rec} ({self.win_pct:.3f})"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def connect() -> psycopg.Connection:
    load_dotenv(os.path.join(HERE, "..", ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL is not set. Locally it comes from .env; in CI it "
            "comes from the environment, so check that the workflow's secret "
            "exists and is spelled the same way the workflow reads it."
        )
    return psycopg.connect(url)


def load_teams(conn: psycopg.Connection) -> dict[str, Team]:
    """The current 32 teams. is_current filters out the legacy LAR/OAK/SD/STL
    rows, which would otherwise put six teams in the NFC West."""
    rows = conn.execute(
        """
        SELECT team_abbr, team_name, team_conf, team_division
        FROM teams WHERE is_current ORDER BY team_abbr
        """
    ).fetchall()
    teams = {r[0]: Team(*r) for r in rows}
    if len(teams) != 32:
        raise SystemExit(f"expected 32 current teams, found {len(teams)}")
    return teams


def load_games(conn: psycopg.Connection, season: int) -> list[Game]:
    """Regular-season games only: playoff games don't count toward records."""
    rows = conn.execute(
        """
        SELECT game_id, week, home_team, away_team, home_score, away_score
        FROM games
        WHERE season = %s AND game_type = 'REG'
        ORDER BY week, game_id
        """,
        (season,),
    ).fetchall()
    return [Game(*r) for r in rows]


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

def compute_records(
    games: list[Game], teams: dict[str, Team]
) -> dict[str, Record]:
    """Walk the completed games once, crediting both teams in each.

    A game counts toward the division record only when both teams share a
    division, and toward the conference record when they share a conference.
    """
    records = {abbr: Record(team=abbr) for abbr in teams}

    for g in games:
        if not g.played:
            continue
        if g.home not in teams or g.away not in teams:
            continue  # defensive: unknown abbreviation

        same_div = teams[g.home].division == teams[g.away].division
        same_conf = teams[g.home].conf == teams[g.away].conf
        home, away = records[g.home], records[g.away]

        if g.home_score == g.away_score:
            home.ties += 1
            away.ties += 1
            if same_div:
                home.div_ties += 1
                away.div_ties += 1
            if same_conf:
                home.conf_ties += 1
                away.conf_ties += 1
            continue

        winner, loser = (home, away) if g.home_score > g.away_score else (away, home)
        winner.wins += 1
        loser.losses += 1
        if same_div:
            winner.div_wins += 1
            loser.div_losses += 1
        if same_conf:
            winner.conf_wins += 1
            loser.conf_losses += 1

    return records


# ---------------------------------------------------------------------------
# Ordering and seeding
# ---------------------------------------------------------------------------

def build_context(
    games: list[Game], teams: dict[str, Team]
) -> SeasonContext:
    """Turn completed games into the structure the tiebreakers read."""
    results = [
        Result(g.home, g.away, g.home_score, g.away_score)
        for g in games
        if g.played
    ]
    return SeasonContext(results, teams)


# --- the simple (pre-tiebreaker) ordering, kept for comparison -------------

def _simple_key(rec: Record, rng: random.Random) -> tuple[float, float]:
    return (-rec.win_pct, rng.random())


def order_teams_simple(
    abbrs: list[str], records: dict[str, Record], rng: random.Random
) -> list[str]:
    return sorted(abbrs, key=lambda a: _simple_key(records[a], rng))


# --- real NFL ordering -----------------------------------------------------

def teams_by_division(teams: dict[str, Team], conf: str | None = None
                      ) -> dict[str, list[str]]:
    by_div: dict[str, list[str]] = {}
    for abbr, team in teams.items():
        if conf and team.conf != conf:
            continue
        by_div.setdefault(team.division, []).append(abbr)
    return dict(sorted(by_div.items()))


def division_standings(
    ctx: SeasonContext,
    teams: dict[str, Team],
    rng: random.Random,
) -> tuple[dict[str, list[str]], list[Decision]]:
    """Each division ordered best to worst, using the division ladder."""
    out: dict[str, list[str]] = {}
    decisions: list[Decision] = []
    for div, abbrs in teams_by_division(teams).items():
        order, ds = rank_teams(abbrs, ctx, DIVISION_LADDER, rng)
        out[div] = order
        decisions.extend(ds)
    return out, decisions


@dataclass
class Seeding:
    conf: str
    seeds: list[str]                 # 7 teams, seed 1 first
    division_winners: list[str]      # seeds 1-4, in order
    wild_cards: list[str]            # seeds 5-7, in order
    decisions: list[Decision] = field(default_factory=list)

    def seed_of(self, team: str) -> int | None:
        return self.seeds.index(team) + 1 if team in self.seeds else None


def seed_conference(
    ctx: SeasonContext,
    teams: dict[str, Team],
    conf: str,
    rng: random.Random,
) -> Seeding:
    """Build one conference's playoff field, seeds 1-7.

    Three stages, each with its own rule:
      1. Win each division -- the DIVISION ladder, since these are rivals.
      2. Order the four winners into seeds 1-4 -- the WILD-CARD ladder,
         because they come from different divisions.
      3. Fill seeds 5-7 from everyone left -- the wild-card procedure,
         including the division-first rule.
    """
    divisions = teams_by_division(teams, conf)
    if len(divisions) != DIVISION_WINNERS_PER_CONF:
        raise SystemExit(f"{conf}: expected 4 divisions, found {len(divisions)}")

    decisions: list[Decision] = []
    winners: list[str] = []
    runners_up: list[str] = []
    for div, abbrs in divisions.items():
        order, ds = rank_teams(abbrs, ctx, DIVISION_LADDER, rng)
        decisions.extend(ds)
        winners.append(order[0])
        runners_up.extend(order[1:])

    seeded_winners, ds = rank_teams(winners, ctx, WILDCARD_LADDER, rng)
    decisions.extend(ds)

    wc_order, ds = rank_wildcards(runners_up, ctx, rng)
    decisions.extend(ds)
    wild_cards = wc_order[:WILD_CARDS_PER_CONF]

    return Seeding(
        conf=conf,
        seeds=seeded_winners + wild_cards,
        division_winners=seeded_winners,
        wild_cards=wild_cards,
        decisions=decisions,
    )


def playoff_seeds(
    ctx: SeasonContext,
    teams: dict[str, Team],
    conf: str,
    rng: random.Random,
) -> list[str]:
    """The 7 playoff teams in seed order."""
    return seed_conference(ctx, teams, conf, rng).seeds


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for coin tosses")
    ap.add_argument("--show-decisions", action="store_true",
                    help="print which step decided each tiebreak")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    with connect() as conn:
        teams = load_teams(conn)
        games = load_games(conn, args.season)

    played = sum(1 for g in games if g.played)
    records = compute_records(games, teams)
    ctx = build_context(games, teams)
    print(f"=== {args.season} standings ({played}/{len(games)} games played) ===")

    div_order, _ = division_standings(ctx, teams, rng)
    for div, order in div_order.items():
        print(f"\n{div}")
        print(f"  {'team':<5} {'overall':>9} {'pct':>6} {'div':>7} {'conf':>7} "
              f"{'SOV':>6} {'SOS':>6}")
        for abbr in order:
            r = records[abbr]
            overall = f"{r.wins}-{r.losses}" + (f"-{r.ties}" if r.ties else "")
            div_rec = f"{r.div_wins}-{r.div_losses}" + (
                f"-{r.div_ties}" if r.div_ties else "")
            conf_rec = f"{r.conf_wins}-{r.conf_losses}" + (
                f"-{r.conf_ties}" if r.conf_ties else "")
            print(f"  {abbr:<5} {overall:>9} {r.win_pct:>6.3f} {div_rec:>7} "
                  f"{conf_rec:>7} {ctx.strength_of_victory(abbr):>6.3f} "
                  f"{ctx.strength_of_schedule(abbr):>6.3f}")

    for conf in ("AFC", "NFC"):
        seeding = seed_conference(ctx, teams, conf, rng)
        print(f"\n{conf} seeds (real NFL tiebreakers)")
        for i, abbr in enumerate(seeding.seeds, start=1):
            tag = "div winner" if i <= DIVISION_WINNERS_PER_CONF else "wild card"
            print(f"  {i}. {abbr:<4} {records[abbr].win_pct:.3f}  {tag}")
        if args.show_decisions and seeding.decisions:
            print(f"  tiebreaks applied:")
            for d in seeding.decisions:
                skipped = (f"  [skipped: {', '.join(d.skipped)}]"
                           if d.skipped else "")
                print(f"    {'/'.join(d.group):<20} -> {d.winner:<4} "
                      f"by {d.step}{skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
