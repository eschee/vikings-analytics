import TierMeter from "./TierMeter";
import { pct } from "@/lib/format";
import type { GameView, RankableGoal } from "@/lib/types";

/** The team's own game, pulled out of the list because it is always the
 *  biggest mover and reads better as a headline card than as row one.
 *
 *  The two chips are oriented to the TEAM, not to whoever the model says to
 *  root for. For every goal shown here those are the same thing, but tying it
 *  to the team keeps "if they win" literally true if that ever changes. */

export default function YourGameCard({
  game,
  teamAbbr,
  teamNick,
  goal,
}: {
  game: GameView;
  teamAbbr: string;
  teamNick: string;
  goal: RankableGoal;
}) {
  const view = game.goals[goal];
  const isHome = game.homeNick === teamNick;
  const opponent = isHome ? game.awayNick : game.homeNick;
  const matchup = `${teamNick} ${isHome ? "vs" : "at"} ${opponent}`;

  const rootForIsTeam = view.rootFor === teamAbbr;
  const raw = game.goals[goal];
  const ifWin = rootForIsTeam ? raw.valueIfWin : raw.valueIfLose;
  const ifLose = rootForIsTeam ? raw.valueIfLose : raw.valueIfWin;

  return (
    <section className="rounded-2xl border border-line bg-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-xs font-semibold tracking-[0.1em] text-muted uppercase">
            Your game · {game.kickoff}
          </p>
          <h2 className="font-display mt-1 text-2xl font-bold text-brand">
            {matchup}
          </h2>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 pt-1">
          <TierMeter tier={view.tier} />
          <span className="text-sm font-semibold text-brand">
            {view.tierLabel}
          </span>
        </div>
      </div>

      {ifWin !== null && ifLose !== null ? (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <p className="flex items-baseline justify-between rounded-xl bg-chip-win px-4 py-3">
            <span className="text-sm text-muted">If they win</span>
            <span className="font-display text-lg font-bold text-brand">
              {pct(ifWin)}
            </span>
          </p>
          <p className="flex items-baseline justify-between rounded-xl bg-chip-lose px-4 py-3">
            <span className="text-sm text-muted">If they lose</span>
            <span className="font-display text-lg font-bold text-lose-text">
              {pct(ifLose)}
            </span>
          </p>
        </div>
      ) : null}
    </section>
  );
}
