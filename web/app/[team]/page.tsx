import type { Metadata } from "next";

import { lookup, renderTeamPage, teamStaticParams } from "./render";

/** One page per team, in contend mode: rooting for the playoffs. Tank mode
 *  is the sibling route, /[team]/tank. The shared logic -- including the
 *  allowlist check -- is in ./render.tsx. */

/** Each team's page gets its own browser-tab title and link-preview text. */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ team: string }>;
}): Promise<Metadata> {
  const { team } = await params;
  const found = await lookup(team).catch(() => null);
  if (!found) return {};
  const nick = found.nick;
  return {
    title: `${nick} — WhoToRoot`,
    description: `Which other NFL results help the ${nick} most, ranked by how much they move their playoff, division and #1 seed odds.`,
  };
}

/* No per-team generateViewport (the phone toolbar colour): reading the URL
   there stops Next.js prerendering the page -- it reports this as
   "blocking-prerender-viewport-runtime". The toolbar keeps the house purple
   from layout.tsx; the banner itself still takes the team's colours. */

export async function generateStaticParams() {
  return teamStaticParams();
}

export default async function TeamPage({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;
  return renderTeamPage(team, "contend");
}
