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
  teamDirectory,
  teamRecord,
  weekImpacts,
} from "./db";
import { isHexColour, teamTheme } from "./colors";
import {
  GOAL_LABELS,
  OVERALL_WEIGHTS,
  RANKABLE_GOALS,
  type GameView,
  type GoalShift,
  type GoalView,
  type OverallView,
  type PageData,
  type RankableGoal,
  type TeamEntry,
  type Tier,
} from "./types";

export { MissingDatabaseError };

/** Display labels. These mirror TIER_LABELS and REASON_LABELS in
 *  hatewatch/config.py; the database stores the codes, not the wording. */
const TIER_LABELS: Record<Tier, string> = {
  must_win: "Must win",
  root_hard: "Root hard",
  a_little: "A little",
  doesnt_matter: "Doesn't matter",
};

/** Why a page could not be built.
 *
 *  loadPageData returns this instead of throwing. Errors do not survive a
 *  "use cache" boundary as the same object -- an earlier version threw
 *  UnknownTeamError and the page's `instanceof` check silently failed,
 *  turning a 404 into a 500. A returned value crosses the boundary intact,
 *  so the whole class of bug goes away rather than being fixed case by case.
 */
export type LoadFailure =
  | { reason: "unknown-team"; message: string }
  | { reason: "no-database"; message: string }
  | { reason: "no-runs"; message: string };

export type LoadResult =
  | { ok: true; data: PageData }
  | { ok: false; failure: LoadFailure };

/** The allowlist, straight from the teams table. */
export async function teamAllowlist(): Promise<string[]> {
  "use cache";
  cacheLife("hours");
  return allowedTeams();
}

/** All 32 teams for the picker, with their raw colours for the banner.
 *  Cached like the allowlist: the teams table changes once a decade. */
export async function directory(): Promise<{
  entries: TeamEntry[];
  colours: Record<string, { primary: string | null; secondary: string | null }>;
}> {
  "use cache";
  cacheLife("hours");
  const rows = await teamDirectory();
  return {
    entries: rows.map((r) => ({
      abbr: r.team_abbr,
      nick: r.team_nick,
      conference: r.team_conf,
      division: r.team_division.replace(/^(AFC|NFC)\s+/, ""),
      colour: isHexColour(r.team_color) ? r.team_color : null,
    })),
    colours: Object.fromEntries(
      rows.map((r) => [
        r.team_abbr,
        { primary: r.team_color, secondary: r.team_color2 },
      ]),
    ),
  };
}

function num(value: string | number | null | undefined): number {
  return value === null || value === undefined ? 0 : Number(value);
}

/** Fold one game's three goals into a single Root score.
 *
 *  The goals can point at different teams -- a Rams loss helps the wild-card
 *  race while a Rams win can help the division -- so each swing is first given
 *  a sign: positive when it favours the HOME team, negative for the away team.
 *  The weighted sum then says both who to root for (its sign) and how much
 *  (its size). Conflicting goals partly cancel, which is the honest answer:
 *  a game that helps one goal and hurts another matters less overall.
 *
 *  A goal whose swing is inside the noise floor contributes nothing. Without
 *  that, fourteen games' worth of noise would add up into small fake scores.
 */
function buildOverall(
  game: Omit<GameView, "overall" | "otherConference">,
  homeAbbr: string,
  awayAbbr: string,
  nicks: Record<string, string>,
  current: Record<RankableGoal, number>,
): OverallView {
  const real = (g: RankableGoal) => game.goals[g].tier !== "doesnt_matter";
  const towardHome = (g: RankableGoal) =>
    game.goals[g].rootFor === homeAbbr ? 1 : -1;

  const signed = RANKABLE_GOALS.reduce(
    (sum, g) =>
      real(g)
        ? sum + towardHome(g) * game.goals[g].impact * OVERALL_WEIGHTS[g]
        : sum,
    0,
  );
  const rootHome = signed >= 0;

  const homeTeam = { abbr: homeAbbr, nick: nicks[homeAbbr] ?? homeAbbr };
  const awayTeam = { abbr: awayAbbr, nick: nicks[awayAbbr] ?? awayAbbr };
  const root = rootHome ? homeTeam : awayTeam;
  const against = rootHome ? awayTeam : homeTeam;

  // Every goal's numbers, flipped where that goal roots for the other side,
  // so "if they win" always means the overall pick winning.
  const shifts: GoalShift[] = RANKABLE_GOALS.map((g) => {
    const v = game.goals[g];
    const same = (v.rootFor === homeAbbr) === rootHome;
    return {
      goal: g,
      label: GOAL_LABELS[g],
      current: current[g],
      ifRootWins: same ? v.valueIfWin : v.valueIfLose,
      ifRootLoses: same ? v.valueIfLose : v.valueIfWin,
      real: real(g),
    };
  });

  const realGoals = RANKABLE_GOALS.filter(real);
  const biggestGoal =
    realGoals.length === 0
      ? null
      : realGoals.reduce((a, b) =>
          game.goals[b].impact > game.goals[a].impact ? b : a,
        );

  // The reason shown should explain the call actually made, so take it from
  // the goal pushing hardest in the chosen direction.
  const agreeing = realGoals.filter(
    (g) => (game.goals[g].rootFor === homeAbbr) === rootHome,
  );
  const reasonGoal =
    agreeing.length === 0
      ? (biggestGoal ?? "playoffs")
      : agreeing.reduce((a, b) =>
          game.goals[b].impact * OVERALL_WEIGHTS[b] >
          game.goals[a].impact * OVERALL_WEIGHTS[a]
            ? b
            : a,
        );

  const pv = game.goals.playoffs;
  const rootForWinPct =
    pv.rootFor === root.abbr ? pv.rootForWinPct : 100 - pv.rootForWinPct;

  return {
    rootFor: root.abbr,
    rootForNick: root.nick,
    againstNick: against.nick,
    score: Math.abs(signed),
    rootForWinPct,
    biggestGoal,
    reasonGoal,
    shifts,
  };
}

