"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import type { TeamEntry } from "@/lib/types";

/** The team switcher in the banner's top-right corner.
 *
 *  A disclosure, not an ARIA "menu": a button that shows and hides a panel of
 *  ordinary links. Menus promise arrow-key navigation and a special
 *  announcement; a list of links needs neither, and Tab already moves through
 *  them. The button carries aria-expanded so its state is announced.
 *
 *  The panel lays the 32 teams out the way the league is organised: AFC and
 *  NFC side by side, each split into its four divisions. It always has a white
 *  background with the house purple text, whatever the banner colour, so it
 *  reads the same on every team's page.
 *
 *  Closes on Escape (returning focus to the button), on a click outside, and
 *  when a team is chosen.
 */

const CONFERENCES = ["AFC", "NFC"] as const;
const DIVISIONS = ["East", "North", "South", "West"] as const;

export default function TeamPicker({
  current,
  currentNick,
  teams,
}: {
  current: string;
  currentNick: string;
  teams: TeamEntry[];
}) {
  const [open, setOpen] = useState(false);
  const wrapper = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    }
    function onPointer(e: PointerEvent) {
      if (wrapper.current && !wrapper.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  return (
    <div ref={wrapper}>
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-full border border-(--team-line) bg-(--team-soft) px-4 py-2 text-sm font-semibold text-(--team-fg)"
      >
        {currentNick}
        <span aria-hidden="true" className="text-(--team-muted)">
          {open ? "⌃" : "⌄"}
        </span>
        <span className="sr-only">— choose a team</span>
      </button>

      {/* Positioned against the banner's content box (which is `relative`),
          so on a phone it spans nearly the full width under the button
          instead of hanging off the screen. From 640px it is a dropdown
          aligned to the button's right edge (the right values match the
          banner's padding). */}
      <div
        id={panelId}
        hidden={!open}
        className="absolute inset-x-3 top-14 z-20 rounded-2xl border border-line bg-card p-4 text-brand shadow-xl sm:inset-x-auto sm:right-5 sm:w-[520px] lg:right-8"
      >
        <nav aria-label="All teams" className="grid grid-cols-2 gap-x-4 sm:gap-x-6">
          {CONFERENCES.map((conf) => (
            <section key={conf}>
              <h2 className="font-display border-b border-line pb-1 text-sm font-bold tracking-[0.12em]">
                {conf}
              </h2>
              {DIVISIONS.map((div) => {
                const inDiv = teams.filter(
                  (t) => t.conference === conf && t.division === div,
                );
                return (
                  <div key={div} className="mt-3">
                    <h3 className="text-xs font-semibold tracking-[0.1em] text-muted uppercase">
                      {div}
                    </h3>
                    <ul className="mt-1">
                      {inDiv.map((t) => {
                        const isCurrent = t.abbr === current;
                        return (
                          <li key={t.abbr}>
                            <Link
                              href={`/${t.abbr.toLowerCase()}`}
                              aria-current={isCurrent ? "page" : undefined}
                              onClick={() => setOpen(false)}
                              className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-page ${
                                isCurrent ? "bg-page font-semibold" : ""
                              }`}
                            >
                              <span
                                aria-hidden="true"
                                className="block h-2.5 w-2.5 shrink-0 rounded-full border border-line"
                                style={
                                  t.colour ? { background: t.colour } : undefined
                                }
                              />
                              {t.nick}
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
            </section>
          ))}
        </nav>
      </div>
    </div>
  );
}
