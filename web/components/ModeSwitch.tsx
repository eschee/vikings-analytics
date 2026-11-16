import Link from "next/link";

import type { Mode } from "@/lib/types";

/** The Contend / Tank switch in the banner.
 *
 *  Two links styled as a segmented control, not a toggle button: each mode
 *  has its own address (/min and /min/tank), so the switch is ordinary
 *  navigation -- it works without JavaScript, the back button undoes it, and
 *  either view can be shared. `aria-current` tells screen readers which one
 *  is showing.
 *
 *  It sits on the team's banner colours, so it draws only with the banner's
 *  contrast-checked variables (--team-*), never with fixed colours. */

const OPTIONS: { mode: Mode; label: string; hint: string }[] = [
  { mode: "contend", label: "Contend", hint: "root for the playoffs" },
  { mode: "tank", label: "Tank", hint: "root for the best draft pick" },
];

export default function ModeSwitch({
  team,
  mode,
}: {
  /** Already validated against the 32-team allowlist. */
  team: string;
  mode: Mode;
}) {
  const base = `/${team.toLowerCase()}`;
  return (
    <nav aria-label="Mode">
      <ul className="inline-flex rounded-full border border-(--team-line) p-1 text-sm font-semibold">
        {OPTIONS.map((o) => {
          const active = o.mode === mode;
          return (
            <li key={o.mode}>
              <Link
                href={o.mode === "tank" ? `${base}/tank` : base}
                aria-current={active ? "page" : undefined}
                title={`${o.label}: ${o.hint}`}
                className={`block rounded-full px-4 py-1.5 ${
                  active
                    ? "bg-(--team-fg) text-(--team-bg)"
                    : "text-(--team-muted) hover:text-(--team-fg)"
                }`}
              >
                {o.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
