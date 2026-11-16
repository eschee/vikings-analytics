import { shareImage } from "@/lib/shareImage";

/** Tank mode's link-preview card, at /min/tank/opengraph-image. Same
 *  drawing as the contend card (lib/shareImage.tsx), with the draft numbers. */

export const alt = "Who to root for this week, tank mode — WhoToRoot";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image({
  params,
}: {
  params: Promise<{ team: string }>;
}) {
  const { team } = await params;
  return shareImage(team, "tank");
}
