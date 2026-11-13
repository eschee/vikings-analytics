import Link from "next/link";

/** Stub, as specified. Enough to explain the vocabulary on the main page
 *  without pretending to document the model yet. */

export default function HowThisWorks() {
  return (
    <main className="px-5 py-8">
      <h1 className="font-display text-3xl font-bold text-brand">
        How this works
      </h1>

      <div className="mt-5 space-y-5 text-sm leading-relaxed text-muted">
        <p>
          Every remaining game this season is played out twenty thousand times.
          Games with a betting line use that line; the rest are priced from team
          ratings fitted to the lines that do exist. Playoff seeding follows the
          real NFL tiebreakers.
        </p>
        <p>
          To work out what a single game is worth, the simulated seasons are
          split by who won it and the two halves are compared. The gap is the
          impact, in percentage points.
        </p>
        <div>
          <h2 className="font-display text-base font-bold text-brand">
            The tiers
          </h2>
          <ul className="mt-2 space-y-1">
            <li>Must win — moves your odds by 10 points or more.</li>
            <li>Root hard — 2 points or more.</li>
            <li>
              A little — smaller, but still bigger than the simulation&apos;s own
              margin of error.
            </li>
            <li>
              Doesn&apos;t matter — too small to tell apart from noise.
            </li>
          </ul>
        </div>
        <p className="text-xs">
          This page is a stub. A fuller write-up of the model is still to come.
        </p>
      </div>

      <Link
        href="/"
        className="mt-8 inline-block text-sm font-medium text-brand underline underline-offset-4"
      >
        Back to the guide
      </Link>
    </main>
  );
}
