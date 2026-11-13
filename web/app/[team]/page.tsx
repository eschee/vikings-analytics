import { notFound } from "next/navigation";

import Guide from "@/components/Guide";
import Header from "@/components/Header";
import {
  MissingDatabaseError,
  loadPageData,
  teamAllowlist,
} from "@/lib/data";

/** One page per team.
 *
 *  THE ALLOWLIST. A URL segment is user input, so it is checked against the
 *  32 teams in the database before it reaches any other query, and anything
 *  else gets a real 404 rather than an empty page that looks like an answer.
 *
 *  The check runs HERE, in the page, before loadPageData is called. It used
 *  to live inside loadPageData and throw UnknownTeamError, which the page
 *  caught and turned into notFound() -- except loadPageData is a "use cache"
 *  function, and an error thrown across that boundary arrives as a different
 *  object, so `instanceof` failed and an unknown team returned 500 instead of
 *  404. Validating before the cached call is both correct and the better
 *  ordering: nothing reaches a query until the segment is known to be a team.
 *
 *  loadPageData still checks as well, so the rule holds for any future caller.
 *
 *  generateStaticParams prerenders the 32 valid teams but is NOT the gate:
 *  `dynamicParams = false` would make the router refuse anything else, and
 *  that option is incompatible with cacheComponents, which this app uses.
 */

export async function generateStaticParams() {
  try {
    const teams = await teamAllowlist();
    return teams.map((abbr) => ({ team: abbr.toLowerCase() }));
  } catch {
    // No database at build time: fall back to the one team we know, rather
    // than failing the whole build.
    return [{ team: "min" }];
  }
}

export default async function TeamPage({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;

  // Allowlist first. notFound() renders the 404 page with a 404 status.
  let allowed: string[];
  try {
    allowed = await teamAllowlist();
  } catch {
    allowed = [];
  }
  if (!allowed.includes(team.toUpperCase())) {
    notFound();
  }

  let data;
  try {
    data = await loadPageData(team);
  } catch (error) {
    if (error instanceof MissingDatabaseError) {
      return (
        <main className="px-5 py-10">
          <h1 className="font-display text-2xl font-bold text-brand">
            No data yet
          </h1>
          <p className="mt-3 text-sm text-muted">{error.message}</p>
        </main>
      );
    }
    throw error;
  }

  return (
    <>
      <Header data={data} />
      <Guide data={data} />
    </>
  );
}
