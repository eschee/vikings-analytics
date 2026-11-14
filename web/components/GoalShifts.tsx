import type { GameView } from "@/lib/types";

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
 */

function Delta({ value, current }: { value: number; current: number }) {
  const d = value - current;
  // Under a tenth of a point rounds to 0.0 -- say "no change" rather than
  // print a direction the number cannot support.
  if (Math.abs(d) < 0.05) {
    return <span className="text-muted">±0</span>;
  }
  const up = d > 0;
  return (
    <span className={up ? "text-up" : "text-lose-text"}>
      <span aria-hidden="true">{up ? "▲" : "▼"}</span>
      <span className="sr-only">{up ? "up" : "down"}</span>
      {Math.abs(d).toFixed(1)}
    </span>
  );
}

function Cell({ value, current }: { value: number | null; current: number }) {
  if (value === null) return <td className="py-1.5 text-right text-muted">—</td>;
  return (
    <td className="py-1.5 text-right whitespace-nowrap tabular-nums">
      <span className="font-semibold text-brand">{value.toFixed(0)}%</span>{" "}
      <span className="text-xs">
        <Delta value={value} current={current} />
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
          <th scope="col" className="pb-1 text-left font-medium">Your odds</th>
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
                {s.current.toFixed(0)}%
              </td>
              <Cell value={ifWin} current={s.current} />
              <Cell value={ifLose} current={s.current} />
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
