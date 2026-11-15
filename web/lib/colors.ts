/** Team banner colours, chosen so every team's banner stays readable.
 *
 *  The database holds each team's primary and secondary colour. Using them
 *  as-is fails for several teams: white text on the Saints' gold is 1.9:1,
 *  on the Titans' light blue 3.2:1, where readable small text needs 4.5:1
 *  (the WCAG AA guideline). So the text colour is picked per team -- white or
 *  near-black, whichever contrasts more -- and every other colour is derived
 *  from that pair and checked the same way.
 *
 *  SECURITY. These strings end up in inline styles. A colour is only ever
 *  used if it matches #RRGGBB exactly; anything else falls back to the house
 *  purple, so a malformed database value can never inject other CSS.
 */

export interface TeamTheme {
  /** Banner background: the team's primary colour. */
  bg: string;
  /** Main text on the banner: white or near-black. */
  fg: string;
  /** The big headline number: the secondary colour if it is readable on the
   *  banner at large-text size (3:1), otherwise the text colour. */
  accent: string;
  /** Secondary text (record, labels): softer than fg but still >= 4.5:1. */
  muted: string;
  /** Hairlines and the picker button's border: decorative, no text. */
  line: string;
  /** The picker button's fill. */
  soft: string;
}

const HOUSE_PURPLE = "#2b1758";
const WHITE = "#ffffff";
const NEAR_BLACK = "#14101f";

const HEX = /^#[0-9a-fA-F]{6}$/;

export function isHexColour(value: unknown): value is string {
  return typeof value === "string" && HEX.test(value);
}

function rgb(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [
    number,
    number,
    number,
  ];
}

function toHex([r, g, b]: [number, number, number]): string {
  return (
    "#" +
    [r, g, b].map((c) => Math.round(c).toString(16).padStart(2, "0")).join("")
  );
}

/** Relative luminance, per the WCAG definition. */
function luminance(hex: string): number {
  const [r, g, b] = rgb(hex).map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** `amount` of the way from colour a to colour b. */
function mix(a: string, b: string, amount: number): string {
  const [ra, ga, ba] = rgb(a);
  const [rb, gb, bb] = rgb(b);
  return toHex([
    ra + (rb - ra) * amount,
    ga + (gb - ga) * amount,
    ba + (bb - ba) * amount,
  ]);
}

export function teamTheme(
  primary: string | null | undefined,
  secondary: string | null | undefined,
): TeamTheme {
  const bg = isHexColour(primary) ? primary : HOUSE_PURPLE;
  const fg = contrast(bg, WHITE) >= contrast(bg, NEAR_BLACK) ? WHITE : NEAR_BLACK;

  const accent =
    isHexColour(secondary) && contrast(bg, secondary) >= 3 ? secondary : fg;

  // Soften the secondary text toward the background, but only as far as it
  // stays readable; on low-contrast teams it simply stays the full text colour.
  const softened = mix(fg, bg, 0.22);
  const muted = contrast(softened, bg) >= 4.5 ? softened : fg;

  return {
    bg,
    fg,
    accent,
    muted,
    line: mix(bg, fg, 0.35),
    soft: mix(bg, fg, 0.12),
  };
}
