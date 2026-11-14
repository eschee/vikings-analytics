import type { Metadata } from "next";
import { notFound } from "next/navigation";

import Guide from "@/components/Guide";
import Header from "@/components/Header";
import { directory, loadPageData, teamAllowlist } from "@/lib/data";

/** Look a URL segment up in the 32-team directory. Returns null for anything
 *  that is not a current team, so an unknown segment never reaches a query --
 *  the directory is one fixed query with no input. */
async function lookup(segment: string) {
  const dir = await directory();
  const abbr = segment.toUpperCase();
  return dir.entries.find((t) => t.abbr === abbr) ?? null;
}

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
    title: `${nick} — Hatewatch`,
    description: `Which other NFL results help the ${nick} most, ranked by how much they move their playoff, division and #1 seed odds.`,
  };
}

/* No per-team generateViewport (the phone toolbar colour): reading the URL
   there stops Next.js prerendering the page -- it reports this as
   "blocking-prerender-viewport-runtime". The toolbar keeps the house purple
   from layout.tsx; the banner itself still takes the team's colours. */

/** One page per team.
 *
 *  THE ALLOWLIST. A URL segment is user input, so it is checked against the
 *  32 teams in the database before it reaches any other query, and anything
 *  else gets a real 404 rather than an empty page that looks like an answer.
 *  The check runs here, before loadPageData, so nothing reaches a query until
 *  the segment is known to be a team. loadPageData checks again, so the rule
 *  holds for any future caller.
 *
 *  If the allowlist cannot be read at all, `allowed` is empty and every team
 *  404s. Fail closed: better to serve nothing than to serve a page built from
 *  an unvalidated segment.
 *
 *  `dynamicParams = false` would have had the router reject unknown segments
 *  outright, but it is incompatible with cacheComponents, which this app uses.
 *  So this runtime check is the only gate.
 *
 *  WHY loadPageData RETURNS A RESULT INSTEAD OF THROWING. It is a "use cache"
 *  function, and an error thrown across that boundary arrives as a different
 *  object, so `instanceof` silently fails. That turned an unknown team into a
 *  500 once already. A returned value crosses intact.
 */

export async function generateStaticParams() {
  try {
    const teams = await teamAllowlist();
    return teams.map((abbr) => ({ team: abbr.toLowerCase() }));
  } catch {
    // No database at build time: prerender the one team we know rather than
    // failing the whole build. Unknown segments still hit the runtime check.
    return [{ team: "min" }];
  }
}

function Notice({ title, message }: { title: string; message: string }) {
  return (
    <main className="mx-auto max-w-[600px] px-5 py-10">
      <h1 className="font-display text-2xl font-bold text-brand">{title}</h1>
      <p className="mt-3 text-sm text-muted">{message}</p>
    </main>
  );
}

export default async function TeamPage({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;

  let allowed: string[];
  try {
    allowed = await teamAllowlist();
  } catch {
    allowed = [];
  }
  if (!allowed.includes(team.toUpperCase())) {
    notFound();
  }

  const result = await loadPageData(team);
  if (!result.ok) {
    if (result.failure.reason === "unknown-team") {
      notFound();
    }
    return (
      <Notice
        title={
          result.failure.reason === "no-database"
            ? "Not connected"
            : "No data yet"
        }
        message={result.failure.message}
      />
    );
  }

  return (
    <>
      <Header data={result.data} />
      <Guide data={result.data} />
    </>
  );
}
