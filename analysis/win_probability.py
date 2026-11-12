"""Turn betting markets into win probabilities for unplayed games.

Three methods, in priority order:

1. MONEYLINE (best). American odds convert to an implied probability:
       negative odds (favorite, e.g. -150): p = |odds| / (|odds| + 100)
       positive odds (underdog, e.g. +130): p = 100  / (odds + 100)
   Both sides' implied probabilities sum to MORE than 1 -- that excess is the
   bookmaker's margin, the "vig" or overround. Measured across the 1,275
   priced games in this database it averages 1.039, i.e. about 3.9%. We remove
   it by normalising the pair so they sum to 1:
       p_home = raw_home / (raw_home + raw_away)
   This is the proportional (or "multiplicative") de-vig. It assumes the margin
   is spread evenly across both sides, which is the standard simple treatment.

2. SPREAD (fallback). The spread is the market's expected home margin of
   victory. Treat the actual margin as normally distributed around it:
       p_home = Phi(spread_line / sigma)
   where Phi is the standard normal CDF and sigma is the standard deviation of
   (actual margin - spread). Measured from the 1,275 completed games in this
   database with a spread: mean residual 0.425 points (so the spread is very
   nearly unbiased) and sigma = 12.38. Run with --calibrate to re-measure.

   NOTE ON SIGN: in nflverse, a POSITIVE spread_line means the HOME team is
   favoured by that many points. Verified two ways against this data -- the
   favourite wins 67.7% of the time under this reading (vs 32.3% inverted), and
   the sign agrees with which side is the moneyline favourite in 99.5% of
   games.

3. COIN FLIP (last resort). No market at all: 0.50. This is not a real
   forecast, just a neutral placeholder. It ignores team quality entirely, so
   a schedule that is mostly unpriced produces mushy, over-even odds.

Usage:
    python analysis/win_probability.py --season 2026
    python analysis/win_probability.py --calibrate
"""

from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass

import psycopg
from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))

# Standard deviation of (actual home margin - spread_line), in points.
# Measured from completed 2022-2026 games in this database; see --calibrate.
SPREAD_SIGMA = 12.38

METHOD_MONEYLINE = "moneyline"
METHOD_SPREAD = "spread"
METHOD_COIN_FLIP = "coin_flip"
METHODS = (METHOD_MONEYLINE, METHOD_SPREAD, METHOD_COIN_FLIP)


@dataclass(frozen=True)
class GameProb:
    game_id: str
    week: int
    home: str
    away: str
    p_home: float
    method: str

    @property
    def p_away(self) -> float:
        return 1.0 - self.p_home


def normal_cdf(z: float) -> float:
    """Standard normal CDF, via erf so we don't need scipy."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def implied_prob_american(odds: float) -> float:
    """Convert American moneyline odds to a raw implied probability (with vig)."""
    if odds < 0:
        return -odds / (-odds + 100.0)
    return 100.0 / (odds + 100.0)


def prob_from_moneyline(home_ml: float, away_ml: float) -> float:
    """De-vigged P(home win) from a pair of moneylines."""
    raw_home = implied_prob_american(home_ml)
    raw_away = implied_prob_american(away_ml)
    total = raw_home + raw_away
    if total <= 0:
        raise ValueError(f"degenerate moneylines: {home_ml}, {away_ml}")
    return raw_home / total


def prob_from_spread(spread_line: float, sigma: float = SPREAD_SIGMA) -> float:
    """P(home win) implied by the spread. Positive spread_line = home favoured."""
    return normal_cdf(spread_line / sigma)


def win_probability(
    *,
    home_moneyline: float | None,
    away_moneyline: float | None,
    spread_line: float | None,
    sigma: float = SPREAD_SIGMA,
) -> tuple[float, str]:
    """Best available P(home win), plus which method produced it."""
    if home_moneyline is not None and away_moneyline is not None:
        return prob_from_moneyline(home_moneyline, away_moneyline), METHOD_MONEYLINE
    if spread_line is not None:
        return prob_from_spread(spread_line, sigma), METHOD_SPREAD
    return 0.5, METHOD_COIN_FLIP


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def connect() -> psycopg.Connection:
    load_dotenv(os.path.join(HERE, "..", ".env"))
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is not set (expected in .env)")
    return psycopg.connect(url)


def remaining_game_probs(
    conn: psycopg.Connection, season: int, sigma: float = SPREAD_SIGMA
) -> list[GameProb]:
    """Win probabilities for every unplayed regular-season game."""
    rows = conn.execute(
        """
        SELECT game_id, week, home_team, away_team,
               home_moneyline, away_moneyline, spread_line
        FROM games
        WHERE season = %s AND game_type = 'REG' AND home_score IS NULL
        ORDER BY week, game_id
        """,
        (season,),
    ).fetchall()

    out = []
    for game_id, week, home, away, h_ml, a_ml, spread in rows:
        p, method = win_probability(
            home_moneyline=float(h_ml) if h_ml is not None else None,
            away_moneyline=float(a_ml) if a_ml is not None else None,
            spread_line=float(spread) if spread is not None else None,
            sigma=sigma,
        )
        out.append(GameProb(game_id, week, home, away, p, method))
    return out


def method_counts(probs: list[GameProb]) -> dict[str, int]:
    counts = {m: 0 for m in METHODS}
    for p in probs:
        counts[p.method] += 1
    return counts


def calibrate(conn: psycopg.Connection) -> tuple[float, float, int]:
    """Re-measure the spread residual from completed games: (mean, sigma, n)."""
    rows = conn.execute(
        """
        SELECT result, spread_line FROM games
        WHERE home_score IS NOT NULL AND spread_line IS NOT NULL
          AND result IS NOT NULL AND game_type = 'REG'
        """
    ).fetchall()
    resid = [float(r) - float(s) for r, s in rows]
    n = len(resid)
    if n < 2:
        raise SystemExit("not enough completed games with a spread to calibrate")
    mean = sum(resid) / n
    var = sum((x - mean) ** 2 for x in resid) / (n - 1)
    return mean, math.sqrt(var), n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--calibrate", action="store_true")
    args = ap.parse_args()

    with connect() as conn:
        if args.calibrate:
            mean, sigma, n = calibrate(conn)
            print(f"spread residual over {n} completed games:")
            print(f"  mean  {mean:+.3f} points (bias; ~0 means the spread is fair)")
            print(f"  sigma {sigma:.3f} points")
            print(f"\nmodule currently uses SPREAD_SIGMA = {SPREAD_SIGMA}")
            return 0

        probs = remaining_game_probs(conn, args.season)
        counts = method_counts(probs)
        print(f"=== {args.season}: win probabilities for {len(probs)} remaining games ===\n")
        for m in METHODS:
            print(f"  {m:<10} {counts[m]:>4}")

        print(f"\n  sample (most lopsided first)")
        for g in sorted(probs, key=lambda g: -abs(g.p_home - 0.5))[:8]:
            print(
                f"    wk{g.week:<3} {g.away:>3} @ {g.home:<3}  "
                f"P(home)={g.p_home:.3f}  [{g.method}]"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
