"use client";

import { useState } from "react";

import type { GameView } from "@/lib/types";

/** The games with no measurable effect this week, in two honest groups,
 *  collapsed by default.
 *
 *  "Too close to call": at least one team is in your conference, so the game
 *  CAN move your odds -- but this week the effect is under 0.1 points or
 *  too small to measure, so even its direction is uncertain. Naming a
 *  side here would be a guess dressed up as advice.
 *
 *  "Can't really affect you": both teams are in the other conference. They
 *  reach you only through tiny strength-of-schedule tiebreakers.
 *
 *  They are listed rather than dropped so the page is visibly complete -- a
 *  fan can confirm a game was considered, instead of wondering if it was
 *  missed.
 */

function Group({
  id,
  title,
  note,
  games,
}: {
  id: string;
  title: string;
  note: string;
  games: GameView[];
}) {
  const [open, setOpen] = useState(false);
  if (games.length === 0) return null;
  const panelId = `${id}-panel`;

  return (
    <section className="rounded-2xl border border-line bg-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 rounded-2xl px-5 py-4 text-left"
      >
        <span className="font-semibold text-brand">
          {title} ({games.length})
        </span>
        <span aria-hidden="true" className="text-muted">
          {open ? "⌃" : "⌄"}
        </span>
      </button>

      <div id={panelId} hidden={!open} className="border-t border-line px-5 py-3">
        <p className="pb-2 text-sm text-muted">{note}</p>
        <ul>
          {games.map((game) => (
            <li
              key={game.gameId}
              className="flex items-baseline justify-between gap-3 py-1.5 text-sm"
            >
              <span className="text-brand">
                {game.awayNick} at {game.homeNick}
              </span>
              <span className="shrink-0 text-muted">{game.kickoff}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function DoesntMatterList({
  games,
  conference,
}: {
  games: GameView[];
  conference: string;
}) {
  const close = games.filter((g) => !g.otherConference);
  const unreachable = games.filter((g) => g.otherConference);
  const other = conference === "AFC" ? "NFC" : "AFC";

  return (
    <>
      <Group
        id="too-close"
        title="Too close to call"
        note="These involve your conference but move your odds by less than a tenth of a point, or by less than we can measure — so we won't guess a side."
        games={close}
      />
      <Group
        id="cant-affect"
        title="Can't really affect you"
        note={`Both teams are in the ${other}. They reach you only through tiny tiebreaker effects.`}
        games={unreachable}
      />
    </>
  );
}
