import { shareImage } from "@/lib/shareImage";

/** The link-preview card for each team's page.
 *
 *  When a link to /min is pasted into Messages, Slack, Discord or X, those
 *  apps fetch this image and show it as a card. Next.js wires it up from the
 *  file name alone: it serves the image at /min/opengraph-image and adds the
 *  og:image tags to the page. The drawing lives in lib/shareImage.tsx, shared
 *  with tank mode's card.
 */

export const alt = "Who to root for this week — WhoToRoot";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;
  return shareImage(team, "contend");
}
