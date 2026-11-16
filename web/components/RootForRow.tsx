"use client";

import GoalShifts from "./GoalShifts";
import RootMeter from "./RootMeter";
import TierMeter from "./TierMeter";
import { pct } from "@/lib/format";
import { reasonSentence, winChancePhrase } from "@/lib/reasons";
import {
  GOAL_LABELS,
  MODE_GOALS,
  OVERALL_WEIGHTS,
  type GameView,
  type Ranking,
} from "@/lib/types";

/** One row of the "Root for" list.
 *
 *  Collapsed it shows who to root for, who they are playing and a meter. In
 *  the Overall ranking that is the Root meter -- one combined number -- plus
 *  which goal the game moves most. Ranked by a single goal it is that goal's
 *  three-dot tier, as before.
 *
 *  Expanded, it shows the reason in plain English and the GoalShifts table:
 *  each goal's odds now, and if either team wins.
 *
 *  The whole summary is a <button> carrying aria-expanded and aria-controls,
 *  so the state is announced and the panel is associated with its trigger. */

// Only contend mode has an Overall ranking, so only its weights are described.
const WEIGHTS_TEXT = MODE_GOALS.contend.map(
  (g) =>
    `${GOAL_LABELS[g].toLowerCase()} ${Math.round((OVERALL_WEIGHTS[g] ?? 0) * 100)}%`,
).join(", ");

export default function RootForRow({
  game,
  ranking,
  teamNick,
  division,
  conference,
  expanded,
  onToggle,
  note,
}: {
  game: GameView;
  ranking: Ranking;
  teamNick: string;
  division: string;
  conference: string;
  expanded: boolean;
  onToggle: () => void;
  /** Shown under the matchup when the row is listed because it matters for a
   *  goal other than the one being ranked by. */
  note?: string | null;
}) {
  const overall = game.overall;
  const isOverall = ranking === "overall";
  const goalView = isOverall ? null : (game.goals[ranking] ?? null);

  const rootFor = goalView?.rootFor ?? overall.rootFor;
  const rootForNick = goalView?.rootForNick ?? overall.rootForNick;
  const againstNick = goalView?.againstNick ?? overall.againstNick;
  const winPct = goalView?.rootForWinPct ?? overall.rootForWinPct;
  // The reason should explain the call shown on the row.
  const reasonView = goalView ?? game.goals[overall.reasonGoal]!;

  const mostly =
    isOverall && overall.biggestGoal
      ? `Moves your ${GOAL_LABELS[overall.biggestGoal].toLowerCase()} odds most`
      : null;

  const panelId = `panel-${game.gameId}`;
  const buttonId = `row-${game.gameId}`;

  return (
    <li className="rounded-2xl border border-line bg-card">
      <h3>
        <button
          type="button"
          id={buttonId}
          aria-expanded={expanded}
          aria-controls={panelId}
          onClick={onToggle}
          className="flex w-full items-center justify-between gap-4 rounded-2xl px-5 py-4 text-left"
        >
          <span className="min-w-0">
            <span className="font-display block text-xl font-bold text-brand">
              {rootForNick}
            </span>
            <span className="mt-0.5 block text-sm text-muted">
              over the {againstNick} · {game.kickoff}
            </span>
            {mostly ? (
              <span className="mt-1 block text-sm font-medium text-brand">
                {mostly}
              </span>
            ) : null}
            {note ? (
              <span className="mt-1 block text-sm font-medium text-brand">
                {note}
              </span>
            ) : null}
          </span>
          <span className="flex shrink-0 flex-col items-end gap-1">
            {goalView ? (
              <>
                <TierMeter tier={goalView.tier} />
                <span className="text-sm font-semibold text-brand">
                  {goalView.tierLabel}
                </span>
              </>
            ) : (
              <>
                <RootMeter score={overall.score} />
                <span className="text-xs text-muted">Root score</span>
              </>
            )}
          </span>
        </button>
      </h3>

      <div
        id={panelId}
        role="region"
        aria-labelledby={buttonId}
        hidden={!expanded}
        className="space-y-4 border-t border-line px-5 py-4"
      >
        <p className="text-sm leading-relaxed text-muted">
          {reasonSentence(reasonView, teamNick, division, conference)}
        </p>

        <GoalShifts
          game={game}
          rootAbbr={rootFor}
          rootNick={rootForNick}
          againstNick={againstNick}
        />

        <p className="text-sm text-muted">
          <span className="font-semibold text-brand">
            {winChancePhrase(winPct)}:
          </span>{" "}
          the {rootForNick} have a {pct(winPct)} chance to win.
        </p>

        {isOverall ? (
          <p className="text-xs text-muted">
            The Root score blends all three swings, weighted {WEIGHTS_TEXT}.
            Swings inside simulation noise count as zero, and goals that want
            opposite teams partly cancel.
          </p>
        ) : null}
      </div>
    </li>
  );
}
