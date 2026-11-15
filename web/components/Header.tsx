import Link from "next/link";
import type { CSSProperties } from "react";

import TeamPicker from "./TeamPicker";
import type { PageData } from "@/lib/types";

/** The banner: wordmark, team picker, record and week, and the headline.
 *
 *  COLOURS. The banner takes the team's colours. They arrive as a finished,
 *  contrast-checked theme (lib/colors.ts) and are set here as CSS variables
 *  on the <header>; every element inside reads them through Tailwind's
 *  `bg-(--team-bg)` style classes. One place sets the colours, everything else
 *  just refers to them -- including the picker button.
 *
 *  The headline always states the playoff number even when the list is ranked
 *  by something else, because it is the one figure a fan opens the page for.
 */

export default function Header({ data }: { data: PageData }) {
  const headlinePct = `${Math.round(data.playoffPct)}%`;
  const t = data.theme;
  const vars = {
    "--team-bg": t.bg,
    "--team-fg": t.fg,
    "--team-accent": t.accent,
    "--team-muted": t.muted,
    "--team-line": t.line,
    "--team-soft": t.soft,
  } as CSSProperties;

  return (
    // The band always spans the window. The inner div limits the content with
    // exactly the same widths and padding as <main> in Guide.tsx, so the
    // header text lines up with the cards below. It is also `relative`, so
    // the picker's panel can be positioned under the button.
    <header
      style={vars}
      className="bg-(--team-bg) pt-5 pb-7 text-(--team-fg) lg:pt-6 lg:pb-9"
    >
      <div className="relative mx-auto max-w-[600px] px-5 lg:max-w-[1180px] lg:px-8">
        <div className="flex items-center justify-between gap-3">
          {/* The wordmark goes home, to the team-picking start screen. */}
          <Link
            href="/"
            className="font-display text-xl font-bold tracking-[0.14em]"
          >
            HATEWATCH
            <span className="sr-only"> — choose a different team</span>
          </Link>
          <TeamPicker
            current={data.teamAbbr}
            currentNick={data.teamNick}
            teams={data.directory}
          />
        </div>

        <div className="mt-5 flex items-center justify-between gap-3">
          <p className="text-sm text-(--team-muted)">
            {data.teamNick} {data.recordText} · Week {data.week}
          </p>
          <span className="rounded-full border border-(--team-line) px-3 py-1 text-xs font-medium text-(--team-muted)">
            Updated {data.updatedLabel}
          </span>
        </div>

        <h1 className="font-display mt-3 text-[34px] leading-[1.12] font-bold">
          <span className="text-(--team-accent)">{headlinePct}</span> chance to
          make the playoffs
        </h1>

        {/* The other two goals, so every "now" number in the detail tables
            has a visible starting point. */}
        <dl className="mt-3 flex gap-5 text-sm">
          <div className="flex items-baseline gap-1.5">
            <dt className="text-(--team-muted)">Division</dt>
            <dd className="font-semibold">{Math.round(data.divisionPct)}%</dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-(--team-muted)">#1 seed</dt>
            <dd className="font-semibold">{Math.round(data.topSeedPct)}%</dd>
          </div>
        </dl>

        {/* Says what kind of number this is, right where it is read. The
            longer explanation, including the measured accuracy, is one tap
            away. A plain <a> (full page load) so the how-it-works page's
            back link can tell where the reader came from. */}
        <p className="mt-3 text-xs text-(--team-muted)">
          Model estimate from 100,000 simulated seasons — betting markets may
          differ by a few points.{" "}
          <a
            href="/how-it-works"
            className="font-semibold whitespace-nowrap text-(--team-fg) underline underline-offset-2"
          >
            How it works
          </a>
        </p>
      </div>
    </header>
  );
}
