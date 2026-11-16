/** Shapes of the exported JSON (hatewatch/export.py) and the view model the
 *  page renders. Keeping them separate means the UI never reaches into the raw
 *  payload: the server narrows it once, and the client only sees what it
 *  needs. */

import type { TeamTheme } from "./colors";

export type GoalKey =
  | "playoffs"
  | "division"
  | "top_seed"
  | "draft"
  | "top_pick";

/** Every goal the site can rank by. Which ones a page shows depends on its
 *  mode (MODE_GOALS). */
export const RANKABLE_GOALS = [
  "playoffs",
  "division",
  "top_seed",
  "draft",
  "top_pick",
] as const;
export type RankableGoal = (typeof RANKABLE_GOALS)[number];

/** Contend: rooting for your team to make a run. Tank: rooting for the best
 *  draft pick -- which means rooting AGAINST your own team. Tank mode lives
 *  at its own address (/min/tank) so it is a deliberate choice, never what a
 *  fan lands on by default, and can be shared. */
export type Mode = "contend" | "tank";

export const MODE_GOALS = {
  contend: ["playoffs", "division", "top_seed"],
  tank: ["draft", "top_pick"],
} as const satisfies Record<Mode, readonly RankableGoal[]>;

export const GOAL_LABELS: Record<RankableGoal, string> = {
  playoffs: "Playoffs",
  division: "Division",
  top_seed: "#1 seed",
  draft: "Draft position",
  top_pick: "#1 pick",
};

/** Draft position is an average pick number, where LOWER is better. Every
 *  other goal is a percentage chance, where higher is better. */
export function isPickGoal(goal: RankableGoal): boolean {
  return goal === "draft";
}

/** The goals present on one game, in display order. A page only loads its
 *  own mode's goals, so components ask the game rather than assume a list. */
export function goalsOf(game: { goals: Partial<Record<RankableGoal, unknown>> }) {
  return RANKABLE_GOALS.filter((g) => game.goals[g] !== undefined);
}

export type Tier = "must_win" | "root_hard" | "a_little" | "doesnt_matter";

export interface RawGoal {
  root_for: string;
  against: string;
  impact_pts: number;
  root_for_win_pct: number;
  value_if_root_for_wins: number | null;
  value_if_root_for_loses: number | null;
  tier: Tier;
  tier_label: string;
  reason_code: string;
  reason_label: string;
}

export interface RawKickoff {
  iso: string | null;
  day: string;
  time: string | null;
  label: string;
  tz: string;
}

export interface RawGame {
  game_id: string;
  away: string;
  home: string;
  kickoff: RawKickoff;
  goals: Partial<Record<GoalKey, RawGoal>>;
}

export interface RawPayload {
  run: {
    run_id: number;
    created_at: string;
    season: number;
    week: number;
    n_sims: number;
    data_as_of: string;
    model_version: string;
  };
  team: {
    abbr: string;
    name: string | null;
    nick: string | null;
    conference: string | null;
    division: string | null;
    record: { wins: number; losses: number; ties: number; text: string };
  };
  odds: {
    team: string;
    playoff_pct: number;
    division_pct: number;
    top_seed_pct: number;
    avg_seed: number | null;
  } | null;
  nicknames: Record<string, string>;
  weeks: { week: number; games: RawGame[] }[];
}

/** What one goal says about one game, already resolved to display strings. */
export interface GoalView {
  goal: RankableGoal;
  label: string;
  rootFor: string;
  rootForNick: string;
  againstNick: string;
  impact: number;
  rootForWinPct: number;
  /** The goal's value when root_for wins / loses. Null for runs saved before
   *  these were stored. */
  valueIfWin: number | null;
  valueIfLose: number | null;
  tier: Tier;
  tierLabel: string;
  reasonCode: string;
  /** The other team the reason is about, for the plain-English sentence. */
  subjectNick: string | null;
}

