import { ImageResponse } from "next/og";

import { loadPageData, teamAllowlist } from "./data";
import { pickLabel } from "./format";
import { shareSummary } from "./share";
import type { Mode } from "./types";

/** The link-preview card, shared by /min/opengraph-image and
 *  /min/tank/opengraph-image so both modes draw the same way.
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

export const size = { width: 1200, height: 630 };

const HOUSE = { bg: "#2b1758", fg: "#ffffff", accent: "#f2b705", muted: "#cfc4e8" };

/** Draw the card for one team in one mode. The segment is untrusted input:
 *  it is checked against the allowlist before it reaches any query. */
export async function shareImage(team: string, mode: Mode) {
  let allowed: string[] = [];
  try {
    allowed = await teamAllowlist();
  } catch {
    allowed = [];
  }
  const result = allowed.includes(team.toUpperCase())
    ? await loadPageData(team, mode)
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
            {mode === "tank"
              ? `Tanking ${data.teamNick} fans, root for`
              : `${data.teamNick} fans, root for`}
          </div>
          <div style={{ display: "flex", fontSize: 76, fontWeight: 700, lineHeight: 1.1, marginTop: 8 }}>
            {summary.rootFor.length > 0
              ? summary.rootFor.join(" · ")
              : "No one this week"}
          </div>
        </div>

        {mode === "tank" ? (
          <div style={{ display: "flex", alignItems: "baseline", fontSize: 44 }}>
            <span>Projected pick</span>
            <span style={{ color: t.accent, fontWeight: 700, fontSize: 64, marginLeft: 16 }}>
              {data.avgDraftPick === null ? "—" : pickLabel(data.avgDraftPick)}
            </span>
          </div>
        ) : (
          <div style={{ display: "flex", alignItems: "baseline", fontSize: 44 }}>
            <span style={{ color: t.accent, fontWeight: 700, fontSize: 64 }}>
              {`${Math.round(data.playoffPct)}%`}
            </span>
            <span style={{ marginLeft: 16 }}>chance to make the playoffs</span>
          </div>
        )}
      </div>
    ),
    size,
  );
}
