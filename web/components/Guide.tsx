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
 *  LAYOUT. On a phone everything stacks in one column. From the `lg`
 *  breakpoint (1024px) it becomes two: your game and the footer on the left,
 *  the Root-for list on the right. The three blocks are placed into grid
 *  cells explicitly, so the phone order (your game, list, footer) stays the
 *  source order -- screen readers and keyboard users get the same sequence on
 *  every screen size. */

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
    <main className="space-y-6 px-5 py-6 lg:grid lg:grid-cols-[minmax(0,380px)_minmax(0,1fr)] lg:grid-rows-[auto_1fr] lg:items-start lg:gap-x-8 lg:gap-y-6 lg:space-y-0 lg:px-8 lg:py-8">
      <div className="lg:col-start-1 lg:row-start-1">
        {data.ownGame ? (
          <YourGameCard
            game={data.ownGame}
            teamAbbr={data.teamAbbr}
            teamNick={data.teamNick}
            ranking={ranking}
          />
        ) : null}
      </div>

      <div className="space-y-6 lg:col-start-2 lg:row-span-2 lg:row-start-1">
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

      <div className="space-y-6 lg:col-start-1 lg:row-start-2">
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
      </div>
    </main>
  );
}
