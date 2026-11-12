"""Backtest the ratings model against the market and against a coin flip.

THE TEST

Fit ratings using only games through a cutoff week, then predict every game
after it -- data the fit never saw. Three forecasts are compared on the same
games:

  * ratings  : P(home) = Phi(predicted_spread / sigma), the model
  * market   : P(home) = Phi(actual_closing_spread / sigma), the ceiling
  * coin flip: P(home) = 0.50, the floor and the status quo

The market line is the benchmark that matters. It is what the model is trying
to approximate for games that have no line yet, so "how close to market" is the
real question; beating the market is not expected and would be suspicious.

METRICS

  * Brier score: mean squared error of the probability. Lower is better.
    A coin flip scores exactly 0.25 on any set of games, which makes it a
    convenient reference point.
  * Log loss: punishes confident errors far more harshly. Lower is better.
  * Accuracy: how often the favoured side won. Easy to read, but blind to
    whether the probability was well-calibrated.
  * Spread MAE: mean absolute error of the predicted spread against the actual
    closing line, in points. This isolates the ratings from the probability
    conversion.

Ties are excluded from probability scoring: the forecasts are binary.

HYPERPARAMETERS

--grid searches half-life and ridge on one season. Because that makes the
chosen values in-sample for *selection*, --validate then re-scores the winning
configuration on seasons the search never touched.

Usage:
    python analysis/backtest.py                        # 2025, cutoff week 8
    python analysis/backtest.py --grid
    python analysis/backtest.py --validate
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from dataclasses import dataclass

import numpy as np
import psycopg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ratings import HALF_LIFE_WEEKS, RIDGE_LAMBDA, fit_for_season
from standings import connect, load_teams
from win_probability import SPREAD_SIGMA, normal_cdf

EPS = 1e-12


@dataclass
class Score:
    label: str
    n: int
    brier: float
    log_loss: float
    accuracy: float
    spread_mae: float | None = None

    def row(self) -> str:
        mae = f"{self.spread_mae:>9.2f}" if self.spread_mae is not None else f"{'-':>9}"
        return (f"  {self.label:<12} {self.n:>5} {self.brier:>8.4f} "
                f"{self.log_loss:>9.4f} {self.accuracy * 100:>8.1f}% {mae}")


def score(
    label: str,
    probs: list[float],
    home_won: list[bool],
    pred_spreads: list[float] | None = None,
    actual_spreads: list[float] | None = None,
) -> Score:
    n = len(probs)
    brier = sum((p - (1.0 if w else 0.0)) ** 2 for p, w in zip(probs, home_won)) / n
    ll = -sum(
        math.log(max(p if w else 1 - p, EPS)) for p, w in zip(probs, home_won)
    ) / n
    # A 0.5 forecast picks no side, so it scores half. This case must be
    # tested BEFORE comparing (p > 0.5) to the outcome: for p == 0.5 that
    # comparison is False == False for every away win, which would hand the
    # coin flip full credit on those games and score it around 75%.
    def credit(p: float, w: bool) -> float:
        if p == 0.5:
            return 0.5
        return 1.0 if ((p > 0.5) == w) else 0.0

    acc = sum(credit(p, w) for p, w in zip(probs, home_won)) / n
    mae = None
    if pred_spreads is not None and actual_spreads is not None:
        mae = sum(abs(p - a) for p, a in zip(pred_spreads, actual_spreads)) / len(
            pred_spreads
        )
    return Score(label, n, brier, ll, acc, mae)


def load_test_games(
    conn: psycopg.Connection, season: int, after_week: int
) -> list[tuple[int, str, str, float, int]]:
    """Completed games after the cutoff, with a closing line. (week, home, away,
    spread_line, result)"""
    rows = conn.execute(
        """
        SELECT week, home_team, away_team, spread_line, result
        FROM games
        WHERE season = %s AND game_type = 'REG' AND week > %s
          AND home_score IS NOT NULL AND spread_line IS NOT NULL
          AND result IS NOT NULL
        ORDER BY week, game_id
        """,
        (season, after_week),
    ).fetchall()
    return [(int(w), h, a, float(s), int(r)) for w, h, a, s, r in rows]


def run_backtest(
    conn: psycopg.Connection,
    season: int,
    split_week: int = 8,
    half_life: float = HALF_LIFE_WEEKS,
    ridge: float = RIDGE_LAMBDA,
    sigma: float = SPREAD_SIGMA,
) -> tuple[list[Score], int]:
    """Fit through split_week, score the rest. Returns (scores, n_fit_games)."""
    fit = fit_for_season(
        conn, season, through_week=split_week, half_life=half_life, ridge=ridge,
        ref_week=split_week,
    )
    test = load_test_games(conn, season, split_week)

    model_p, market_p, flip_p, won = [], [], [], []
    pred_sp, actual_sp = [], []
    for week, home, away, spread, result in test:
        if result == 0:
            continue  # tie: no binary outcome to score
        ps = fit.predict_spread(home, away)
        model_p.append(normal_cdf(ps / sigma))
        market_p.append(normal_cdf(spread / sigma))
        flip_p.append(0.5)
        won.append(result > 0)
        pred_sp.append(ps)
        actual_sp.append(spread)

    if not won:
        raise SystemExit(f"{season}: no scorable games after week {split_week}")

    scores = [
        score("ratings", model_p, won, pred_sp, actual_sp),
        score("market", market_p, won),
        score("coin flip", flip_p, won),
    ]
    return scores, fit.n_games


def print_scores(scores: list[Score], header: str) -> None:
    print(header)
    print(f"  {'forecast':<12} {'n':>5} {'brier':>8} {'log loss':>9} "
          f"{'acc':>9} {'sprd MAE':>9}")
    print("  " + "-" * 56)
    for s in scores:
        print(s.row())


def grid_search(conn: psycopg.Connection, season: int, split_week: int) -> tuple[float, float]:
    half_lives = [2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 1e6]
    ridges = [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
    print(f"=== grid search on {season}, fit through week {split_week} ===")
    print(f"  objective: Brier score on weeks {split_week + 1}-18\n")
    print(f"  {'half-life':>10} " + " ".join(f"{r:>7}" for r in ridges))
    best = (None, None, 9e9)
    for hl in half_lives:
        cells = []
        for rg in ridges:
            scores, _ = run_backtest(conn, season, split_week, hl, rg)
            b = scores[0].brier
            cells.append(f"{b:>7.4f}")
            if b < best[2]:
                best = (hl, rg, b)
        label = "none" if hl > 1000 else f"{hl:g}"
        print(f"  {label:>10} " + " ".join(cells))
    hl, rg, b = best
    label = "none (flat)" if hl > 1000 else f"{hl:g} weeks"
    print(f"\n  best: half-life {label}, ridge {rg:g} -> Brier {b:.4f}")
    return hl, rg


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--split-week", type=int, default=8)
    ap.add_argument("--half-life", type=float, default=HALF_LIFE_WEEKS)
    ap.add_argument("--ridge", type=float, default=RIDGE_LAMBDA)
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--validate", action="store_true",
                    help="re-score the current defaults on other seasons")
    args = ap.parse_args()

    with connect() as conn:
        if args.grid:
            grid_search(conn, args.season, args.split_week)
            return 0

        if args.validate:
            print(f"=== out-of-sample validation ===")
            print(f"  config: half-life {args.half_life:g} weeks, "
                  f"ridge {args.ridge:g}, cutoff week {args.split_week}\n")
            for season in (2022, 2023, 2024, 2025):
                scores, n_fit = run_backtest(
                    conn, season, args.split_week, args.half_life, args.ridge
                )
                print_scores(
                    scores,
                    f"{season} (fit on {n_fit} games through week {args.split_week})",
                )
                print()
            return 0

        scores, n_fit = run_backtest(
            conn, args.season, args.split_week, args.half_life, args.ridge
        )
        print(f"=== backtest: {args.season}, fit through week {args.split_week} ===")
        print(f"  fitted on {n_fit} priced games, "
              f"half-life {args.half_life:g} weeks, ridge {args.ridge:g}\n")
        print_scores(scores, f"  weeks {args.split_week + 1}-18:")
        flip, model, market = scores[2].brier, scores[0].brier, scores[1].brier
        print(f"\n  Brier improvement over a coin flip: "
              f"{(flip - model) / flip * 100:.1f}%")
        gap = (flip - market)
        if gap > 0:
            print(f"  share of the market's edge captured: "
                  f"{(flip - model) / gap * 100:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
