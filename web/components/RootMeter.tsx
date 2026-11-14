/** The Root meter: one bar for the combined Root score.
 *
 *  The bar fills left to right and its colour runs green -> yellow -> red as
 *  the score climbs, like a heat gauge: green is "a little", red is "this one
 *  really matters". Both the length and the colour carry the same signal, so a
 *  colour-blind reader still gets it from the length, and the number is
 *  printed next to the bar in text. The bar itself is decorative and hidden
 *  from screen readers; the visible number is what gets read out.
 */

/** A score at or above this fills the bar. Other games this season top out
 *  around 4-5 points; the team's own game is far above and simply pins full. */
export const METER_FULL_AT = 5;

/** Hue 130 is green, 0 is red, passing through yellow around 50. */
function meterColour(fraction: number): string {
  const hue = Math.round(130 * (1 - fraction));
  return `hsl(${hue} 70% 42%)`;
}

/** `compact` keeps the short bar at every size. The team's own game uses it:
 *  its bar is always full, so length tells nothing there, and the space is
 *  better spent keeping the matchup title on one line. */
export default function RootMeter({
  score,
  compact = false,
}: {
  score: number;
  compact?: boolean;
}) {
  const fraction = Math.min(score / METER_FULL_AT, 1);
  // A real but tiny score still shows a sliver, so it never looks empty.
  const width = score > 0 ? Math.max(fraction * 100, 6) : 0;

  return (
    <span className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className={`block h-2.5 w-20 overflow-hidden rounded-full bg-dot-off ${compact ? "" : "lg:w-36"}`}
      >
        <span
          className="block h-full rounded-full"
          style={{ width: `${width}%`, background: meterColour(fraction) }}
        />
      </span>
      {/* A minimum, not a fixed width: a score like "18.9" is four characters
          and must push the bar left rather than spill out of the card. */}
      <span className="font-display min-w-10 text-right text-lg font-bold text-brand tabular-nums">
        {score.toFixed(1)}
      </span>
    </span>
  );
}
