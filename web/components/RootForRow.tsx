"use client";

import TierMeter from "./TierMeter";
import { points, pct } from "@/lib/format";
import { reasonSentence, winChancePhrase } from "@/lib/reasons";
import { RANKABLE_GOALS, type GameView, type RankableGoal } from "@/lib/types";

/** One row of the "Root for" list.
 *
 *  Collapsed it shows only who to root for, who they are playing and the tier
 *  meter -- no numbers, which keeps the list scannable. Everything numeric
 *  lives in the expanded panel.
 *
 *  The whole summary is a <button> carrying aria-expanded and aria-controls,
 *  so the state is announced and the panel is associated with its trigger. */

export default function RootForRow({
  game,
  goal,
  teamNick,
  division,
  conference,
  expanded,
  onToggle,
  note,
}: {
  game: GameView;
  goal: RankableGoal;
  teamNick: string;
  division: string;
  conference: string;
  expanded: boolean;
  onToggle: () => void;
  /** Shown under the matchup when the row is listed because it matters for a
   *  goal other than the one being ranked by. */
  note?: string | null;
}) {
  const view = game.goals[goal];
  const panelId = `panel-${game.gameId}`;
  const buttonId = `row-${game.gameId}`;

  // Where the goals point at different teams, say so once, in the panel.
  const disagreeing = RANKABLE_GOALS.filter(
    (g) => game.goals[g].rootFor !== view.rootFor,
  );

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
              {view.rootForNick}
            </span>
            <span className="mt-0.5 block text-sm text-muted">
              over the {view.againstNick} · {game.kickoff}
            </span>
            {note ? (
              <span className="mt-1 block text-sm font-medium text-brand">
                {note}
              </span>
            ) : null}
          </span>
          <span className="flex shrink-0 flex-col items-end gap-1">
            <TierMeter tier={view.tier} />
            <span className="text-sm font-semibold text-brand">
              {view.tierLabel}
            </span>
          </span>
        </button>
      </h3>

      <div
        id={panelId}
        role="region"
        aria-labelledby={buttonId}
        hidden={!expanded}
        className="border-t border-line px-5 py-4"
      >
        <p className="text-sm leading-relaxed text-muted">
          {reasonSentence(view, teamNick, division, conference)}
        </p>

        <dl className="mt-4 space-y-1.5">
          {RANKABLE_GOALS.map((g) => {
            const gv = game.goals[g];
            return (
              <div key={g} className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-muted">{gv.label}</dt>
                <dd className="text-sm font-semibold text-brand">
                  {gv.tier === "doesnt_matter"
                    ? "No real effect"
                    : `${gv.rootForNick} ${points(gv.impact)}`}
                </dd>
              </div>
            );
          })}
        </dl>

        <p className="mt-4 text-sm text-muted">
          <span className="font-semibold text-brand">
            {winChancePhrase(view.rootForWinPct)}:
          </span>{" "}
          the {view.rootForNick} have a {pct(view.rootForWinPct)} chance to win.
        </p>

        {disagreeing.length > 0 ? (
          <p className="mt-3 rounded-xl bg-page px-3 py-2 text-sm text-muted">
            These goals disagree —{" "}
            {disagreeing
              .map((g) => `${game.goals[g].label} wants the ${game.goals[g].rootForNick}`)
              .join(", ")}
            .
          </p>
        ) : null}
      </div>
    </li>
  );
}
