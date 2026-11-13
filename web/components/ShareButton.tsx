"use client";

import { useState } from "react";

/** Placeholder. Kept as a real, focusable button that says plainly that it is
 *  not wired up yet, rather than a disabled control or one that silently does
 *  nothing. The message is announced politely so a screen-reader user learns
 *  the same thing a sighted user does. */

export default function ShareButton() {
  const [clicked, setClicked] = useState(false);

  return (
    <div>
      <button
        type="button"
        onClick={() => setClicked(true)}
        className="font-display flex w-full items-center justify-center gap-2 rounded-2xl bg-gold px-5 py-4 text-lg font-bold text-brand"
      >
        <span aria-hidden="true">↑</span>
        Share this week&apos;s guide
      </button>
      <p role="status" className="mt-2 text-center text-sm text-muted">
        {clicked ? "Sharing isn't built yet — coming soon." : ""}
      </p>
    </div>
  );
}