/** What the list can be ranked by: one goal, or all three combined. */
export type Ranking = RankableGoal | "overall";

/** How much each goal counts toward the combined Root score. They sum to 1,
 *  so the score reads as a weighted average swing in percentage points.
 *  Playoffs leads because getting in is the season; the division adds a home
 *  game; the #1 seed adds the bye. Tune here -- nothing else hard-codes them. */
export const OVERALL_WEIGHTS: Partial<Record<RankableGoal, number>> = {
  playoffs: 0.5,
  division: 0.3,
  top_seed: 0.2,
};

/** Tank mode's "overall" is draft position alone. It is not blended with the
 *  #1-pick chance because the two are in different units (picks vs
 *  percentage points); a weighted sum of them would mean nothing. Tank mode
 *  therefore never offers an "Overall" ranking -- this only orients the
 *  shared detail table to the side that helps your draft position. */
export const TANK_WEIGHTS: Partial<Record<RankableGoal, number>> = {
  draft: 1,
};

/** One goal's odds, oriented to the team the overall score says to root for. */
export interface GoalShift {
  goal: RankableGoal;
  label: string;
  /** The team's odds right now, before this game is played (for draft
   *  position: the average projected pick). */
  current: number;
  /** The team's odds if the overall root-for team wins / loses. Null for
   *  runs saved before these were stored. */
  ifRootWins: number | null;
  ifRootLoses: number | null;
  /** False when this goal's swing is inside simulation noise. */
  real: boolean;
}

/** All three goals folded into one number. */
export interface OverallView {
  rootFor: string;
  rootForNick: string;
  againstNick: string;
  /** Weighted swing in points, 0 when every goal is inside the noise. */
  score: number;
  /** Chance the root-for team wins the game. */
  rootForWinPct: number;
  /** The goal this game moves the most (largest real swing), or null. */
  biggestGoal: RankableGoal | null;
  /** The goal whose reason best explains the pick: the largest weighted
   *  contribution pointing the same way as the overall call. */
  reasonGoal: RankableGoal;
  shifts: GoalShift[];
}

export interface GameView {
  gameId: string;
  awayNick: string;
  homeNick: string;
  kickoff: string;
  kickoffTz: string;
  isOwnGame: boolean;
  /** One entry per goal of the page's mode (MODE_GOALS). The server drops
   *  any game missing one of them, so every goal of the mode is present. */
  goals: Partial<Record<RankableGoal, GoalView>>;
  overall: OverallView;
  /** Neither team is in the viewer's conference: such a game can reach their
   *  odds only through tiny tiebreaker effects, and the model never ranks it
   *  (hatewatch/impacts.py `_other_conference`). */
  otherConference: boolean;
}

/** One team in the picker. `colour` is already validated as #RRGGBB, or
 *  null, so it is safe to put in a style attribute. */
export interface TeamEntry {
  abbr: string;
  nick: string;
  conference: string;
  /** "East", "North"... -- the conference prefix is dropped for display. */
  division: string;
  colour: string | null;
}

export interface PageData {
  /** The banner colours for this team. */
  theme: TeamTheme;
  /** All 32 teams, ordered by conference, division, nickname. */
  directory: TeamEntry[];
  teamNick: string;
  teamName: string;
  teamAbbr: string;
  division: string;
  conference: string;
  recordText: string;
  week: number;
  season: number;
  playoffPct: number;
  divisionPct: number;
  topSeedPct: number;
  /** Tank mode's numbers. Null for runs saved before tank mode existed. */
  avgDraftPick: number | null;
  topPickPct: number | null;
  top5PickPct: number | null;
  mode: Mode;
  /** The goals this page ranks by, in display order. */
  goals: readonly RankableGoal[];
  updatedLabel: string;
  /** How many seasons the latest run simulated, from sim_runs.n_sims. */
  nSims: number;
  defaultGoal: Ranking;
  ownGame: GameView | null;
  games: GameView[];
}
