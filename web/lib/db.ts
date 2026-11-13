/** Server-only access to Neon.
 *
 *  Uses the `web_reader` role, which holds SELECT on five tables and nothing
 *  else -- it cannot write, and the analysis tables are not in this database
 *  at all. So even a query bug cannot damage anything.
 *
 *  Every query below is a tagged template from @neondatabase/serverless, which
 *  sends interpolated values as bound parameters rather than splicing them
 *  into SQL text. No query is assembled by joining strings.
 *
 *  Two things are formatted in SQL rather than in JavaScript, on purpose:
 *  kickoff times and the "updated" stamp. Both need US Central time, and
 *  Postgres already knows the timezone database. Doing it here means the
 *  rendered string is identical for every reader and matches what the Python
 *  exporter produces, with no date library in the bundle.
 */

import "server-only";

import { neon } from "@neondatabase/serverless";

/** Built lazily: at build time on a fresh clone there may be no DATABASE_URL
 *  yet, and a module-level call would crash the import rather than let the
 *  page render its "not configured" state. */
function client() {
  const url = process.env.DATABASE_URL;
  if (!url) {
    throw new MissingDatabaseError(
      "DATABASE_URL is not set. Point it at the web_reader connection string.",
    );
  }
  return neon(url);
}

export class MissingDatabaseError extends Error {}

export interface RunRow {
  run_id: number;
  season: number;
  week: number;
  n_sims: number;
  updated: string;
}

export async function latestRun(): Promise<RunRow | null> {
  const sql = client();
  const rows = (await sql`
    SELECT run_id, season, week, n_sims,
           to_char(created_at AT TIME ZONE 'America/Chicago',
                   'Dy FMHH12:MI AM') || ' CT' AS updated
    FROM sim_runs
    ORDER BY created_at DESC, run_id DESC
    LIMIT 1
  `) as RunRow[];
  return rows[0] ?? null;
}

/** The teams a URL may name. Everything else is a 404.
 *
 *  Read from the database rather than hardcoded, so the allowlist cannot
 *  drift from the teams that actually have data. */
export async function allowedTeams(): Promise<string[]> {
  const sql = client();
  const rows = (await sql`
    SELECT team_abbr FROM teams WHERE is_current ORDER BY team_abbr
  `) as { team_abbr: string }[];
  return rows.map((r) => r.team_abbr);
}

export async function nicknames(): Promise<Record<string, string>> {
  const sql = client();
  const rows = (await sql`
    SELECT team_abbr, team_nick FROM teams WHERE is_current
  `) as { team_abbr: string; team_nick: string }[];
  return Object.fromEntries(rows.map((r) => [r.team_abbr, r.team_nick]));
}

export interface TeamRow {
  team_abbr: string;
  team_name: string;
  team_nick: string;
  team_conf: string;
  team_division: string;
}

export async function teamInfo(abbr: string): Promise<TeamRow | null> {
  const sql = client();
  const rows = (await sql`
    SELECT team_abbr, team_name, team_nick, team_conf, team_division
    FROM teams WHERE team_abbr = ${abbr}
  `) as TeamRow[];
  return rows[0] ?? null;
}

/** W-L-T so far, counted the same way the Python standings code counts it:
 *  result is home score minus away score, so a positive result is a home win. */
export async function teamRecord(abbr: string, season: number) {
  const sql = client();
  const rows = (await sql`
    SELECT
      count(*) FILTER (WHERE (home_team = ${abbr} AND result > 0)
                          OR (away_team = ${abbr} AND result < 0)) AS wins,
      count(*) FILTER (WHERE (home_team = ${abbr} AND result < 0)
                          OR (away_team = ${abbr} AND result > 0)) AS losses,
      count(*) FILTER (WHERE result = 0) AS ties
    FROM games
    WHERE season = ${season} AND game_type = 'REG'
      AND home_score IS NOT NULL
      AND ${abbr} IN (home_team, away_team)
  `) as { wins: string; losses: string; ties: string }[];
  const r = rows[0];
  const wins = Number(r?.wins ?? 0);
  const losses = Number(r?.losses ?? 0);
  const ties = Number(r?.ties ?? 0);
  return {
    wins,
    losses,
    ties,
    text: `${wins}-${losses}` + (ties ? `-${ties}` : ""),
  };
}

export interface OddsRow {
  playoff_pct: string;
  division_pct: string;
  top_seed_pct: string;
  avg_seed: string | null;
}

export async function teamOdds(runId: number, abbr: string) {
  const sql = client();
  const rows = (await sql`
    SELECT playoff_pct, division_pct, top_seed_pct, avg_seed
    FROM team_odds WHERE run_id = ${runId} AND team = ${abbr}
  `) as OddsRow[];
  return rows[0] ?? null;
}

export interface ImpactRow {
  game_id: string;
  week: number;
  away_team: string;
  home_team: string;
  goal: string;
  root_for: string;
  against: string;
  impact_pts: string;
  root_for_win_pct: string;
  value_if_root_for_wins: string | null;
  value_if_root_for_loses: string | null;
  tier: string;
  reason_code: string;
  kickoff: string | null;
}

/** Every impact row for one team in one week. The draft goal is excluded in
 *  SQL: it is stored, but the site never shows it. */
export async function weekImpacts(
  runId: number,
  abbr: string,
  week: number,
): Promise<ImpactRow[]> {
  const sql = client();
  return (await sql`
    SELECT i.game_id, g.week, g.away_team, g.home_team, i.goal, i.root_for,
           CASE WHEN i.root_for = g.home_team THEN g.away_team
                ELSE g.home_team END AS against,
           i.impact_pts, i.root_for_win_pct,
           i.value_if_root_for_wins, i.value_if_root_for_loses,
           i.tier, i.reason_code,
           -- Stored Eastern, displayed Central. Written inline rather than
           -- interpolated, so the whole query stays a single literal.
           to_char(((g.gameday + g.gametime::time)
                    AT TIME ZONE 'America/New_York')
                    AT TIME ZONE 'America/Chicago',
                   'Dy FMHH12:MI AM') AS kickoff
    FROM game_impacts i
    JOIN games g ON g.game_id = i.game_id
    WHERE i.run_id = ${runId} AND i.team = ${abbr}
      AND g.week = ${week} AND i.goal <> 'draft'
    ORDER BY i.impact_pts DESC
  `) as ImpactRow[];
}
