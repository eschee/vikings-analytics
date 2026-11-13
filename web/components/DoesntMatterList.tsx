"use client";

import { useState } from "react";

import type { GameView, RankableGoal } from "@/lib/types";

/** The games below the noise floor, collapsed by default.
 *
 *  They are listed rather than dropped so the page is visibly complete -- a
 *  fan can confirm a game was considered and judged not to matter, instead of
 *  wondering whether it was missed. */

export default function DoesntMatterList({
  games,
  goal,
}: {
  games: GameView[];
  goal: RankableGoal;
}) {
  const [open, setOpen] = useState(false);
  if (games.length === 0) return null;

  return (
    <section className="rounded-2xl border border-line bg-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="doesnt-matter-panel"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 rounded-2xl px-5 py-4 text-left"
      >
        <span className="font-semibold text-brand">
          Doesn&apos;t matter ({games.length})
        </span>
        <span aria-hidden="true" className="text-muted">
          {open ? "⌃" : "⌄"}
        </span>
      </button>

      <ul
        id="doesnt-matter-panel"
        hidden={!open}
        className="border-t border-line px-5 py-3"
      >
        {games.map((game) => {
          const view = game.goals[goal];
          return (
            <li
              key={game.gameId}
              className="flex items-baseline justify-between gap-3 py-1.5 text-sm"
            >
              <span className="text-brand">
                {game.awayNick} at {game.homeNick}
              </span>
              <span className="shrink-0 text-muted">{game.kickoff}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
