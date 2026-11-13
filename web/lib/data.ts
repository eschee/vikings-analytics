/** Builds the page's view model from Neon.
 *
 *  Server-only. The browser never sees a row: this narrows the query results
 *  into display strings and hands the client components a small object.
 *
 *  Replaces the earlier version that read an exported JSON file. The file is
 *  still produced by `python -m hatewatch.export` for local work, but the
 *  deployed site reads the database so a refresh shows up without a commit.
 */

import { cacheLife } from "next/cache";

import {
  MissingDatabaseError,
  allowedTeams,
  latestRun,
  nicknames,
  teamInfo,
  teamOdds,
  teamRecord,
  weekImpacts,
} from "./db";
import {
  GOAL_LABELS,
  RANKABLE_GOALS,
  type GameView,
  type GoalView,
  type PageData,
  type RankableGoal,
  type Tier,
} from "./types";

export { MissingDatabaseError };

/** Above this, "will they make the playoffs" has stopped being the
 *  interesting question, so the page ranks by the division race instead. */
export const PLAYOFFS_SETTLED_PCT = 97;

/** Display labels. These mirror TIER_LABELS and REASON_LABELS in
 *  hatewatch/config.py; the database stores the codes, not the wording. */
const TIER_LABELS: Record<Tier, string> = {
  must_win: "Must win",
  root_hard: "Root hard",
  a_little: "A little",
  doesnt_matter: "Doesn't matter",
};

export class UnknownTeamError extends Error {}

/** The allowlist, straight from the teams table. */
export async function teamAllowlist(): Promise<string[]> {
  "use cache";
  cacheLife("hours");
  return allowedTeams();
}

function num(value: string | number | null | undefined): number {
  return value === null || value === undefined ? 0 : Number(value);
}

export async function loadPageData(teamParam: string): Promise<PageData> {
  // The simulation runs three times a week, so an hour-old page is never
  // misleading. The GitHub Action also pokes a Vercel deploy hook after each
  // run, which rebuilds immediately; this is the backstop for when it doesn't.
  "use cache";
  cacheLife("hours");

  const abbr = teamParam.toUpperCase();

  // Allowlist first, before the value reaches any other query. An unknown
  // team is a 404, never an empty page that looks like a real answer.
  const allowed = await allowedTeams();
  if (!allowed.includes(abbr)) {
    throw new UnknownTeamError(`${teamParam} is not an NFL team`);
  }

  const run = await latestRun();
  if (!run) {
    throw new MissingDatabaseError(
      "No simulation runs are stored yet. Run `python -m hatewatch.run`.",
    );
  }

  const [team, record, odds, nicks, impacts] = await Promise.all([
    teamInfo(abbr),
    teamRecord(abbr, run.season),
    teamOdds(run.run_id, abbr),
    nicknames(),
    weekImpacts(run.run_id, abbr, run.week),
  ]);

  // Group the flat impact rows into one entry per game, with its goals.
  const byGame = new Map<string, GameView>();
  for (const row of impacts) {
    const goal = row.goal as RankableGoal;
    if (!RANKABLE_GOALS.includes(goal)) continue;

    let game = byGame.get(row.game_id);
    if (!game) {
      game = {
        gameId: row.game_id,
        awayNick: nicks[row.away_team] ?? row.away_team,
        homeNick: nicks[row.home_team] ?? row.home_team,
        kickoff: row.kickoff ?? "",
        kickoffTz: "CT",
        isOwnGame: row.away_team === abbr || row.home_team === abbr,
        goals: {} as Record<RankableGoal, GoalView>,
      };
      byGame.set(row.game_id, game);
    }

    const tier = row.tier as Tier;
    game.goals[goal] = {
      goal,
      label: GOAL_LABELS[goal],
      rootFor: row.root_for,
      rootForNick: nicks[row.root_for] ?? row.root_for,
      againstNick: nicks[row.against] ?? row.against,
      impact: num(row.impact_pts),
      rootForWinPct: num(row.root_for_win_pct),
      valueIfWin:
        row.value_if_root_for_wins === null
          ? null
          : num(row.value_if_root_for_wins),
      valueIfLose:
        row.value_if_root_for_loses === null
          ? null
          : num(row.value_if_root_for_loses),
      tier,
      tierLabel: TIER_LABELS[tier] ?? tier,
      reasonCode: row.reason_code,
      subjectNick:
        row.reason_code === "own_game" ||
        row.reason_code === "tiebreaker_effect"
          ? null
          : (nicks[row.against] ?? row.against),
    };
  }

  // Drop any game missing one of the three goals rather than render blanks.
  const views = [...byGame.values()].filter((g) =>
    RANKABLE_GOALS.every((k) => g.goals[k] !== undefined),
  );

  const playoffPct = num(odds?.playoff_pct);
  const settled = playoffPct >= PLAYOFFS_SETTLED_PCT;

  return {
    teamNick: team?.team_nick ?? abbr,
    teamName: team?.team_name ?? abbr,
    teamAbbr: abbr,
    division: team?.team_division ?? "",
    conference: team?.team_conf ?? "",
    recordText: record.text,
    week: run.week,
    season: run.season,
    playoffPct,
    divisionPct: num(odds?.division_pct),
    topSeedPct: num(odds?.top_seed_pct),
    updatedLabel: run.updated,
    defaultGoal: settled ? "division" : "playoffs",
    defaultGoalNote: settled
      ? `A playoff spot is all but locked at ${playoffPct.toFixed(0)}%, so games are ranked by the division race instead.`
      : null,
    ownGame: views.find((g) => g.isOwnGame) ?? null,
    games: views.filter((g) => !g.isOwnGame),
  };
}
