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
