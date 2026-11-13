"use client";

import { GOAL_LABELS, RANKABLE_GOALS, type RankableGoal } from "@/lib/types";

/** A real <select>, styled to match the pill in the design.
 *
 *  Using the native control rather than a custom menu means keyboard support,
 *  screen-reader announcement and the mobile picker all come for free and
 *  correctly. The chevron is drawn alongside and hidden from assistive tech. */

export default function GoalSelector({
  value,
  onChange,
}: {
  value: RankableGoal;
  onChange: (goal: RankableGoal) => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-line bg-card py-2 pr-3 pl-4">
      <label htmlFor="rank-goal" className="text-sm text-muted">
        Ranking by
      </label>
      <div className="relative flex items-center">
        <select
          id="rank-goal"
          value={value}
          onChange={(e) => onChange(e.target.value as RankableGoal)}
          className="appearance-none bg-transparent pr-5 text-sm font-semibold text-brand"
        >
          {RANKABLE_GOALS.map((goal) => (
            <option key={goal} value={goal}>
              {GOAL_LABELS[goal]}
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
