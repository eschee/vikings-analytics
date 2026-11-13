"use client";

import { useMemo, useState } from "react";

import DoesntMatterList from "./DoesntMatterList";
import OtherGoalsList from "./OtherGoalsList";
import GoalSelector from "./GoalSelector";
import RootForRow from "./RootForRow";
import ShareButton from "./ShareButton";
import YourGameCard from "./YourGameCard";
import { RANKABLE_GOALS, type PageData, type RankableGoal } from "@/lib/types";

/** Everything interactive lives here: the chosen ranking goal and which row
 *  is open. The server does all the data work and hands this a small, finished
 *  view model, so switching goals is instant and nothing refetches.
 *
 *  One row is open at a time. With fourteen games an accordion keeps the list
 *  scannable; opening a second row closes the first. */

export default function Guide({ data }: { data: PageData }) {
  const [goal, setGoal] = useState<RankableGoal>(data.defaultGoal);
  const [openId, setOpenId] = useState<string | null>(null);

  // Three buckets, not two. A game only reaches "doesn't matter" when it is
  // below the noise floor for EVERY goal. One that is quiet for the selected
  // goal but loud for another still belongs on the page -- it just belongs
  // under its own heading, so the main list stays about what was asked for.
  const { matters, otherGoals, ignorable } = useMemo(() => {
    const sorted = [...data.games].sort(
      (a, b) => b.goals[goal].impact - a.goals[goal].impact,
    );
    const matters = sorted.filter((g) => g.goals[goal].tier !== "doesnt_matter");
    const rest = sorted.filter((g) => g.goals[goal].tier === "doesnt_matter");
    const mattersElsewhere = (g: (typeof rest)[number]) =>
      RANKABLE_GOALS.some((k) => g.goals[k].tier !== "doesnt_matter");
    return {
      matters,
      otherGoals: rest.filter(mattersElsewhere),
      ignorable: rest.filter((g) => !mattersElsewhere(g)),
    };
  }, [data.games, goal]);

  return (
    <main className="space-y-6 px-5 py-6">
      {data.ownGame ? (
        <YourGameCard
          game={data.ownGame}
          teamAbbr={data.teamAbbr}
          teamNick={data.teamNick}
          goal={goal}
        />
      ) : null}

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-2xl font-bold text-brand">
            Root for
          </h2>
          <GoalSelector value={goal} onChange={setGoal} />
        </div>

        {/* Shown only when the default was switched because a playoff spot is
            already effectively locked. */}
        {data.defaultGoalNote && goal === data.defaultGoal ? (
          <p className="rounded-xl border border-line bg-card px-4 py-3 text-sm text-muted">
            {data.defaultGoalNote}
          </p>
        ) : null}

        {matters.length > 0 ? (
          <ul className="space-y-3">
            {matters.map((game) => (
              <RootForRow
                key={game.gameId}
                game={game}
                goal={goal}
                teamNick={data.teamNick}
                division={data.division}
                conference={data.conference}
                expanded={openId === game.gameId}
                onToggle={() =>
                  setOpenId((cur) => (cur === game.gameId ? null : game.gameId))
                }
              />
            ))}
          </ul>
        ) : (
          <p className="rounded-2xl border border-line bg-card px-5 py-4 text-sm text-muted">
            No other game this week moves your odds beyond simulation noise.
          </p>
        )}
      </section>

      <OtherGoalsList
        games={otherGoals}
        selectedGoal={goal}
        teamNick={data.teamNick}
        division={data.division}
        conference={data.conference}
        openId={openId}
        onToggle={(id) => setOpenId((cur) => (cur === id ? null : id))}
      />

      <DoesntMatterList games={ignorable} goal={goal} />

      <ShareButton />

      {/* The timestamp lives in the header now, so the footer does not repeat
          it. */}
      <footer className="pb-4 text-center">
        <a
          href="/how-it-works"
          className="inline-block text-sm font-medium text-brand underline underline-offset-4"
        >
          How this works
        </a>
      </footer>
    </main>
  );
}
