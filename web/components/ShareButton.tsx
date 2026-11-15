"use client";

import { useState } from "react";

/** Share this week's guide.
 *
 *  Two paths, tried in order:
 *
 *  1. The Web Share API (navigator.share). Phones, and Safari/Chrome/Edge on
 *     a Mac, open the system share sheet -- Messages, WhatsApp, Mail -- with
 *     the text and link filled in. Nothing to install; the browser does it.
 *  2. Otherwise, copy "text + link" to the clipboard and say so.
 *
 *  If both fail (an old browser, or clipboard access refused), the link is
 *  shown in a read-only field, selected, so it can be copied by hand.
 *
 *  The link is the page's own address at the moment of the click, so it
 *  always points at the team being viewed. The text is built by the caller
 *  from the page's data. Nothing is sent anywhere by this component: the
 *  browser hands the text to whichever app the user picks.
 *
 *  Status messages use role="status", so screen readers announce "Copied"
 *  the same way it appears on screen.
 */

type State = "idle" | "copied" | "manual";

export default function ShareButton({
  title,
  text,
}: {
  title: string;
  text: string;
}) {
  const [state, setState] = useState<State>("idle");
  const [url, setUrl] = useState("");

  async function share() {
    const link = window.location.href;
    setUrl(link);

    if (typeof navigator.share === "function") {
      try {
        await navigator.share({ title, text, url: link });
        return;
      } catch (err) {
        // The user closing the share sheet is not an error worth showing.
        if (err instanceof DOMException && err.name === "AbortError") return;
        // Anything else (e.g. sharing blocked): fall through to copying.
      }
    }

    try {
      await navigator.clipboard.writeText(`${text}\n${link}`);
      setState("copied");
    } catch {
      setState("manual");
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={share}
        className="font-display flex w-full items-center justify-center gap-2 rounded-2xl bg-gold px-5 py-4 text-lg font-bold text-brand"
      >
        <span aria-hidden="true">↑</span>
        Share this week&apos;s guide
      </button>

      <p role="status" className="mt-2 text-center text-sm text-muted">
        {state === "copied" ? "Copied — paste it anywhere." : ""}
        {state === "manual" ? "Copy this link:" : ""}
      </p>

      {state === "manual" ? (
        <input
          readOnly
          value={url}
          aria-label="Link to this page"
          onFocus={(e) => e.currentTarget.select()}
          autoFocus
          className="mt-1 w-full rounded-xl border border-line bg-card px-3 py-2 text-sm text-brand"
        />
      ) : null}
    </div>
  );
}
