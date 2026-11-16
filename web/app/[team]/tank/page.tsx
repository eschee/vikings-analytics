import type { Metadata } from "next";

import { lookup, renderTeamPage, teamStaticParams } from "../render";

/** Tank mode: which results help a team's DRAFT position. Same page as
 *  contend mode, ranked by the draft goals instead (see ../render.tsx). */

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
    title: `${nick} tank mode — Hatewatch`,
    description: `Tanking? Which NFL results move the ${nick} up the draft order, and their chance at the #1 pick.`,
  };
}

export async function generateStaticParams() {
  return teamStaticParams();
}

export default async function TankPage({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;
  return renderTeamPage(team, "tank");
}
