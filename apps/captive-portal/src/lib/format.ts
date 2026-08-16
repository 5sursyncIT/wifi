/**
 * Human formatting for offer figures, in French.
 *
 * Kept apart from the rendering code so the wording is unit-tested: an offer that
 * says "3600 secondes" instead of "1 heure" is a usability defect on a portal whose
 * whole job is to be understood in a few seconds (§12.1).
 */

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const SECONDS_PER_DAY = 86400;

function plural(value: number, singular: string, plural_: string): string {
  return `${value} ${value > 1 ? plural_ : singular}`;
}

export function formatPrice(priceXof: number): string {
  if (priceXof === 0) return "Gratuit";
  // Narrow no-break space between groups, as French typography expects.
  return `${priceXof.toLocaleString("fr-FR").replace(/ | /g, " ")} FCFA`;
}

export function formatDuration(seconds: number | null): string | null {
  if (seconds === null || seconds <= 0) return null;

  if (seconds % SECONDS_PER_DAY === 0) {
    return plural(seconds / SECONDS_PER_DAY, "jour", "jours");
  }
  if (seconds % SECONDS_PER_HOUR === 0) {
    return plural(seconds / SECONDS_PER_HOUR, "heure", "heures");
  }
  if (seconds < SECONDS_PER_HOUR) {
    return plural(Math.round(seconds / SECONDS_PER_MINUTE), "minute", "minutes");
  }

  // Leftover minutes matter to someone buying time: never round them away.
  const hours = Math.floor(seconds / SECONDS_PER_HOUR);
  const minutes = Math.round((seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  return `${hours} h ${minutes} min`;
}

export function formatVolume(bytes: number | null): string | null {
  if (bytes === null || bytes <= 0) return null;

  const gigabytes = bytes / 1_000_000_000;
  if (gigabytes >= 1) {
    const rounded = Math.round(gigabytes * 10) / 10;
    return `${Number.isInteger(rounded) ? rounded : rounded.toString().replace(".", ",")} Go`;
  }

  return `${Math.round(bytes / 1_000_000)} Mo`;
}
