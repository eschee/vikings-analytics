"""Records and standings for any season.

Computes overall, division and conference records from the games table, then
orders teams into division standings and playoff seeds.

TIEBREAKERS: this uses win percentage, then a random draw. The real NFL
tiebreaker ladder (head-to-head, division record, common games, conference
record, strength of victory, strength of schedule, then coin flip) is not
implemented yet. Division and conference records ARE computed here, so the
first few rungs of that ladder can be added without touching the data layer.
A random tiebreak is deliberate rather than lazy: in a Monte Carlo simulation
it gives every tied team an equal share of the contested seed, which is a
defensible neutral prior. It does mean two runs can disagree on a knife-edge
tie.

Usage:
    python analysis/standings.py --season 2026
"""

from __future__ import annotations

import argparse
import os
import random
from dataclasses import dataclass, field

import psycopg
from dotenv import load_dotenv

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
        raise SystemExit("DATABASE_URL is not set (expected in .env)")
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

def _sort_key(rec: Record, rng: random.Random) -> tuple[float, float]:
    """Win percentage, then a random draw.

    See the module docstring: the real NFL ladder goes here eventually.
    """
    return (-rec.win_pct, rng.random())


def order_teams(
    abbrs: list[str], records: dict[str, Record], rng: random.Random
) -> list[str]:
    return sorted(abbrs, key=lambda a: _sort_key(records[a], rng))


def division_standings(
    records: dict[str, Record], teams: dict[str, Team], rng: random.Random
) -> dict[str, list[str]]:
    """Each division's teams, best to worst."""
    by_div: dict[str, list[str]] = {}
    for abbr, team in teams.items():
        by_div.setdefault(team.division, []).append(abbr)
    return {d: order_teams(a, records, rng) for d, a in sorted(by_div.items())}


def playoff_seeds(
    records: dict[str, Record],
    teams: dict[str, Team],
    conf: str,
    rng: random.Random,
) -> list[str]:
    """The 7 playoff teams in one conference, in seed order.

    Division winners take seeds 1-4 ordered by record; the best three
    non-winners take seeds 5-7.
    """
    divisions = {
        d: order for d, order in division_standings(records, teams, rng).items()
        if d.startswith(conf)
    }
    if len(divisions) != DIVISION_WINNERS_PER_CONF:
        raise SystemExit(f"{conf}: expected 4 divisions, found {len(divisions)}")

    winners = [order[0] for order in divisions.values()]
    others = [a for order in divisions.values() for a in order[1:]]

    seeded_winners = order_teams(winners, records, rng)
    wild_cards = order_teams(others, records, rng)[:WILD_CARDS_PER_CONF]
    return seeded_winners + wild_cards


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--seed", type=int, default=0, help="RNG seed for tiebreaks")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    with connect() as conn:
        teams = load_teams(conn)
        games = load_games(conn, args.season)

    played = sum(1 for g in games if g.played)
    records = compute_records(games, teams)
    print(f"=== {args.season} standings ({played}/{len(games)} games played) ===")

    for div, order in division_standings(records, teams, rng).items():
        print(f"\n{div}")
        print(f"  {'team':<5} {'overall':>9} {'pct':>6} {'div':>7} {'conf':>7}")
        for abbr in order:
            r = records[abbr]
            overall = f"{r.wins}-{r.losses}" + (f"-{r.ties}" if r.ties else "")
            div_rec = f"{r.div_wins}-{r.div_losses}" + (f"-{r.div_ties}" if r.div_ties else "")
            conf_rec = f"{r.conf_wins}-{r.conf_losses}" + (f"-{r.conf_ties}" if r.conf_ties else "")
            print(f"  {abbr:<5} {overall:>9} {r.win_pct:>6.3f} {div_rec:>7} {conf_rec:>7}")

    for conf in ("AFC", "NFC"):
        seeds = playoff_seeds(records, teams, conf, rng)
        print(f"\n{conf} seeds if the season ended today (win pct, random tiebreak)")
        for i, abbr in enumerate(seeds, start=1):
            tag = "div winner" if i <= DIVISION_WINNERS_PER_CONF else "wild card"
            print(f"  {i}. {abbr:<4} {records[abbr].win_pct:.3f}  {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