export async function loadPageData(teamParam: string): Promise<LoadResult> {
  // The simulation runs three times a week, so an hour-old page is never
  // misleading. The GitHub Action also pokes a Vercel deploy hook after each
  // run, which rebuilds immediately; this is the backstop for when it doesn't.
  "use cache";
  cacheLife("hours");

  const abbr = teamParam.toUpperCase();

  // Allowlist first, before the value reaches any other query. An unknown
  // team is a 404, never an empty page that looks like a real answer.
  let allowed: string[];
  let run: Awaited<ReturnType<typeof latestRun>>;
  try {
    allowed = await allowedTeams();
    if (!allowed.includes(abbr)) {
      return {
        ok: false,
        failure: {
          reason: "unknown-team",
          message: `${teamParam} is not an NFL team`,
        },
      };
    }
    run = await latestRun();
  } catch {
    return {
      ok: false,
      failure: {
        reason: "no-database",
        message:
          "The database is not reachable. Check that DATABASE_URL points at " +
          "the web_reader connection string.",
      },
    };
  }

  if (!run) {
    return {
      ok: false,
      failure: {
        reason: "no-runs",
        message:
          "No simulation runs are stored yet. Run `python -m hatewatch.run`.",
      },
    };
  }

  const [team, record, odds, nicks, impacts, dir] = await Promise.all([
    teamInfo(abbr),
    teamRecord(abbr, run.season),
    teamOdds(run.run_id, abbr),
    nicknames(),
    weekImpacts(run.run_id, abbr, run.week),
    directory(),
  ]);
  const colours = dir.colours[abbr];
  const confOf = Object.fromEntries(
    dir.entries.map((e) => [e.abbr, e.conference]),
  );

  // Group the flat impact rows into one entry per game, with its goals.
  // `overall` is filled in once all three goals are present.
  const byGame = new Map<string, Omit<GameView, "overall" | "otherConference">>();
  const sides = new Map<string, { home: string; away: string }>();
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
      sides.set(row.game_id, { home: row.home_team, away: row.away_team });
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

  const playoffPct = num(odds?.playoff_pct);
  const current: Record<RankableGoal, number> = {
    playoffs: playoffPct,
    division: num(odds?.division_pct),
    top_seed: num(odds?.top_seed_pct),
  };

  // Drop any game missing one of the three goals rather than render blanks.
  const views: GameView[] = [...byGame.values()]
    .filter((g) => RANKABLE_GOALS.every((k) => g.goals[k] !== undefined))
    .map((g) => {
      const s = sides.get(g.gameId)!;
      return {
        ...g,
        overall: buildOverall(g, s.home, s.away, nicks, current),
        otherConference:
          confOf[s.home] !== team?.team_conf &&
          confOf[s.away] !== team?.team_conf,
      };
    });

  return {
    ok: true,
    data: {
    theme: teamTheme(colours?.primary, colours?.secondary),
    directory: dir.entries,
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
    nSims: Number(run.n_sims),
    // The combined score already discounts a settled race -- a locked playoff
    // spot barely moves, so it contributes little -- which retires the old
    // "switch to division at 97%" rule.
    defaultGoal: "overall",
    ownGame: views.find((g) => g.isOwnGame) ?? null,
    games: views.filter((g) => !g.isOwnGame),
    },
  };
}
