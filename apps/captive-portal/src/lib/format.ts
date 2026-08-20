/**
 * Human formatting for offer figures.
 *
 * Kept apart from the rendering code so the wording is unit-tested: an offer that
 * says "3600 secondes" instead of "1 heure" is a usability defect on a portal whose
 * whole job is to be understood in a few seconds (§12.1).
 */
import { translate, type Locale } from "./i18n";

const SECONDS_PER_MINUTE = 60;
const SECONDS_PER_HOUR = 3600;
const SECONDS_PER_DAY = 86400;

function plural(locale: Locale, value: number, singularKey: "day" | "hour" | "minute"): string {
  const pluralKey = `${singularKey}s` as const;
  return `${value} ${translate(locale, value > 1 ? pluralKey : singularKey)}`;
}

export function formatPrice(priceXof: number, locale: Locale = "fr"): string {
  if (priceXof === 0) return translate(locale, "free");
  const grouped = priceXof.toLocaleString(locale === "en" ? "en-GB" : "fr-FR").replace(/ | /g, " ");
  return `${grouped} FCFA`;
}

export function formatDuration(seconds: number | null, locale: Locale = "fr"): string | null {
  if (seconds === null || seconds <= 0) return null;

  if (seconds % SECONDS_PER_DAY === 0) {
    return plural(locale, seconds / SECONDS_PER_DAY, "day");
  }
  if (seconds % SECONDS_PER_HOUR === 0) {
    return plural(locale, seconds / SECONDS_PER_HOUR, "hour");
  }
  if (seconds < SECONDS_PER_HOUR) {
    return plural(locale, Math.round(seconds / SECONDS_PER_MINUTE), "minute");
  }

  // Leftover minutes matter to someone buying time: never round them away.
  const hours = Math.floor(seconds / SECONDS_PER_HOUR);
  const minutes = Math.round((seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE);
  return `${hours} h ${minutes} min`;
}

export function formatVolume(bytes: number | null, locale: Locale = "fr"): string | null {
  if (bytes === null || bytes <= 0) return null;

  const gigabytes = bytes / 1_000_000_000;
  if (gigabytes >= 1) {
    const rounded = Math.round(gigabytes * 10) / 10;
    const number = Number.isInteger(rounded)
      ? String(rounded)
      : rounded.toFixed(1).replace(".", locale === "en" ? "." : ",");
    return `${number} ${translate(locale, "gigabyte")}`;
  }

  return `${Math.round(bytes / 1_000_000)} ${translate(locale, "megabyte")}`;
}
