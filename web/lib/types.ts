/** Shapes of the exported JSON (hatewatch/export.py) and the view model the
 *  page renders. Keeping them separate means the UI never reaches into the raw
 *  payload: the server narrows it once, and the client only sees what it
 *  needs. */

import type { TeamTheme } from "./colors";

export type GoalKey = "playoffs" | "division" | "top_seed" | "draft";

/** The three goals the site ranks by. The draft goal is computed and stored,
 *  but deliberately not shown: it tells a fan to root against their own team,
 *  which is not what this page is for. */
export const RANKABLE_GOALS = ["playoffs", "division", "top_seed"] as const;
export type RankableGoal = (typeof RANKABLE_GOALS)[number];

export const GOAL_LABELS: Record<RankableGoal, string> = {
  playoffs: "Playoffs",
  division: "Division",
  top_seed: "#1 seed",
};

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
export const OVERALL_WEIGHTS: Record<RankableGoal, number> = {
  playoffs: 0.5,
  division: 0.3,
  top_seed: 0.2,
};

/** One goal's odds, oriented to the team the overall score says to root for. */
export interface GoalShift {
  goal: RankableGoal;
  label: string;
  /** The team's odds right now, before this game is played. */
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
  /** One entry per rankable goal. */
  goals: Record<RankableGoal, GoalView>;
  overall: OverallView;
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
  updatedLabel: string;
  defaultGoal: Ranking;
  ownGame: GameView | null;
  games: GameView[];
}
