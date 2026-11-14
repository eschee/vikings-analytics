import GoalShifts from "./GoalShifts";
import RootMeter from "./RootMeter";
import TierMeter from "./TierMeter";
import type { GameView, Ranking } from "@/lib/types";

/** The team's own game, pulled out of the list because it is always the
 *  biggest mover and reads better as a headline card than as row one.
 *
 *  The table is oriented to the TEAM, not to whoever the model says to root
 *  for. Those are always the same here, but tying it to the team keeps
 *  "Vikings win" literally true if that ever changes. */

export default function YourGameCard({
  game,
  teamAbbr,
  teamNick,
  ranking,
}: {
  game: GameView;
  teamAbbr: string;
  teamNick: string;
  ranking: Ranking;
}) {
  const isHome = game.homeNick === teamNick;
  const opponent = isHome ? game.awayNick : game.homeNick;
  const matchup = `${teamNick} ${isHome ? "vs" : "at"} ${opponent}`;
  const goalView = ranking === "overall" ? null : game.goals[ranking];

  return (
    <section className="rounded-2xl border border-line bg-card p-5">
      {/* The label gets its own line so it never wraps beside the meter;
          the matchup and the meter share the row below it. */}
      <p className="text-xs font-semibold tracking-[0.1em] text-muted uppercase">
        Your game · {game.kickoff}
      </p>
      <div className="mt-1 flex items-center justify-between gap-4">
        <h2 className="font-display min-w-0 text-2xl font-bold text-brand">
          {matchup}
        </h2>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {goalView ? (
            <>
              <TierMeter tier={goalView.tier} />
              <span className="text-sm font-semibold text-brand">
                {goalView.tierLabel}
              </span>
            </>
          ) : (
            <>
              <RootMeter score={game.overall.score} compact />
              <span className="text-xs text-muted">Root score</span>
            </>
          )}
        </div>
      </div>

      <div className="mt-4">
        <GoalShifts
          game={game}
          rootAbbr={teamAbbr}
          rootNick={teamNick}
          againstNick={opponent}
        />
      </div>
    </section>
  );
}
