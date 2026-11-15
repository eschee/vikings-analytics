import type { Metadata } from "next";

import BackLink from "@/components/BackLink";
import { GOAL_LABELS, OVERALL_WEIGHTS, RANKABLE_GOALS } from "@/lib/types";

/** How the numbers are made, and how far to trust them.
 *
 *  Written for a fan, not a statistician, but every claim here is checked
 *  against the code or a measurement:
 *    - simulation count, pricing and ratings: hatewatch/run.py,
 *      analysis/simulate.py (SEASON_* settings), analysis/win_probability.py
 *    - Root score weights: OVERALL_WEIGHTS in lib/types.ts (imported below,
 *      so this page cannot drift from the code)
 *    - tier cutoffs: hatewatch/config.py
 *    - the accuracy table: analysis/season_backtest.py, model v5, Nov 2026
 *  If any of those change, change this page in the same pull request.
 */

export const metadata: Metadata = {
  title: "How this works — Hatewatch",
  description:
    "Where Hatewatch's playoff odds come from, what the Root score means, and how accurate the model has been.",
};

const WEIGHTS_TEXT = RANKABLE_GOALS.map(
  (g) => `${GOAL_LABELS[g].toLowerCase()} ${Math.round(OVERALL_WEIGHTS[g] * 100)}%`,
).join(", ");

/** Model v5 replayed on 2023-2025 (weeks 6, 10, 14): playoff forecasts
 *  grouped by what we said, against what happened. */
const PLAYOFF_CALIBRATION = [
  { said: "about 12%", happened: "5%", teams: 40 },
  { said: "about 29%", happened: "35%", teams: 52 },
  { said: "about 49%", happened: "48%", teams: 40 },
  { said: "about 69%", happened: "72%", teams: 46 },
  { said: "about 87%", happened: "86%", teams: 36 },
  { said: "about 99%", happened: "100%", teams: 23 },
];

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="font-display text-xl font-bold text-brand">{title}</h2>
      {children}
    </section>
  );
}

