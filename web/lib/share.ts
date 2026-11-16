/** The one-line summary used by the share button and the link-preview image,
 *  so the message and the picture always say the same thing.
 *
 *  "Who to root for" here means the Overall ranking: the games with the
 *  highest combined Root score, excluding the team's own game (rooting for
 *  yourself goes without saying). */

import { chance, pickLabel } from "./format";
import type { PageData } from "./types";

/** How many teams to name. Three fits a text message and a preview card. */
const TOP_N = 3;

/** "A", "A and B", "A, B and C". */
function list(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export interface ShareSummary {
  title: string;
  /** e.g. "Vikings fans, week 10: root for the Patriots, Cardinals and
   *  Raiders. 74% chance to make the playoffs." */
  text: string;
  /** The nicknames named in `text`, most important first. */
  rootFor: string[];
}

export function shareSummary(data: PageData): ShareSummary {
  // Contend: the Overall ranking. Tank: draft position, its default -- in
  // tank mode `overall` is built from draft position alone (TANK_WEIGHTS).
  const rootFor = [...data.games]
    .filter((g) => g.overall.score > 0)
    .sort((a, b) => b.overall.score - a.overall.score)
    .slice(0, TOP_N)
    .map((g) => g.overall.rootForNick);

  if (data.mode === "tank") {
    const lead = `Tanking ${data.teamNick} fans, week ${data.week}:`;
    const pick =
      data.avgDraftPick === null
        ? ""
        : ` Projected pick ${pickLabel(data.avgDraftPick)}, ${chance(
            data.topPickPct ?? 0,
          )} chance at #1.`;
    // The own game is listed separately, but for tanking it is THE result
    // to root for, so name it first.
    const own = data.ownGame?.overall;
    const names = [
      ...(own && own.score > 0 && own.rootFor !== data.teamAbbr
        ? [own.rootForNick]
        : []),
      ...rootFor,
    ].slice(0, TOP_N);
    return {
      title: `Who should tanking ${data.teamNick} fans root for? — Hatewatch`,
      text:
        names.length > 0
          ? `${lead} root for the ${list(names)}.${pick}`
          : `${lead} no game this week moves the draft order.${pick}`,
      rootFor: names,
    };
  }

  const pct = `${Math.round(data.playoffPct)}% chance to make the playoffs.`;
  const lead = `${data.teamNick} fans, week ${data.week}:`;
  const text =
    rootFor.length > 0
      ? `${lead} root for the ${list(rootFor)}. ${pct}`
      : `${lead} no other game this week moves the needle. ${pct}`;

  return {
    title: `Who should ${data.teamNick} fans root for? — Hatewatch`,
    text,
    rootFor,
  };
}
