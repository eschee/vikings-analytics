import type { Metadata } from "next";
import Link from "next/link";

import { directory } from "@/lib/data";
import type { TeamEntry } from "@/lib/types";

/** The start screen: pick your team.
 *
 *  This used to redirect straight to the Vikings. Now every visitor chooses,
 *  from all 32 teams laid out the way the league is: AFC and NFC, each split
 *  into East / North / South / West.
 *
 *  Data: the cached team directory (lib/data.ts `directory()`), one fixed
 *  query with no input. Colours there are already validated as #RRGGBB, so
 *  they are safe in a style attribute. Every link is built from a team
 *  abbreviation in that list, and each team page re-checks its own segment
 *  against the allowlist anyway.
 *
 *  If the database cannot be reached, the screen says so instead of showing
 *  an empty grid that looks like the league has no teams.
 */

export const metadata: Metadata = {
  title: "Hatewatch — who to root for",
  description:
    "Pick your NFL team and see which other games to root for this week, ranked by how much they move your playoff, division and #1 seed odds.",
};

const CONFERENCES = ["AFC", "NFC"] as const;
const DIVISIONS = ["East", "North", "South", "West"] as const;

function TeamButton({ team }: { team: TeamEntry }) {
  return (
    <li>
      <Link
        href={`/${team.abbr.toLowerCase()}`}
        className="flex items-center gap-3 rounded-xl border border-line bg-card px-3 py-3 font-semibold text-brand hover:bg-page"
      >
        <span
          aria-hidden="true"
          className="block h-6 w-1.5 shrink-0 rounded-full bg-dot-off"
          style={team.colour ? { background: team.colour } : undefined}
        />
        {team.nick}
      </Link>
    </li>
  );
}

export default async function Home() {
  let teams: TeamEntry[] = [];
  let failed = false;
  try {
    teams = (await directory()).entries;
  } catch {
    failed = true;
  }

  return (
    <>
      <header className="bg-brand pt-6 pb-9 text-white">
        <div className="mx-auto max-w-[600px] px-5 lg:max-w-[1180px] lg:px-8">
          <span className="font-display text-xl font-bold tracking-[0.14em]">
            HATEWATCH
          </span>
          <h1 className="font-display mt-6 text-[34px] leading-[1.12] font-bold">
            Who should you root for{" "}
            <span className="text-gold">this week?</span>
          </h1>
          <p className="mt-3 max-w-[560px] text-sm leading-relaxed text-lavender">
            Pick your team. We&apos;ll rank every other game by how much it
            moves your chances of making the playoffs, winning the division and
            earning the #1 seed.
          </p>
        </div>
      </header>

      <main className="mx-auto max-w-[600px] px-5 py-8 lg:max-w-[1180px] lg:px-8">
        {failed || teams.length === 0 ? (
          <p className="rounded-2xl border border-line bg-card px-5 py-4 text-sm text-muted">
            The team list can&apos;t be loaded right now. Please try again in a
            minute.
          </p>
        ) : (
          <nav
            aria-label="Choose your team"
            className="grid gap-8 lg:grid-cols-2 lg:gap-10"
          >
            {CONFERENCES.map((conf) => (
              <section key={conf}>
                <h2 className="font-display border-b border-line pb-2 text-2xl font-bold text-brand">
                  {conf}
                </h2>
                <div className="mt-4 grid grid-cols-1 gap-5 sm:grid-cols-2">
                  {DIVISIONS.map((div) => (
                    <div key={div}>
                      <h3 className="text-xs font-semibold tracking-[0.1em] text-muted uppercase">
                        {conf} {div}
                      </h3>
                      <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-1">
                        {teams
                          .filter((t) => t.conference === conf && t.division === div)
                          .map((t) => (
                            <TeamButton key={t.abbr} team={t} />
                          ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </nav>
        )}

        <footer className="mt-10 pb-4 text-center">
          <a
            href="/how-it-works"
            className="inline-block text-sm font-medium text-brand underline underline-offset-4"
          >
            How this works
          </a>
        </footer>
      </main>
    </>
  );
}
