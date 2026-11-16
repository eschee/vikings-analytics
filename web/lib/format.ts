/** Small display helpers. All return plain strings. */

export function pct(value: number, digits = 0): string {
  return `${value.toFixed(digits)}%`;
}

/** Impact is already in percentage points (or draft picks). One decimal reads
 *  honestly without implying more precision than 20,000 simulations support. */
export function points(value: number): string {
  return `${value.toFixed(1)} pts`;
}

export function signedPoints(value: number): string {
  return `+${value.toFixed(1)}`;
}

/** "Mon 9:00 AM CT" from an ISO timestamp, formatted on the server so the
 *  string never shifts with the reader's own timezone. */
export function updatedLabel(iso: string): string {
  const d = new Date(iso);
  const date = new Intl.DateTimeFormat("en-US", {
    weekday: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone: "America/Chicago",
  }).format(d);
  return `${date} CT`;
}

/** A chance for a headline: whole percent, but "<1%" rather than a
 *  misleading "0%" when it is small yet possible. */
export function chance(value: number): string {
  if (value > 0 && value < 1) return "<1%";
  return `${Math.round(value)}%`;
}

/** An average pick, e.g. "#12". Whole picks in the headline: the decimal
 *  is noise to a fan reading "where will we pick?". */
export function pickLabel(avg: number): string {
  return `#${Math.round(avg)}`;
}
