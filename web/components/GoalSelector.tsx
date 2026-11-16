"use client";

import { GOAL_LABELS, type RankableGoal, type Ranking } from "@/lib/types";

/** A real <select>, styled to match the pill in the design.
 *
 *  Using the native control rather than a custom menu means keyboard support,
 *  screen-reader announcement and the mobile picker all come for free and
 *  correctly. The chevron is drawn alongside and hidden from assistive tech.
 *
 *  In contend mode "Overall" -- the combined Root score -- comes first and
 *  is the default; the single goals stay available for anyone who wants one
 *  race. Tank mode offers its two goals only (see TANK_WEIGHTS for why there
 *  is no tank Overall). */

export default function GoalSelector({
  value,
  onChange,
  goals,
  withOverall,
}: {
  value: Ranking;
  onChange: (ranking: Ranking) => void;
  goals: readonly RankableGoal[];
  withOverall: boolean;
}) {
  const options: { value: Ranking; label: string }[] = [
    ...(withOverall ? [{ value: "overall" as const, label: "Overall" }] : []),
    ...goals.map((g) => ({ value: g, label: GOAL_LABELS[g] })),
  ];
  return (
    <div className="flex items-center gap-2 rounded-full border border-line bg-card py-2 pr-3 pl-4">
      <label htmlFor="rank-goal" className="text-sm text-muted">
        Ranking by
      </label>
      <div className="relative flex items-center">
        <select
          id="rank-goal"
          value={value}
          onChange={(e) => onChange(e.target.value as Ranking)}
          className="appearance-none bg-transparent pr-5 text-sm font-semibold text-brand"
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <span
          aria-hidden="true"
          className="pointer-events-none absolute right-0 text-muted"
        >
          ⌄
        </span>
      </div>
    </div>
  );
}
