import type { PageData } from "@/lib/types";

/** The purple header: wordmark, team picker, record and week, and the
 *  headline. The headline always states the playoff number even when the list
 *  is ranked by something else, because it is the one figure a fan opens the
 *  page for. */

export default function Header({ data }: { data: PageData }) {
  const headlinePct = `${Math.round(data.playoffPct)}%`;

  return (
    <header className="bg-brand px-5 pt-5 pb-7 text-white">
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
    </header>
  );
}
