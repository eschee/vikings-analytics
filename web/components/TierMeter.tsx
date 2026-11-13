import type { Tier } from "@/lib/types";

/** Three dots showing how much a game matters: Must win is three filled,
 *  Root hard two, A little one. The dots are decorative -- the tier label sits
 *  next to them in text -- so they are hidden from screen readers rather than
 *  read out as "circle circle circle". */

const FILLED: Record<Tier, number> = {
  must_win: 3,
  root_hard: 2,
  a_little: 1,
  doesnt_matter: 0,
};

export default function TierMeter({ tier }: { tier: Tier }) {
  const filled = FILLED[tier] ?? 0;
  return (
    <span className="flex gap-1" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className={`block h-2 w-2 rounded-full ${
            i < filled ? "bg-dot-on" : "bg-dot-off"
          }`}
        />
      ))}
    </span>
  );
}
