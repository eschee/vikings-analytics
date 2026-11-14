import type { PageData } from "@/lib/types";

/** The purple header: wordmark, team picker, record and week, and the
 *  headline. The headline always states the playoff number even when the list
 *  is ranked by something else, because it is the one figure a fan opens the
 *  page for. */

export default function Header({ data }: { data: PageData }) {
  const headlinePct = `${Math.round(data.playoffPct)}%`;

  return (
    // The purple band always spans the window. The inner div limits the
    // content with exactly the same widths and padding as <main> in
    // Guide.tsx, so the header text lines up with the cards below.
    <header className="bg-brand pt-5 pb-7 text-white lg:pt-6 lg:pb-9">
      <div className="mx-auto max-w-[600px] px-5 lg:max-w-[1180px] lg:px-8">
      <div className="flex items-center justify-between gap-3">
        <span className="font-display text-xl font-bold tracking-[0.14em]">
          HATEWATCH
        </span>

        {/* Only one team exists so far. The control is still a real button so
            it is reachable by keyboard, and announces that it is inactive
            rather than silently doing nothing. */}
        <button
          type="button"
          aria-disabled="true"
          className="flex items-center gap-2 rounded-full border border-brand-line bg-brand-soft px-4 py-2 text-sm font-semibold text-white"
        >
          {data.teamNick}
          <span aria-hidden="true" className="text-lavender">
            ⌄
          </span>
          <span className="sr-only">
            — only the {data.teamNick} are available right now
          </span>
        </button>
      </div>

      <div className="mt-5 flex items-center justify-between gap-3">
        <p className="text-sm text-lavender">
          {data.teamNick} {data.recordText} · Week {data.week}
        </p>
        <span className="rounded-full border border-brand-line px-3 py-1 text-xs font-medium text-lavender">
          Updated {data.updatedLabel}
        </span>
      </div>

      <h1 className="font-display mt-3 text-[34px] leading-[1.12] font-bold">
        <span className="text-gold">{headlinePct}</span> chance to make the
        playoffs
      </h1>

      {/* The other two goals, so every "now" number in the detail tables
          has a visible starting point. */}
      <dl className="mt-3 flex gap-5 text-sm">
        <div className="flex items-baseline gap-1.5">
          <dt className="text-lavender">Division</dt>
          <dd className="font-semibold">{Math.round(data.divisionPct)}%</dd>
        </div>
        <div className="flex items-baseline gap-1.5">
          <dt className="text-lavender">#1 seed</dt>
          <dd className="font-semibold">{Math.round(data.topSeedPct)}%</dd>
        </div>
      </dl>
      </div>
    </header>
  );
}
