# Hatewatch — project notes

Read this at the start of a session. It is the state of the project as of
2026-11-13, after PR #8. `CLAUDE.md` holds the rules; this holds the context.

---

## Vision

A "who to root for" site. On any given week a fan knows their own team's game
matters — what they do not know is which of the other thirteen games they
should care about, which way, and how much.

Hatewatch answers that. For each remaining game it says which result helps
your team, ranked by how much it moves three things: **making the playoffs**,
**winning the division**, and **the #1 seed**.

- **Every team.** Every number is computed and stored for all 32 teams; the
  site serves `/[team]` for each, and the header's team picker switches
  between them. `/` still redirects to the Vikings.
- **Simple first, detail on tap.** The collapsed row shows who to root for and
  a three-dot meter — no numbers. Tapping opens the reason in plain English,
  the per-goal impacts, and the chance the team you want actually wins.
- **Mobile-first.** A 480px column, centred on desktop. The phone layout is
  the real layout.

---

## Architecture

```
nflverse (nflreadpy)
      |  games, lines, teams
      v
Python simulation            local, and in GitHub Actions
  ratings -> win probs -> 100,000 simulated seasons -> impacts
      |
      v
Neon Postgres 18.7           5 tables, ~19 MB (code requires >= 16)
      |  web_reader (SELECT only)
      v
Next.js 16 on Vercel         App Router, TypeScript, Tailwind v4
```

**Refresh schedule.** `.github/workflows/refresh.yml` runs
`python -m hatewatch.run --skip-schema` on Mon, Tue and Fri at 14:00 UTC — the
morning after Thursday, Sunday and Monday football. On success it calls a
Vercel deploy hook so the site rebuilds immediately. About 2m 40s per run.

### Code layout

| path | role |
|---|---|
| `etl/load_data.py` | nflverse → Postgres, re-runnable per season |
| `analysis/ratings.py` | market-implied team ratings from spreads |
| `analysis/win_probability.py` | moneyline/spread/ratings → P(home win) |
| `analysis/tiebreakers.py` | the real NFL tiebreaker ladders |
| `analysis/standings.py` | records, division order, playoff seeding |
| `analysis/simulate.py` | Monte Carlo season simulation |
| `analysis/backtest.py` | ratings vs market vs coin flip |
| `analysis/validate_seeds.py` | seeding checked against real brackets |
| `analysis/guide.py` | terminal report (was `hatewatch.py`; renamed to free the name) |
| `hatewatch/` | the package: config, impacts, reasons, store, run, export |
| `scripts/neon_bootstrap.py` | one-time Neon setup: migrations, roles, seed |
| `sql/00*.sql` | migrations, applied in filename order |
| `web/` | the Next.js site |

### Database roles

Created by `scripts/neon_bootstrap.py`. Verified with 22 live privilege probes
— every "denied" below was tested, not assumed.

| role | can | cannot |
|---|---|---|
| `neondb_owner` | everything; applies migrations, creates roles | — |
| `web_reader` | `SELECT` on `games`, `teams`, `sim_runs`, `team_odds`, `game_impacts` | write anything, DDL |
| `refresh_writer` | `SELECT` on those five; `INSERT`+`DELETE` on `games`; `INSERT` on the three result tables; `DELETE` on `game_impacts`; `MAINTAIN` | **any DDL**, **any `UPDATE`**, `DELETE` on `sim_runs` |

`refresh_writer` has no `DELETE` on `sim_runs` on purpose: that would cascade
and destroy the `team_odds` history. Pruning deletes from `game_impacts`
directly instead.

### Tables on Neon

Only what the site and the refresh job read. `plays` (139 MB), `contracts`
(14 MB) and `players` (10 MB) stay in the local database — 163 MB of analysis
data that neither the site nor the refresh job touches.

