"use client";

/** "Back to the guide" that returns to the team you came from.
 *
 *  The how-it-works page is shared by all 32 teams, so a fixed link would
 *  send a Bears fan to the Vikings. If the reader arrived from a page on this
 *  site, the link goes back in history -- to their team, scrolled where they
 *  were. Otherwise (opened directly, or from another site) it is an ordinary
 *  link to the home page.
 *
 *  No URL parameter carries the team, so there is nothing to validate and
 *  nothing anyone can tamper with.
 */

export default function BackLink() {
  function onClick(e: React.MouseEvent<HTMLAnchorElement>) {
    let sameSite = false;
    try {
      sameSite =
        document.referrer !== "" &&
        new URL(document.referrer).origin === window.location.origin;
    } catch {
      sameSite = false;
    }
    if (sameSite && window.history.length > 1) {
      e.preventDefault();
      window.history.back();
    }
  }

  return (
    <a
      href="/"
      onClick={onClick}
      className="inline-block text-sm font-medium text-brand underline underline-offset-4"
    >
      ← Back to the guide
    </a>
  );
}
