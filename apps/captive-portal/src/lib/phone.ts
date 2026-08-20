/**
 * Normalise a phone number typed on the captive portal to E.164.
 *
 * The API only accepts international format (§8.1). Citizens in Dakar usually
 * type a local mobile (77…); the country code is implied, not demanded.
 */
const E164 = /^\+[1-9]\d{7,14}$/;
const LOCAL_SN_MOBILE = /^7\d{8}$/;

export function toE164(raw: string): string | null {
  const trimmed = raw.trim().replace(/[\s.-]/g, "");
  if (E164.test(trimmed)) {
    return trimmed;
  }

  const digits = trimmed.startsWith("+")
    ? trimmed.slice(1).replace(/\D/g, "")
    : trimmed.replace(/\D/g, "");

  if (digits.startsWith("00")) {
    const international = `+${digits.slice(2)}`;
    return E164.test(international) ? international : null;
  }
  if (digits.startsWith("221") && digits.length >= 12) {
    const international = `+${digits}`;
    return E164.test(international) ? international : null;
  }
  if (LOCAL_SN_MOBILE.test(digits)) {
    return `+221${digits}`;
  }
  return null;
}
