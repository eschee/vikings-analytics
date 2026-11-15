import { ImageResponse } from "next/og";

import { loadPageData, teamAllowlist } from "@/lib/data";
import { shareSummary } from "@/lib/share";

/** The link-preview card for each team's page.
 *
 *  When a link to /min is pasted into Messages, Slack, Discord or X, those
 *  apps fetch this image and show it as a card. Next.js wires it up from the
 *  file name alone: it serves the image at /min/opengraph-image and adds the
 *  og:image tags to the page.
 *
 *  It says the same thing as the share button's text (lib/share.ts), in the
 *  team's banner colours (already contrast-checked and validated as #RRGGBB
 *  in lib/colors.ts). The URL segment is checked against the 32-team
 *  allowlist before anything else; an unknown team gets a plain house card,
 *  never an error page rendered as an image.
 *
 *  `ImageResponse` ships with Next.js (next/og) -- no extra package. It draws
 *  with a subset of CSS: every box with more than one child must be flex.
 */

export const alt = "Who to root for this week — Hatewatch";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const HOUSE = { bg: "#2b1758", fg: "#ffffff", accent: "#f2b705", muted: "#cfc4e8" };

export default async function Image({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;

  let allowed: string[] = [];
  try {
    allowed = await teamAllowlist();
  } catch {
    allowed = [];
  }
  const result = allowed.includes(team.toUpperCase())
    ? await loadPageData(team)
    : null;

  if (!result || !result.ok) {
    return new ImageResponse(
      (
        <div
          style={{
            width: "100%",
            height: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: HOUSE.bg,
            color: HOUSE.fg,
            fontSize: 72,
            fontWeight: 700,
            letterSpacing: 8,
          }}
        >
          HATEWATCH
        </div>
      ),
      size,
    );
  }

  const data = result.data;
  const t = data.theme;
  const summary = shareSummary(data);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: t.bg,
          color: t.fg,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30 }}>
          <span style={{ fontWeight: 700, letterSpacing: 6 }}>HATEWATCH</span>
          <span style={{ color: t.muted }}>
            {`${data.teamNick} ${data.recordText} · Week ${data.week}`}
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 40, color: t.muted }}>
            {`${data.teamNick} fans, root for`}
          </div>
          <div style={{ display: "flex", fontSize: 76, fontWeight: 700, lineHeight: 1.1, marginTop: 8 }}>
            {summary.rootFor.length > 0
              ? summary.rootFor.join(" · ")
              : "No one this week"}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "baseline", fontSize: 44 }}>
          <span style={{ color: t.accent, fontWeight: 700, fontSize: 64 }}>
            {`${Math.round(data.playoffPct)}%`}
          </span>
          <span style={{ marginLeft: 16 }}>chance to make the playoffs</span>
        </div>
      </div>
    ),
    size,
  );
}
