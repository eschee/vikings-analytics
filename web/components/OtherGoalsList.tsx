"use client";

import RootForRow from "./RootForRow";
import {
  GOAL_LABELS,
  RANKABLE_GOALS,
  type GameView,
  type RankableGoal,
  type Tier,
} from "@/lib/types";

/** Games that are quiet for the goal you picked but loud for another.
 *
 *  Before this existed they fell into "Doesn't matter", which was wrong in a
 *  way a reader would notice: a division rival's game can be worth five points
 *  in the division race and still be noise for the playoff odds, because
 *  making the playoffs at all barely depends on who wins the North. Filing it
 *  under "doesn't matter" told a fan to ignore a game that mattered to them.
 */

/** How loudly to put it, by how much the other goal moves. */
const STRENGTH: Record<Tier, string> = {
  must_win: "Huge",
  root_hard: "Big",
  a_little: "Worth a little",
  doesnt_matter: "",
};

/** The goal this game matters MOST for, ignoring the one being ranked by. */
function bestOtherGoal(game: GameView, selected: RankableGoal) {
  return RANKABLE_GOALS.filter(
    (g) => g !== selected && game.goals[g].tier !== "doesnt_matter",
  ).sort((a, b) => game.goals[b].impact - game.goals[a].impact)[0];
}

export function otherGoalLine(
  game: GameView,
  selected: RankableGoal,
): string | null {
  const other = bestOtherGoal(game, selected);
  if (!other) return null;
  const view = game.goals[other];
  const strength = STRENGTH[view.tier];
  const goalName = GOAL_LABELS[other].toLowerCase();
  const label = goalName === "#1 seed" ? "the #1 seed" : `the ${goalName}`;
  return `${strength} for ${label}: root for the ${view.rootForNick}.`;
}

export default function OtherGoalsList({
  games,
  selectedGoal,
  teamNick,
  division,
  conference,
  openId,
  onToggle,
}: {
  games: GameView[];
  selectedGoal: RankableGoal;
  teamNick: string;
  division: string;
  conference: string;
  openId: string | null;
  onToggle: (id: string) => void;
}) {
  if (games.length === 0) return null;

  // Rank by how much the other goal moves, so the loudest sits on top.
  const sorted = [...games].sort((a, b) => {
    const ga = bestOtherGoal(a, selectedGoal);
    const gb = bestOtherGoal(b, selectedGoal);
    return (gb ? b.goals[gb].impact : 0) - (ga ? a.goals[ga].impact : 0);
  });

  return (
    <section className="space-y-3">
      <h2 className="font-display text-xl font-bold text-brand">
        Matters for other goals
      </h2>
      <ul className="space-y-3">
        {sorted.map((game) => {
          const other = bestOtherGoal(game, selectedGoal);
          return (
            <RootForRow
              key={game.gameId}
              game={game}
              goal={other ?? selectedGoal}
              teamNick={teamNick}
              division={division}
              conference={conference}
              expanded={openId === game.gameId}
              onToggle={() => onToggle(game.gameId)}
              note={otherGoalLine(game, selectedGoal)}
            />
          );
        })}
      </ul>
    </section>
  );
}