| table | contents | growth |
|---|---|---|
| `games` | 2026 season only | fixed |
| `teams` | 32 current + 4 legacy, `is_current` flag | fixed |
| `sim_runs` | one row per run | kept forever |
| `team_odds` | 32 rows per run, incl. tank numbers (avg pick, #1 pick %, top-5 %) | kept forever (~22 kB/run) |
| `game_impacts` | ~21,800 rows per run (5 goals) | **pruned to newest 3 runs** (~4.6 MB/run) |

### Secrets — names and locations only

**Never print a value. Never commit one. Never prefix one `NEXT_PUBLIC_`.**

| name | lives in | role | goes to |
|---|---|---|---|
| `DATABASE_URL` | `.env` | local Postgres | stays local |
| `NEON_ADMIN_URL` | `.env` | `neondb_owner` | **local only** — never Vercel, never GitHub |
| `NEON_WEB_READER_URL` | `.env` | `web_reader` | copied to Vercel as `DATABASE_URL` |
| `NEON_REFRESH_URL` | `.env` | `refresh_writer` | copied to GitHub secret `NEON_REFRESH_URL` |
| `DATABASE_URL` | `web/.env.local` | `web_reader` | local dev |
| `DATABASE_URL` | Vercel env vars | `web_reader` | the deployed site |
| `NEON_REFRESH_URL` | GitHub Actions secret | `refresh_writer` | the refresh workflow |
| `VERCEL_DEPLOY_HOOK` | GitHub Actions secret | — | triggers the rebuild |

Both `.env` files are mode `0600` and gitignored. No `.env` has ever been
committed, in any branch, at any point in history.

To hand a value to the user, copy it to the clipboard — never print it:

```
python - <<'PY'
import os, subprocess
from dotenv import load_dotenv
load_dotenv('.env')
subprocess.run(['pbcopy'], input=os.environ['NEON_WEB_READER_URL'].encode())
PY
```

---

## What is built

PRs #1–#16 are merged. Each was security-reviewed before merge.

| PR | what it added |
|---|---|
| **#1** | Postgres schema and the nflverse loader, 2022–2025. 197k plays, 1,139 games. Re-runnable: reloading a season replaces it. |
| **#2** | The first guide. Teams table, 2026 season, win probabilities from betting markets, 20k-sim Monte Carlo, impact ranking. |
| **#3** | Market-implied team ratings, replacing the 50/50 fallback for unpriced games. Backtest harness. Rating jitter. #1 seed and draft goals. |
| **#4** | The real NFL tiebreaker ladders, both of them, replacing win%-then-random. |
| **#5** | Result tables and the `hatewatch` package. All 32 teams, tiers, reason codes, `python -m hatewatch.run`. |
| **#6** | The Next.js site. Then 100k sims, the forced-outcome verification, and "Matters for other goals". |
| **#7** | Deployment: Neon, the two roles, retention, `--skip-schema`, the scheduled workflow, the site reading Neon, `/[team]` with the allowlist. |
| **#8** | Early guard for a missing secret, actions upgraded to v7, `.env` permissions fixed. |
| **#9** | This file, and the rule that every session reads it first. |
| **#10** | The Overall Root score (playoffs/division/#1 seed weighted 50/30/20) with a green-to-red meter as the default ranking; a per-goal "now / if A wins / if B wins" table on tap; two-column layout from 900px. |
| **#11** | All 32 teams: the header team picker (AFC/NFC by division) and banners in each team's colours, with text colour chosen per team for contrast; per-team page titles; a note for eliminated teams. |
| **#12** | The season-odds backtest and the v5 model it chose (see Key results). |
| **#13** | A working share button (system share sheet, else copy) and a per-team link-preview card. |
| **#14** | The full "How this works" page with the measured accuracy, and a "model estimate" note under the headline. |
| **#15** | A pick-your-team start screen at `/`, and a share button that copies on laptops (Chrome on macOS left `navigator.share` hanging). |
| **#16** | Per-game significance tiers, 200k sims, other-conference games never ranked, and "Too close to call" / "Can't really affect you" groups. |
| **#17** | Paired replays for the current week's games (each replayed both ways in the same 40k seasons), and a 0.1-point minimum. |
| **#18** | Tank mode: a Contend / Tank switch on every team page (`/min/tank`), ranking games by draft position and #1-pick chance. NFL draft order in the simulation (non-playoff teams first, strength-of-schedule tiebreak). Migration 006. Model v5.3. |

### Key results

**Tiebreakers: 8/8 exact.** The seeding code reproduces the real playoff
bracket for every conference-season 2022–2025, seeds 1 through 7. The real
seeds were recovered from the bracket itself (the #1 seed rests; the rest play
2v7, 3v6, 4v5), and the ordering was checked by the pairing rule — **every
wild-card matchup pairs seeds summing to 9** — which never consults a record,
so it cannot agree with our logic by construction. 51 ties were actually
resolved, by head-to-head sweep (16), head-to-head (12), conference record
(10), common games (8) and strength of victory (5). The old win%-then-random
logic scored **3/8**.

**The impact method is verified, not just asserted.** Impacts come from
*conditioning*: split the simulated seasons by who won a game, compare the
halves. That was checked against *forcing* each outcome — an intervention that
overrides one result without disturbing anything else — using common random
numbers so the pair differs only in that game.

| game | conditioning | forced | gap | SE |
|---|---|---|---|---|
| NE @ DET | 1.880 | 1.629 | 0.251 | 0.277 |
| LA @ ARI | 3.239 | 2.889 | 0.350 | 0.335 |
| PIT @ CIN *(AFC control)* | −0.217 | **0.000** | 0.217 | 0.283 |

All inside one standard error. The control is the strongest result: forcing an
AFC-only game moved MIN's odds by *exactly* zero across 100,000 seasons — so
the games used to measure the noise floor really do have no effect.

**Noise floor at 100k sims** (vs 20k):

| goal | 20,000 | 100,000 |
|---|---|---|
| playoffs | 1.96 | **1.29** |
| division | 1.61 | **1.12** |
| #1 seed | 1.37 | **0.69** |

**Ratings backtest**, fit through week 8, scored on everything after:

| season | ratings | market | coin flip |
|---|---|---|---|
| 2022 | 67.3% | 70.7% | 50% |
| 2023 | 64.0% | 70.7% | 50% |
| 2024 | 65.8% | 75.8% | 50% |
| 2025 | 53.6% | 60.9% | 50% |

Clearly better than a coin flip, short of the closing line — which is the
correct outcome. 2025 was an unpredictable year for the market too.

**Season-odds backtest** (`analysis/season_backtest.py`, Nov 2026). The
headline numbers — playoff, division, #1 seed odds — replayed for 2023–2025
from weeks 6, 10 and 14, using only what was known then: results before the
cutoff, betting lines for that week and the next, ratings fitted from those
lines alone. 288 forecasts per goal, scored against what happened. 2022 is
excluded: the cancelled BUF–CIN game left two teams at 16 games.

| model | playoffs Brier | division calibration gap |
|---|---|---|
| v4: 6-week half-life, full spreads | 0.1343 | 7.6 pts |
| two weeks of lines, coin flips after | 0.1285 | 5.1 pts |
| **v5 (live): 2-week half-life, 75% spreads, 1.5× jitter** | **0.1288** | **4.4 pts** |

v4 was overconfident, mainly on divisions: teams it gave ~87% won the
division 71% of the time. v5 beats v4 on playoff Brier in each season
separately. It only *ties* the coin-flip version on Brier — ratings for
far-off games add little beyond the betting lines — so its value is honest
calibration, not sharper picks.

**Against live markets (week 10, 2026):** most teams within ~5 points of
Kalshi, perthirtysix and The Athletic; a few 10–16 points apart (TB, DAL,
DET under v4). Markets remain the better forecaster of season odds; see
"Market data" under Known limitations.

---

## Key decisions, and why

**Ratings are fitted from spreads, not scores.** A spread is a forecast made
by people with money at stake, already adjusted for injuries, rest and
weather. A final score is one noisy sample, and it rewards blowouts the market
does not treat as proportionally meaningful.

**We simulate rather than read an odds API.** An API can give a team's playoff
probability. It cannot answer "how much does *this* game move it", which is
the entire product — that needs a counterfactual. Simulating also yields all
32 teams' numbers from one run, so a Bears page costs nothing extra.

**100,000 simulations, not 20,000.** At 20k the noise floor sat at ~1.9, just
under the 2.0 "Root hard" cutoff, so a game whose true impact was near 2
points flipped tier between runs on noise alone — observed directly: NE @ DET
scored Root hard, Root hard, then Doesn't matter across three runs. At 100k
the floor drops to 1.29 and the band stops being a coin toss. Costs 60s.

**Each game is judged against its own measurement error.** A game counts as
real ("A little" or above) when its swing is at least 2.5 of its own standard
errors (`SIGNIFICANCE_Z`), computed from how many simulated seasons fell on
each side. The earlier rule — the largest swing on games between two
other-conference teams — broke under v5: the bigger rating jitter lets those
games reach you through interconference games, the floor jumped from 1.1 to
1.95 points, and three real week-10 games for the Vikings (1.7–1.9 points, z of
5–7) were labelled "doesn't matter". Games between two other-conference teams
are never ranked at all: their only channel is tiny tiebreakers, so any
measured swing is noise. 200,000 sims (was 100k) shrink the error so smaller
real effects show; about two minutes per run. The tank goals use the same
per-game test, with no conference split (the draft ranks all 32 teams).

**This week's games are measured by paired replays.** In the first 40,000
simulated seasons (`PAIRED_SIMS`), each current-week game is flipped and that
season re-seeded, so the game is seen both ways with everything else
identical. Errors drop from ~0.2 to ~0.05 points and games that cannot
matter come out at exactly zero. Tiebreak coin tosses use one random stream
per (season, conference) so a replay repeats them. Only the two teams'
conferences are re-seeded. Adds ~4 minutes per run. Week-10 check for MIN:
conditioning said LA @ ARI moved the division 0.82 points; paired showed
−0.01 — the conditioning figure was noise. Future weeks still use
conditioning (below), but the site only shows the current week.

**Tank mode is a separate page, not a fourth goal in the Overall score.**
It tells a fan to root against their own team, so it lives at its own
address (`/min/tank`), reached only by the switch — never a default. Two
goals: draft position (average pick; cutoffs 1.0 / 0.2 picks, set from the
week-10 dry run: own games 1.7–3.6 picks, other games ≤ 0.34, 95% under
0.19) and #1 pick (percentage points, the playoff cutoffs). No combined tank
score — picks and percentage points do not add. The draft order follows the
NFL: non-playoff teams first, then wins, then strength of schedule (weaker
picks first), then random; playoff teams by record (the NFL uses elimination
round; playoffs are not simulated). On real 2023–2025 final standings the
rule matched every 2024 and 2025 draft slot except known trades (CAR→CHI #1,
MIN–NYJ and MIN–JAX in 2024; CLE–JAX #2/#5 in 2025); 2026 also fits once
trades are allowed for (ATL→LA, IND→NYJ, DAL's pick, and apparently KC–CLE
and CIN–NYG). Paired replays carry the draft too (+8 s per run).
Migration 006 widens two allowlists, so 004 now carries `draft_rival` as
well — every file re-runs on each local load, and 004 runs first.

**Impacts by conditioning, not re-simulation.** Each game's winner already
varies across iterations, so one run answers all 135 games at once. Verified
against forcing (above).

**The real tiebreakers run inside the simulation loop**, rather than a fast
vectorised copy. It costs real time, but the simulator uses the *same* code
validated against the brackets, instead of a parallel implementation that
could silently drift.

**The site's database role is read-only.** The website never writes. A query
bug, or a future injection, cannot damage anything.

**The refresh job holds no DDL rights.** `hatewatch.run` used to apply every
migration on every run; `--skip-schema` means migrations are applied once by
the owner and the job can only write rows.

**Retention is asymmetric.** `team_odds` is 22 kB/run and is what any
odds-over-time chart needs, so it is kept forever. `game_impacts` is 3.65
MB/run and only the newest is ever rendered, so it is pruned to three.

**Timezones are converted in SQL.** Postgres already has the timezone
database. Kickoffs are stored Eastern, displayed Central, and the conversion
happens in the query — so the rendered string is identical for every reader
and no date library enters the bundle.

**Display strings are built server-side.** The browser receives a small view
model of finished strings, not rows.

---

## Known limitations

**Future-week impacts run slightly high.** Weeks 12+ have no betting lines, so
those games are priced from ratings — and conditioning on "team X won" also
selects simulations where X's rating drew high, which affects X's *other*
games. Measured on CHI @ DET (week 12): conditioning 0.709 vs forced 0.252, a
0.457 pp gap at 1.65σ. So those numbers blend "what this result does" with
"what it tells us about the teams". Fixing it properly needs two forced runs
per game — 272 runs — which is why conditioning exists. Market-priced games
(the current week or two) are unaffected and provably equivalent.

**Injuries reach the model only through betting lines.** Weeks with a line
(the next one or two) pick up news once the line moves and a refresh runs
(Mon/Tue/Fri). Later weeks see it only as fast as the ratings follow recent
lines — faster under v5's 2-week half-life, still not instantly.

**Market data: none we may use yet.** Kalshi covers playoffs, division and
#1 seed for all 32 teams, but its Developer Agreement v1.1 (§3, §3.1, §3.5,
§6.4) forbids storing, sharing, benchmarking against or publicly naming its
data without written permission. A permission request was emailed to
institutional@kalshi.com on 2026-11-14; until a written yes arrives, make no
Kalshi API calls. Polymarket's terms are ambiguous and its #1 seed markets
are near-empty. The Odds API allows display but has no playoff or division
futures. No 2022–2024 futures history exists in any usable source.

**Tank mode's draft order is approximate past pick 18.** Playoff teams are
ordered by record, not by playoff round, and the NFL's division/conference
draft tiebreakers after strength of schedule are not implemented (coin flip
instead). Runs saved before v5.3 have no tank numbers; the tank page says so.

**`.env` has a sub-millisecond TOCTOU window.** `write_env` truncates, writes,
then `chmod`s to `0600`. Between those the file is world-readable. Before PR
#8 it stayed `0644` *permanently*, so this is a large improvement, not a
regression. Closing it entirely means writing a sibling temp file opened
`0600` and `os.replace`-ing it — which would also make the write atomic.

**Net touchdowns is not implemented** — step 11 of 12 in the tiebreaker
ladder. Touchdown counts are not in `games`, and simulated seasons have no
scores. It was never reached in the 8/8 validation.


**Simulated games never tie.** Real ties already played count as half a win.

**Seeding compares total wins, not win percentage.** Valid only because every
team finishes 17 games — asserted in code, not assumed.

**Only 2026 is on Neon.** Historical seasons, play-by-play, players and
contracts live in the local database.

**Actions use mutable major tags** (`@v7`) rather than SHA pins.

**Scheduled runs start late.** The first `schedule` run (Fri 2026-11-13)
succeeded — including the first retention prune on Neon (17,280 rows) and the
Vercel rebuild — but GitHub started it at 20:48 UTC, nearly seven hours after
its 14:00 slot. GitHub does not guarantee start times; if timing matters,
schedule earlier or dispatch manually.

---

## Roadmap

Done since the first version of this list: the share button and per-team
preview card (PR #13), and the full "How this works" page with the measured
accuracy plus a "model estimate" note under the headline (PR #14). The
how-it-works page quotes backtest numbers by hand — update it whenever the
model or `season_backtest.py` results change.

1. **End of season — before the regular season ends (Jan 2027).** With no
   games left, the guide has nothing to show and will look broken. Needs a
   "season's over, here's how it ended" state, then a plan for loading the
   2027 season (`DEFAULT_SEASON`, nflverse schedule release) next fall.
2. **Remember the chosen team** — the picker works (PR #11) but does not
   remember a choice, and `/` always goes to the Vikings.
3. **Refresh timing** — GitHub starts scheduled runs hours late; consider
   earlier slots or weekend-morning runs (a workflow change: plan first).
4. **Market-odds comparison** — blocked on Kalshi's written permission (see
   Known limitations). If granted: calibrate the simulation's ratings to the
   futures so headline odds match the market and impacts stay consistent.
5. **AI features, later** — natural-language summaries of a week, or asking
   "what has to happen for us to win the division?".

---

## Running it

```bash
# refresh + simulate + save (uses DATABASE_URL)
python -m hatewatch.run                    # 200k sims + paired replays, ~6 min
python -m hatewatch.run --skip-schema      # production: no DDL rights needed

# terminal report
python analysis/guide.py --compare
python analysis/guide.py --goal division --week 11

# checks
python analysis/validate_seeds.py          # 8/8 against real brackets
python analysis/backtest.py --validate     # ratings vs market vs coin flip

# the site
cd web && npm run dev                      # http://localhost:3000
```
