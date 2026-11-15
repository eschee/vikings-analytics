"use client";

import { useEffect, useRef, useState } from "react";

/** Share this week's guide.
 *
 *  WHICH PATH, AND WHY
 *
 *  Phones and tablets (a touch screen: `pointer: coarse`) get the system
 *  share sheet via the Web Share API -- Messages, WhatsApp, Mail -- which is
 *  what people expect there.
 *
 *  Laptops and desktops copy "message + link" to the clipboard instead, and
 *  the button itself turns into "✓ Link copied". Desktop browsers do expose
 *  navigator.share, but on a Mac Chrome's share menu can open out of sight or
 *  not at all, and the promise then never settles: the click looked like it
 *  did nothing. (Found by sending a real mouse click in a test browser.)
 *  Copying always gives visible feedback.
 *
 *  If copying is refused, the link appears in a selected, read-only field to
 *  copy by hand.
 *
 *  The link is the page's own address at the moment of the click. Nothing is
 *  sent anywhere by this component: the browser hands the text to whichever
 *  app the user picks, or to their own clipboard.
 */

type State = "idle" | "copied" | "manual";

/** How long "✓ Link copied" stays before the button resets. */
const COPIED_MS = 3000;

export default function ShareButton({
  title,
  text,
}: {
  title: string;
  text: string;
}) {
  const [state, setState] = useState<State>("idle");
  const [url, setUrl] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  function showCopied() {
    setState("copied");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), COPIED_MS);
  }

  async function share() {
    const link = window.location.href;
    setUrl(link);

    const touch = window.matchMedia("(pointer: coarse)").matches;
    if (touch && typeof navigator.share === "function") {
      try {
        await navigator.share({ title, text, url: link });
        return;
      } catch (err) {
        // Closing the share sheet is not an error worth showing.
        if (err instanceof DOMException && err.name === "AbortError") return;
        // Anything else (sharing blocked): fall through to copying.
      }
    }

    try {
      await navigator.clipboard.writeText(`${text}\n${link}`);
      showCopied();
    } catch {
      setState("manual");
    }
  }

  const copied = state === "copied";

  return (
    <div>
      <button
        type="button"
        onClick={share}
        className="font-display flex w-full items-center justify-center gap-2 rounded-2xl bg-gold px-5 py-4 text-lg font-bold text-brand"
      >
        <span aria-hidden="true">{copied ? "✓" : "↑"}</span>
        {copied ? "Link copied" : "Share this week’s guide"}
      </button>

      {/* Announced to screen readers; on screen it adds a hint under the
          button, so the change is visible even without reading the label. */}
      <p role="status" className="mt-2 text-center text-sm text-muted">
        {copied ? "Paste it into a text, chat or post." : ""}
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