export default function HowThisWorks() {
  return (
    <main className="mx-auto max-w-[600px] px-5 py-8">
      <BackLink />

      <h1 className="font-display mt-4 text-3xl font-bold text-brand">
        How this works
      </h1>
      <p className="mt-3 text-base leading-relaxed text-muted">
        Hatewatch tells you which other NFL games to care about this week, and
        which way to root. Here is where the numbers come from, and how far to
        trust them.
      </p>

      <div className="mt-8 space-y-10 text-sm leading-relaxed text-muted">
        <Section title="Where the odds come from">
          <ol className="list-decimal space-y-3 pl-5">
            <li>
              <span className="font-semibold text-brand">
                Every remaining game gets a win chance.
              </span>{" "}
              For this week and next, that is the betting market&apos;s
              moneyline, with the sportsbook&apos;s margin taken out. Further
              ahead there are no lines yet, so we predict a point spread from
              team ratings — each team&apos;s strength as implied by this
              season&apos;s betting lines, weighted toward the last couple of
              weeks.
            </li>
            <li>
              <span className="font-semibold text-brand">
                The rest of the season is played out 100,000 times.
              </span>{" "}
              Each simulated season also gets its own &ldquo;we might be wrong
              about this team&rdquo; adjustment for every team, held for the
              whole season, so a team we underrate keeps beating our
              expectations — just like in real life.
            </li>
            <li>
              <span className="font-semibold text-brand">
                Each simulated season is seeded with the real NFL tiebreakers.
              </span>{" "}
              That code reproduces every real playoff bracket from 2022 to
              2025.
            </li>
            <li>
              <span className="font-semibold text-brand">We count.</span> If a
              team makes the playoffs in 74,000 of the 100,000 seasons, that is
              a 74% chance. Division and #1 seed odds work the same way.
            </li>
          </ol>
        </Section>

        <Section title="What makes a game matter">
          <p>
            To value one game, we split the 100,000 seasons by who won it and
            compare the two halves. If your playoff chance is 76% in the
            seasons where the Cardinals won and 73% where the Rams won, that
            game is worth about 3 points to you, and you should root for the
            Cardinals.
          </p>
          <p>
            <span className="font-semibold text-brand">The Root score</span>{" "}
            folds your three goals into one number, weighted {WEIGHTS_TEXT}.
            Making the playoffs comes first; the division adds a home game; the
            #1 seed adds a bye. Swings too small to tell apart from simulation
            noise count as zero, and when the goals want opposite teams they
            partly cancel. The weights are our judgement, not a law — pick a
            single goal from &ldquo;Ranking by&rdquo; to see that race alone.
          </p>
          <div>
            <p className="font-semibold text-brand">
              When ranking by a single goal:
            </p>
            <ul className="mt-1 space-y-1">
              <li>Must win — moves that goal by 10 points or more.</li>
              <li>Root hard — 2 points or more.</li>
              <li>A little — smaller, but bigger than simulation noise.</li>
              <li>Doesn&apos;t matter — too small to tell apart from noise.</li>
            </ul>
          </div>
        </Section>

        <Section title="How accurate is it?">
          <p>
            We replayed the 2023, 2024 and 2025 seasons from weeks 6, 10 and
            14, giving the model only what it would have known at the time,
            and compared its playoff odds with what actually happened (288
            forecasts):
          </p>
          <table className="w-full text-left">
            <caption className="sr-only">
              Playoff odds we gave, against how often those teams made it
            </caption>
            <thead>
              <tr className="border-b border-line text-xs text-muted">
                <th scope="col" className="py-1.5 font-medium">We said</th>
                <th scope="col" className="py-1.5 text-right font-medium">Made the playoffs</th>
                <th scope="col" className="py-1.5 text-right font-medium">Teams</th>
              </tr>
            </thead>
            <tbody>
              {PLAYOFF_CALIBRATION.map((r) => (
                <tr key={r.said}>
                  <td className="py-1.5">{r.said}</td>
                  <td className="py-1.5 text-right font-semibold text-brand tabular-nums">
                    {r.happened}
                  </td>
                  <td className="py-1.5 text-right tabular-nums">{r.teams}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            So the playoff odds are close to honest. Division odds are less
            so: teams we gave around 70% to win their division won it about
            half the time. Treat a strong division favourite as a favourite,
            not a lock.
          </p>
          <p>
            <span className="font-semibold text-brand">
              Betting markets are better.
            </span>{" "}
            When we compared in November 2026, most teams were within about 5
            points of the season-long betting markets, but a few differed by 10
            or more — and on average the market is the better forecaster. We use the market&apos;s own lines
            for the next two weeks; it is the weeks after that where we can be
            off.
          </p>
        </Section>

        <Section title="What it can't know">
          <ul className="list-disc space-y-2 pl-5">
            <li>
              <span className="font-semibold text-brand">Injuries</span> reach
              the model only through the betting lines. A quarterback hurt on
              Wednesday shows up once the line moves and the next update runs;
              for games several weeks away, it shows up gradually.
            </li>
            <li>
              <span className="font-semibold text-brand">Timing.</span> The
              numbers update Monday, Tuesday and Friday mornings (US time), and
              sometimes run hours late. The &ldquo;Updated&rdquo; stamp at the
              top shows when.
            </li>
            <li>
              <span className="font-semibold text-brand">
                Far-off games are fuzzier.
              </span>{" "}
              How much a game three or more weeks away matters is estimated a
              little high, because the model partly reads a win as a sign the
              team is better than it thought.
            </li>
            <li>
              <span className="font-semibold text-brand">Ties.</span> Simulated
              games never end tied; real ties already played count as half a
              win.
            </li>
          </ul>
          <p>
            A 70% chance means the other thing happens three times in ten.
            These are honest odds, not predictions.
          </p>
        </Section>
      </div>

      <div className="mt-10">
        <BackLink />
      </div>
    </main>
  );
}
