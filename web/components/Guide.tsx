"use client";

import { useMemo, useState } from "react";

import DoesntMatterList from "./DoesntMatterList";
import OtherGoalsList from "./OtherGoalsList";
import GoalSelector from "./GoalSelector";
import RootForRow from "./RootForRow";
import ShareButton from "./ShareButton";
import YourGameCard from "./YourGameCard";
import {
  RANKABLE_GOALS,
  type GameView,
  type PageData,
  type Ranking,
} from "@/lib/types";

/** Everything interactive lives here: the chosen ranking and which row is
 *  open. The server does all the data work and hands this a small, finished
 *  view model, so switching rankings is instant and nothing refetches.
 *
 *  One row is open at a time. With fourteen games an accordion keeps the list
 *  scannable; opening a second row closes the first.
 *
 *  LAYOUT. On a phone everything stacks: your game, the list, then the share
 *  button and footer. From the `lg` breakpoint (1024px, any Mac) it becomes
 *  two columns centred at 1180px: a 420px left column holding your game, the
 *  share button and footer, which stays put (sticky) while the list on the
 *  right scrolls past it.
 *
 *  The share button and footer therefore appear in two places in the markup
 *  -- in the left column (shown on lg only) and at the bottom (hidden on lg).
 *  Exactly one is ever displayed, and `display: none` also removes the other
 *  from the accessibility tree, so nobody hears it twice. The alternative,
 *  reordering one copy with CSS grid, would make the visual order differ from
 *  the reading order on one of the two layouts. */

function Extras() {
  return (
    <>
      <ShareButton />
      {/* The timestamp lives in the header, so the footer does not repeat
          it. */}
      <footer className="pb-4 text-center">
        <a
          href="/how-it-works"
          className="inline-block text-sm font-medium text-brand underline underline-offset-4"
        >
          How this works
        </a>
      </footer>
    </>
  );
}

function strength(game: GameView, ranking: Ranking): number {
  return ranking === "overall"
    ? game.overall.score
    : game.goals[ranking].impact;
}

function matters(game: GameView, ranking: Ranking): boolean {
  return ranking === "overall"
    ? game.overall.score > 0
    : game.goals[ranking].tier !== "doesnt_matter";
}

export default function Guide({ data }: { data: PageData }) {
  const [ranking, setRanking] = useState<Ranking>(data.defaultGoal);
  const [openId, setOpenId] = useState<string | null>(null);
  const toggle = (id: string) => setOpenId((cur) => (cur === id ? null : id));

  // Three buckets, not two. A game only reaches "doesn't matter" when it is
  // below the noise floor for EVERY goal. One that is quiet for the selected
  // goal but loud for another still belongs on the page -- it just belongs
  // under its own heading. In the Overall ranking that middle bucket is
  // always empty: a game loud for any goal already has a Root score.
  const { listed, otherGoals, ignorable } = useMemo(() => {
    const sorted = [...data.games].sort(
      (a, b) => strength(b, ranking) - strength(a, ranking),
    );
    const listed = sorted.filter((g) => matters(g, ranking));
    const rest = sorted.filter((g) => !matters(g, ranking));
    const mattersElsewhere = (g: GameView) =>
      RANKABLE_GOALS.some((k) => g.goals[k].tier !== "doesnt_matter");
    return {
      listed,
      otherGoals: rest.filter(mattersElsewhere),
      ignorable: rest.filter((g) => !mattersElsewhere(g)),
    };
  }, [data.games, ranking]);

  return (
    <main className="space-y-6 px-5 py-6 lg:mx-auto lg:grid lg:max-w-[1180px] lg:grid-cols-[420px_minmax(0,1fr)] lg:items-start lg:gap-10 lg:space-y-0 lg:px-8 lg:py-8">
      <aside className="space-y-6 lg:sticky lg:top-8">
        {data.ownGame ? (
          <YourGameCard
            game={data.ownGame}
            teamAbbr={data.teamAbbr}
            teamNick={data.teamNick}
            ranking={ranking}
          />
        ) : null}
        <div className="hidden space-y-6 lg:block">
          <Extras />
        </div>
      </aside>

      <div className="space-y-6">
        <section className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-display text-2xl font-bold text-brand">
              Root for
            </h2>
            <GoalSelector value={ranking} onChange={setRanking} />
          </div>

          {listed.length > 0 ? (
            <ul className="space-y-3">
              {listed.map((game) => (
                <RootForRow
                  key={game.gameId}
                  game={game}
                  ranking={ranking}
                  teamNick={data.teamNick}
                  division={data.division}
                  conference={data.conference}
                  expanded={openId === game.gameId}
                  onToggle={() => toggle(game.gameId)}
                />
              ))}
            </ul>
          ) : (
            <p className="rounded-2xl border border-line bg-card px-5 py-4 text-sm text-muted">
              No other game this week moves your odds beyond simulation noise.
            </p>
          )}
        </section>

        {ranking !== "overall" ? (
          <OtherGoalsList
            games={otherGoals}
            selectedGoal={ranking}
            teamNick={data.teamNick}
            division={data.division}
            conference={data.conference}
            openId={openId}
            onToggle={toggle}
          />
        ) : null}

        <DoesntMatterList games={ignorable} />
      </div>

      <div className="space-y-6 lg:hidden">
        <Extras />
      </div>
    </main>
  );
}
