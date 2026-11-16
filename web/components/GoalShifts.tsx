import { isPickGoal, type GameView, type RankableGoal } from "@/lib/types";

/** The detail table: for each goal, the team's odds now and what they become
 *  if either side wins.
 *
 *  Columns are oriented to `rootAbbr` -- the team this row tells you to root
 *  for -- so the first outcome column is always the result you want. The
 *  server stores the numbers oriented to the overall pick; when a per-goal
 *  ranking roots for the other side, the two columns are swapped here.
 *
 *  A goal whose swing is inside simulation noise is still listed, greyed and
 *  marked, so the table is complete and nothing looks forgotten.
 *
 *  UNITS. Draft position is an average pick ("#12.4") where a SMALLER number
 *  is better; everything else is a percentage where bigger is better. The
 *  arrow follows the number, the colour follows whether that is good for you
 *  -- so moving from #12.4 to #12.1 is a green ▼.
 */

/** "12%", or one decimal for a small chance, where whole percents would
 *  show the #1-pick odds of most teams as a flat 0%. */
function formatValue(goal: RankableGoal, v: number): string {
  if (isPickGoal(goal)) return `#${v.toFixed(1)}`;
  return v > 0 && v < 10 ? `${v.toFixed(1)}%` : `${v.toFixed(0)}%`;
}

function Delta({
  value,
  current,
  lowerIsBetter,
}: {
  value: number;
  current: number;
  lowerIsBetter: boolean;
}) {
  const d = value - current;
  // Under a tenth of a point rounds to 0.0 -- say "no change" rather than
  // print a direction the number cannot support.
  if (Math.abs(d) < 0.05) {
    return <span className="text-muted">±0</span>;
  }
  const up = d > 0;
  const good = lowerIsBetter ? !up : up;
  return (
    <span className={good ? "text-up" : "text-lose-text"}>
      <span aria-hidden="true">{up ? "▲" : "▼"}</span>
      <span className="sr-only">{up ? "up" : "down"}</span>
      {Math.abs(d).toFixed(1)}
    </span>
  );
}

function Cell({
  goal,
  value,
  current,
}: {
  goal: RankableGoal;
  value: number | null;
  current: number;
}) {
  if (value === null) return <td className="py-1.5 text-right text-muted">—</td>;
  return (
    <td className="py-1.5 text-right whitespace-nowrap tabular-nums">
      <span className="font-semibold text-brand">{formatValue(goal, value)}</span>{" "}
      <span className="text-xs">
        <Delta value={value} current={current} lowerIsBetter={isPickGoal(goal)} />
      </span>
    </td>
  );
}

export default function GoalShifts({
  game,
  rootAbbr,
  rootNick,
  againstNick,
}: {
  game: GameView;
  rootAbbr: string;
  rootNick: string;
  againstNick: string;
}) {
  const flip = rootAbbr !== game.overall.rootFor;

  return (
    <table className="w-full text-sm">
      <caption className="sr-only">
        Your odds now, and if each team wins
      </caption>
      <thead>
        <tr className="text-xs text-muted">
          <th scope="col" className="pb-1 text-left font-medium">
            {game.overall.shifts.some((s) => isPickGoal(s.goal))
              ? "Your draft"
              : "Your odds"}
          </th>
          <th scope="col" className="pb-1 text-right font-medium">Now</th>
          <th scope="col" className="pb-1 text-right font-medium">
            {rootNick} win
          </th>
          <th scope="col" className="pb-1 text-right font-medium">
            {againstNick} win
          </th>
        </tr>
      </thead>
      <tbody className="border-t border-line">
        {game.overall.shifts.map((s) => {
          const ifWin = flip ? s.ifRootLoses : s.ifRootWins;
          const ifLose = flip ? s.ifRootWins : s.ifRootLoses;
          return (
            <tr key={s.goal} className={s.real ? "" : "opacity-60"}>
              <th scope="row" className="py-1.5 text-left font-normal text-muted">
                {s.label}
                {s.real ? null : (
                  <span className="block text-xs">within noise</span>
                )}
              </th>
              <td className="py-1.5 text-right text-muted tabular-nums">
                {formatValue(s.goal, s.current)}
              </td>
              <Cell goal={s.goal} value={ifWin} current={s.current} />
              <Cell goal={s.goal} value={ifLose} current={s.current} />
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
