/** Loads the exported JSON and narrows it into the view model the page renders.
 *
 *  This runs on the server only. The raw export is ~290 KB and covers nine
 *  weeks; the browser receives just the current week, already resolved to
 *  display strings. */

import { promises as fs } from "node:fs";
import path from "node:path";

import { updatedLabel } from "./format";
import {
  GOAL_LABELS,
  RANKABLE_GOALS,
  type GameView,
  type GoalView,
  type PageData,
  type RankableGoal,
  type RawGame,
  type RawPayload,
  type Tier,
} from "./types";

/** Above this, "will they make the playoffs" has stopped being the
 *  interesting question, so the page ranks by the division race instead. */
export const PLAYOFFS_SETTLED_PCT = 97;

const DATA_DIR = path.join(process.cwd(), "sample-data");

export class MissingDataError extends Error {}

export async function loadPayload(teamAbbr = "MIN"): Promise<RawPayload> {
  const file = path.join(DATA_DIR, `${teamAbbr.toLowerCase()}-latest.json`);
  let text: string;
  try {
    text = await fs.readFile(file, "utf8");
  } catch {
    throw new MissingDataError(
      `No exported data at sample-data/${teamAbbr.toLowerCase()}-latest.json. ` +
        `Generate it from the project root with: ` +
        `python -m hatewatch.export --team ${teamAbbr.toUpperCase()}`,
    );
  }
  return JSON.parse(text) as RawPayload;
}

/** Which other team a reason sentence should name.
 *
 *  For most codes the interesting team is the one the rule fired on, which is
 *  the opponent of whoever we are rooting for. For a cross-conference game
 *  neither team is relevant by name, so we return null and the sentence talks
 *  about the mechanism instead. */
function subjectFor(
  reasonCode: string,
  rootFor: string,
  against: string,
  nicknames: Record<string, string>,
): string | null {
  if (reasonCode === "own_game" || reasonCode === "tiebreaker_effect") {
    return null;
  }
  return nicknames[against] ?? against;
}

function toGoalView(
  goal: RankableGoal,
  raw: NonNullable<RawGame["goals"][RankableGoal]>,
  nicknames: Record<string, string>,
): GoalView {
  return {
    goal,
    label: GOAL_LABELS[goal],
    rootFor: raw.root_for,
    rootForNick: nicknames[raw.root_for] ?? raw.root_for,
    againstNick: nicknames[raw.against] ?? raw.against,
    impact: raw.impact_pts,
    rootForWinPct: raw.root_for_win_pct,
    valueIfWin: raw.value_if_root_for_wins,
    valueIfLose: raw.value_if_root_for_loses,
    tier: raw.tier as Tier,
    tierLabel: raw.tier_label,
    reasonCode: raw.reason_code,
    subjectNick: subjectFor(raw.reason_code, raw.root_for, raw.against, nicknames),
  };
}

function toGameView(
  raw: RawGame,
  teamAbbr: string,
  nicknames: Record<string, string>,
): GameView | null {
  const goals = {} as Record<RankableGoal, GoalView>;
  for (const goal of RANKABLE_GOALS) {
    const g = raw.goals[goal];
    if (!g) return null; // a goal is missing: skip rather than render blanks
    goals[goal] = toGoalView(goal, g, nicknames);
  }
  return {
    gameId: raw.game_id,
    awayNick: nicknames[raw.away] ?? raw.away,
    homeNick: nicknames[raw.home] ?? raw.home,
    kickoff: raw.kickoff?.label ?? "",
    kickoffTz: raw.kickoff?.tz ?? "",
    isOwnGame: raw.away === teamAbbr || raw.home === teamAbbr,
    goals,
  };
}

export async function loadPageData(teamAbbr = "MIN"): Promise<PageData> {
  // The exported JSON is a build-time input, not live data: it only changes
  // when `python -m hatewatch.export` is re-run. Marking the read cacheable
  // lets Next prerender the page instead of treating a file read as runtime
  // data and refusing to build it statically.
  "use cache";
  const payload = await loadPayload(teamAbbr);
  const nicknames = payload.nicknames ?? {};
  const week = payload.run.week;
  const thisWeek = payload.weeks.find((w) => w.week === week);

  const views = (thisWeek?.games ?? [])
    .map((g) => toGameView(g, payload.team.abbr, nicknames))
    .filter((g): g is GameView => g !== null);

  const ownGame = views.find((g) => g.isOwnGame) ?? null;
  const games = views.filter((g) => !g.isOwnGame);

  const playoffPct = payload.odds?.playoff_pct ?? 0;
  const settled = playoffPct >= PLAYOFFS_SETTLED_PCT;

  return {
    teamNick: payload.team.nick ?? payload.team.abbr,
    teamName: payload.team.name ?? payload.team.abbr,
    teamAbbr: payload.team.abbr,
    division: payload.team.division ?? "",
    conference: payload.team.conference ?? "",
    recordText: payload.team.record?.text ?? "",
    week,
    season: payload.run.season,
    playoffPct,
    divisionPct: payload.odds?.division_pct ?? 0,
    topSeedPct: payload.odds?.top_seed_pct ?? 0,
    updatedLabel: updatedLabel(payload.run.created_at),
    defaultGoal: settled ? "division" : "playoffs",
    defaultGoalNote: settled
      ? `A playoff spot is all but locked at ${playoffPct.toFixed(0)}%, so games are ranked by the division race instead.`
      : null,
    ownGame,
    games,
  };
}
