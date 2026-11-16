import GoalShifts from "./GoalShifts";
import RootMeter from "./RootMeter";
import TierMeter from "./TierMeter";
import type { GameView, Mode, Ranking } from "@/lib/types";

/** The team's own game, pulled out of the list because it is always the
 *  biggest mover and reads better as a headline card than as row one.
 *
 *  In contend mode the table is oriented to the TEAM, not to whoever the
 *  model says to root for. Those are always the same there, but tying it to
 *  the team keeps "Vikings win" literally true if that ever changes.
 *
 *  Tank mode flips it: a loss is what helps the draft position, so the card
 *  says so out loud and the table leads with the opponent winning. */

export default function YourGameCard({
  game,
  teamAbbr,
  teamNick,
  ranking,
  mode,
}: {
  game: GameView;
  teamAbbr: string;
  teamNick: string;
  ranking: Ranking;
  mode: Mode;
}) {
  const isHome = game.homeNick === teamNick;
  const opponent = isHome ? game.awayNick : game.homeNick;
  const matchup = `${teamNick} ${isHome ? "vs" : "at"} ${opponent}`;
  const goalView = ranking === "overall" ? null : (game.goals[ranking] ?? null);
  // Tank mode: root for whoever the draft says -- almost always the opponent.
  const tankRoot = mode === "tank" && game.overall.rootFor !== teamAbbr;

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

      {tankRoot ? (
        <p className="mt-2 text-sm font-medium text-brand">
          Tanking? Root for the {opponent} — a {teamNick} loss helps your
          draft position more than any other result.
        </p>
      ) : null}

      <div className="mt-4">
        <GoalShifts
          game={game}
          rootAbbr={tankRoot ? game.overall.rootFor : teamAbbr}
          rootNick={tankRoot ? opponent : teamNick}
          againstNick={tankRoot ? teamNick : opponent}
        />
      </div>
    </section>
  );
}
