/** Reason codes to plain English.
 *
 *  The export ships a short label ("Division rival"); this turns it into a
 *  sentence a reader understands without knowing how the model works. Each
 *  sentence explains the MECHANISM, because "division rival" alone does not
 *  tell you why a division loss is worth more than any other loss.
 *
 *  Every branch returns a literal string with values interpolated as plain
 *  text. Nothing here is ever HTML. */

import type { GoalView } from "./types";

export function reasonSentence(
  goal: GoalView,
  teamNick: string,
  division: string,
  conference: string,
): string {
  const other = goal.subjectNick;

  switch (goal.reasonCode) {
    case "own_game":
      return `The ${teamNick} are playing. Nothing else on the schedule moves your odds this much.`;

    case "division_rival":
      return other
        ? `The ${other} are in the ${division} with you. A loss for them counts double: it costs them a game AND it helps you in the head-to-head and division-record tiebreakers.`
        : `A ${division} rival is playing, and division results count twice — once in the standings, once in the tiebreakers.`;

    case "wildcard_competitor":
      return other
        ? `The ${other} are chasing the same wild-card spot. Every game they lose is one fewer team ahead of you.`
        : `This game involves a team competing with you for a wild-card spot.`;

    case "top_seed_race":
      return other
        ? `The ${other} are in the running for the ${conference}'s top seed — the one team that gets a first-round bye.`
        : `This game moves the race for the ${conference}'s top seed and its first-round bye.`;

    case "tiebreaker_effect":
      return `Neither team is in the ${conference}, so this can only reach you through strength-of-victory and strength-of-schedule tiebreakers. That is why the effect is tiny.`;

    case "other":
      return other
        ? `The ${other} are in your conference, but their season is close to settled either way, so this barely moves your odds.`
        : `This game is in your conference but barely moves your odds.`;

    default:
      return `This game has a small effect on your odds.`;
  }
}

/** How likely the team you are rooting for is to actually win, in words.
 *  The phrase sets expectations before the number lands. */
export function winChancePhrase(pct: number): string {
  if (pct < 25) return "Long shot";
  if (pct < 45) return "Underdog";
  if (pct <= 55) return "Coin flip";
  if (pct <= 75) return "Favored";
  return "Likely";
}
