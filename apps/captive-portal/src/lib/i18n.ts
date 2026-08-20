/**
 * Captive-portal copy (cahier des charges §1 rule 16, ADR-0003).
 *
 * French is the functional reference. Wolof and English are ready from day one;
 * Wolof stays short so the journey remains usable if long copy is missing.
 * Keys are English. No i18n runtime: the Astro bundle budget forbids next-intl.
 */

export const LOCALES = ["fr", "wo", "en"] as const;

export type Locale = (typeof LOCALES)[number];

export const STORAGE_KEY = "dakar-wifi:lang";

const FR = {
  brand: "Dakar WiFi",
  network_name: "Réseau DAKAR-WIFI",
  logo_alt: "Armoiries de la Ville de Dakar",
  loading_offers: "Chargement des offres…",
  footer_dev: "Ville de Dakar — plateforme en cours de développement",
  language: "Langue",
  connect_free: "Se connecter gratuitement",
  buy_offer: "Acheter {name}",
  devices: "{count} appareils",
  voucher_title: "J’ai un coupon",
  voucher_use: "Utiliser le coupon",
  voucher_rejected: "Coupon refusé. Vérifiez le code.",
  identify_first: "Identifiez-vous d’abord depuis une offre affichée.",
  help_title: "Besoin d’aide ?",
  help_placeholder: "Décrivez le problème en quelques mots.",
  help_send: "Envoyer",
  help_opened: "Ticket {number} ouvert. Un agent de la Ville vous répondra.",
  help_rate_limited: "Trop de demandes. Patientez avant d’ouvrir un autre ticket.",
  help_failed: "Envoi impossible. Réessayez dans un instant.",
  ticket_connexion: "Connexion",
  ticket_otp: "Code SMS",
  ticket_paiement: "Paiement",
  ticket_quota: "Quota",
  ticket_qualite: "Qualité du réseau",
  ticket_autre: "Autre",
  demo_title: "Environnement de démonstration",
  demo_body: "Le paiement et le réseau sont simulés. Aucun débit réel n’est effectué.",
  fallback_title: "Point d’accès en cours de configuration",
  fallback_generic: "Ce point d’accès n’est pas prêt.",
  zone_inactive: "Ce point d’accès est momentanément fermé. Réessayez plus tard.",
  no_offer_available: "Aucune offre n’est disponible ici pour l’instant.",
  phone_title: "Votre numéro de téléphone",
  phone_label: "Numéro de téléphone",
  consent: "J’accepte les conditions d’utilisation et la politique de confidentialité.",
  receive_code: "Recevoir un code",
  sending: "Envoi…",
  phone_invalid: "Entrez un numéro sénégalais à 9 chiffres, par exemple 77 123 45 67.",
  consent_required: "Vous devez accepter les conditions pour continuer.",
  otp_rate_limited: "Trop de demandes. Patientez quelques minutes.",
  send_failed: "Envoi impossible. Réessayez dans un instant.",
  code_title: "Code reçu par SMS",
  code_sent: "Un code à six chiffres a été envoyé au {phone}.",
  code_label: "Code à six chiffres",
  validate: "Valider",
  verifying: "Vérification…",
  change_number: "Modifier le numéro",
  invalid_code: "Code incorrect. Vérifiez et réessayez.",
  verify_failed: "Vérification impossible. Réessayez dans un instant.",
  connected: "Vous êtes connecté",
  access_until: "Votre accès est actif jusqu’à {time}.",
  access_active: "Votre accès est actif.",
  continue: "Continuer",
  disconnect_network: "Se déconnecter du réseau",
  session_closed: "Session fermée. Vous pouvez quitter le réseau.",
  disconnect_failed: "Déconnexion impossible. Réessayez dans un instant.",
  download_data: "Télécharger mes données",
  export_failed: "Export impossible. Réessayez dans un instant.",
  delete_account: "Supprimer mon compte",
  confirm_delete: "Confirmer la suppression",
  account_deleted: "Compte supprimé. Vos justificatifs de paiement sont conservés.",
  delete_failed: "Suppression impossible. Réessayez dans un instant.",
  missing_nas_title: "Identifiant de borne absent",
  missing_nas_body:
    "Cette page s’ouvre normalement automatiquement à la connexion au réseau. En développement, ajoutez ?nas_id=demo-nas-001 à l’adresse.",
  unknown_hotspot: "Ce point d’accès n’est pas reconnu. Signalez-le à un agent de la Ville.",
  service_unavailable: "Service momentanément indisponible. Réessayez dans un instant.",
  connection_impossible: "Connexion impossible",
  cooldown: "Vous avez déjà utilisé l’accès gratuit récemment. Choisissez un forfait.",
  outside_hours: "L’accès gratuit n’est pas disponible à cette heure.",
  not_offered_here: "L’accès gratuit n’est pas proposé sur ce point d’accès.",
  no_free_offer: "Aucune offre gratuite sur ce point d’accès.",
  activation_failed: "L’activation a échoué. Réessayez dans un instant.",
  too_many_devices: "Le nombre maximal d’appareils pour l’accès gratuit est atteint.",
  account_unusable: "Ce compte ne peut pas être utilisé. Contactez la Ville.",
  voucher_not_found: "Ce coupon n’est pas reconnu.",
  voucher_expired: "Ce coupon a expiré.",
  voucher_revoked: "Ce coupon a été révoqué.",
  voucher_exhausted: "Ce coupon a déjà été utilisé.",
  voucher_already_used: "Vous avez déjà utilisé ce coupon.",
  voucher_zone_mismatch: "Ce coupon n’est pas valable sur ce point d’accès.",
  voucher_campaign_inactive: "Cette campagne n’est plus active.",
  rate_limited: "Trop de tentatives. Patientez quelques minutes.",
  payment_subtitle: "Paiement de votre forfait",
  validate_on_phone: "Validez sur votre téléphone",
  remaining_time: "Temps restant : {time}",
  finish_payment: "Terminez le paiement",
  finish_payment_body: "Ouvrez ce lien dans votre navigateur complet pour terminer le paiement.",
  open_payment_page: "Ouvrir la page de paiement",
  access_activated: "Votre accès est activé",
  payment_confirmed: "Paiement confirmé. Votre accès est actif.",
  receipt_line: "Commande {number} — {amount} {currency}",
  receipt_unavailable: "Le paiement a réussi, mais le reçu n’est pas disponible pour le moment.",
  payment_failed: "Le paiement n'a pas abouti",
  payment_expired: "Le délai de paiement est écoulé.",
  payment_refused: "Le paiement a été refusé ou la commande a expiré.",
  order_create_failed: "La commande n'a pas pu être créée. Réessayez dans un instant.",
  footer_secure: "Ville de Dakar — paiement sécurisé",
  purchase_title: "Achat — Dakar WiFi",
  free: "Gratuit",
  day: "jour",
  days: "jours",
  hour: "heure",
  hours: "heures",
  minute: "minute",
  minutes: "minutes",
  megabyte: "Mo",
  gigabyte: "Go",
};

const EN: typeof FR = {
  brand: "Dakar WiFi",
  network_name: "DAKAR-WIFI network",
  logo_alt: "Coat of arms of the City of Dakar",
  loading_offers: "Loading offers…",
  footer_dev: "City of Dakar — platform under development",
  language: "Language",
  connect_free: "Connect for free",
  buy_offer: "Buy {name}",
  devices: "{count} devices",
  voucher_title: "I have a voucher",
  voucher_use: "Use voucher",
  voucher_rejected: "Voucher refused. Check the code.",
  identify_first: "Sign in first from an offer on this page.",
  help_title: "Need help?",
  help_placeholder: "Describe the problem in a few words.",
  help_send: "Send",
  help_opened: "Ticket {number} opened. A City agent will get back to you.",
  help_rate_limited: "Too many requests. Wait before opening another ticket.",
  help_failed: "Could not send. Try again in a moment.",
  ticket_connexion: "Connection",
  ticket_otp: "SMS code",
  ticket_paiement: "Payment",
  ticket_quota: "Quota",
  ticket_qualite: "Network quality",
  ticket_autre: "Other",
  demo_title: "Demonstration environment",
  demo_body: "Payment and network are simulated. No real charge is made.",
  fallback_title: "Access point being configured",
  fallback_generic: "This access point is not ready.",
  zone_inactive: "This access point is temporarily closed. Try again later.",
  no_offer_available: "No offer is available here right now.",
  phone_title: "Your phone number",
  phone_label: "Phone number",
  consent: "I accept the terms of use and the privacy policy.",
  receive_code: "Receive a code",
  sending: "Sending…",
  phone_invalid: "Enter a Senegalese 9-digit number, for example 77 123 45 67.",
  consent_required: "You must accept the terms to continue.",
  otp_rate_limited: "Too many requests. Wait a few minutes.",
  send_failed: "Could not send. Try again in a moment.",
  code_title: "Code received by SMS",
  code_sent: "A six-digit code was sent to {phone}.",
  code_label: "Six-digit code",
  validate: "Confirm",
  verifying: "Checking…",
  change_number: "Change number",
  invalid_code: "Incorrect code. Check and try again.",
  verify_failed: "Could not verify. Try again in a moment.",
  connected: "You are online",
  access_until: "Your access is active until {time}.",
  access_active: "Your access is active.",
  continue: "Continue",
  disconnect_network: "Disconnect from the network",
  session_closed: "Session closed. You can leave the network.",
  disconnect_failed: "Could not disconnect. Try again in a moment.",
  download_data: "Download my data",
  export_failed: "Could not export. Try again in a moment.",
  delete_account: "Delete my account",
  confirm_delete: "Confirm deletion",
  account_deleted: "Account deleted. Your payment records are kept.",
  delete_failed: "Could not delete. Try again in a moment.",
  missing_nas_title: "Access-point identifier missing",
  missing_nas_body:
    "This page normally opens automatically when you join the network. In development, add ?nas_id=demo-nas-001 to the address.",
  unknown_hotspot: "This access point is not recognised. Tell a City agent.",
  service_unavailable: "Service temporarily unavailable. Try again in a moment.",
  connection_impossible: "Connection failed",
  cooldown: "You already used free access recently. Choose a paid plan.",
  outside_hours: "Free access is not available at this time.",
  not_offered_here: "Free access is not offered on this access point.",
  no_free_offer: "No free offer on this access point.",
  activation_failed: "Activation failed. Try again in a moment.",
  too_many_devices: "The maximum number of devices for free access is reached.",
  account_unusable: "This account cannot be used. Contact the City.",
  voucher_not_found: "This voucher is not recognised.",
  voucher_expired: "This voucher has expired.",
  voucher_revoked: "This voucher has been revoked.",
  voucher_exhausted: "This voucher has already been used.",
  voucher_already_used: "You have already used this voucher.",
  voucher_zone_mismatch: "This voucher is not valid on this access point.",
  voucher_campaign_inactive: "This campaign is no longer active.",
  rate_limited: "Too many attempts. Wait a few minutes.",
  payment_subtitle: "Pay for your plan",
  validate_on_phone: "Confirm on your phone",
  remaining_time: "Time left: {time}",
  finish_payment: "Finish payment",
  finish_payment_body: "Open this link in a full browser to finish payment.",
  open_payment_page: "Open the payment page",
  access_activated: "Your access is activated",
  payment_confirmed: "Payment confirmed. Your access is active.",
  receipt_line: "Order {number} — {amount} {currency}",
  receipt_unavailable: "Payment succeeded, but the receipt is not available yet.",
  payment_failed: "Payment did not go through",
  payment_expired: "The payment deadline has passed.",
  payment_refused: "Payment was refused or the order expired.",
  order_create_failed: "The order could not be created. Try again in a moment.",
  footer_secure: "City of Dakar — secure payment",
  purchase_title: "Purchase — Dakar WiFi",
  free: "Free",
  day: "day",
  days: "days",
  hour: "hour",
  hours: "hours",
  minute: "minute",
  minutes: "minutes",
  megabyte: "MB",
  gigabyte: "GB",
};

const WO: Partial<typeof FR> = {
  brand: "Dakar WiFi",
  network_name: "Reso DAKAR-WIFI",
  logo_alt: "Armoiries yu Ville Dakar",
  loading_offers: "Offers yi ngi ñëw…",
  footer_dev: "Ville Dakar — plateforme bi dafa nekk ci liggéey",
  language: "Làkk",
  connect_free: "Jàpp ci neen",
  buy_offer: "Jënd {name}",
  devices: "{count} apparayil",
  voucher_title: "Am naa coupon",
  voucher_use: "Jëfandikoo coupon bi",
  voucher_rejected: "Coupon bi bañ na. Seetel kode bi.",
  identify_first: "Jàppal ci offer bu fi nekk ba noppi.",
  help_title: "Soxla nga ndimbal?",
  help_placeholder: "Waxal jafe-jafe bi ci ay baat yu néew.",
  help_send: "Yónnee",
  help_opened: "Ticket {number} ubbi nañu ko. Agent bu Ville bi dina la tontu.",
  help_rate_limited: "Too na. Fàwwal bala ngay ubbi ticket bu bees.",
  help_failed: "Yónnee mënul. Jéemaatal ci kanam.",
  ticket_connexion: "Jàpp",
  ticket_otp: "Kode SMS",
  ticket_paiement: "Fay",
  ticket_quota: "Quota",
  ticket_qualite: "Reso bi",
  ticket_autre: "Yeneen",
  demo_title: "Demo",
  demo_body: "Fay ak reso dañu leen di natt. Amul xaalis bu dëgg.",
  fallback_title: "Borne bi dafa ñëw",
  fallback_generic: "Borne bi généewul.",
  zone_inactive: "Borne bi tëj nañu ko. Jéemaatal ci kanam.",
  no_offer_available: "Amul offer fi léegi.",
  phone_title: "Sa numéro telefon",
  phone_label: "Numéro telefon",
  consent: "Nangu naa liggéey yi ak sutura si.",
  receive_code: "Jël kode",
  sending: "Yónnee…",
  phone_invalid: "Bindal numéro Senegal bu 9 chiffre, misaal 77 123 45 67.",
  consent_required: "War nga nangu liggéey yi ngir kontine.",
  otp_rate_limited: "Too na. Fàwwal ay minuti.",
  send_failed: "Yónnee mënul. Jéemaatal ci kanam.",
  code_title: "Kode SMS",
  code_sent: "Kode bu 6 chiffre yónnee nañu ko ci {phone}.",
  code_label: "Kode bu 6 chiffre",
  validate: "Dëggal",
  verifying: "Seet…",
  change_number: "Soppi numéro bi",
  invalid_code: "Kode bi baaxul. Seetal te jéemaatal.",
  verify_failed: "Seet mënul. Jéemaatal ci kanam.",
  connected: "Jàpp nga",
  access_until: "Sa jàpp dëgg na ba {time}.",
  access_active: "Sa jàpp dëgg na.",
  continue: "Kontine",
  disconnect_network: "Teggil ci reso bi",
  session_closed: "Session tëj na. Mën nga génn.",
  disconnect_failed: "Teggil mënul. Jéemaatal ci kanam.",
  download_data: "Wàcce sama ay data",
  export_failed: "Wàcce mënul. Jéemaatal ci kanam.",
  delete_account: "Dindi sama compte",
  confirm_delete: "Dëggal dindi gi",
  account_deleted: "Compte dindu na. Reçu yi des nañu.",
  delete_failed: "Dindi mënul. Jéemaatal ci kanam.",
  missing_nas_title: "ID borne bi amul",
  missing_nas_body:
    "Xët wi dafa wara ubbi boppam bu nga jàpp ci reso bi. Ci développement, yokk ?nas_id=demo-nas-001.",
  unknown_hotspot: "Borne bi xaméewul. Waxal agent bu Ville bi.",
  service_unavailable: "Service bi génneewul. Jéemaatal ci kanam.",
  connection_impossible: "Jàpp mënul",
  cooldown: "Jëfandikoo nga jàpp bu neen léegi. Tànnal forfait.",
  outside_hours: "Jàpp bu neen amul ci waxtu wii.",
  not_offered_here: "Jàpp bu neen amul ci borne bii.",
  no_free_offer: "Amul offer bu neen ci borne bii.",
  activation_failed: "Jàpp bi antuwul. Jéemaatal ci kanam.",
  too_many_devices: "Apparayil yu bari nañu ci jàpp bu neen.",
  account_unusable: "Compte bii mënul jëfandikoo. Wooyal Ville bi.",
  voucher_not_found: "Coupon bii xaméewul.",
  voucher_expired: "Coupon bi jeex na.",
  voucher_revoked: "Coupon bi dëddu nañu ko.",
  voucher_exhausted: "Coupon bi jëfandikoo nañu ko ba noppi.",
  voucher_already_used: "Jëfandikoo nga coupon bii ba noppi.",
  voucher_zone_mismatch: "Coupon bii doxul ci borne bii.",
  voucher_campaign_inactive: "Campagne bii génneewul.",
  rate_limited: "Jéem yu bari. Fàwwal ay minuti.",
  payment_subtitle: "Fay sa forfait",
  validate_on_phone: "Dëggal ci sa telefon",
  remaining_time: "Waxtu bi des : {time}",
  finish_payment: "Jeexal fay gi",
  finish_payment_body: "Ubbi link bii ci navigateur bu mat ngir jeexal fay gi.",
  open_payment_page: "Ubbi xët u fay",
  access_activated: "Sa jàpp dëgg na",
  payment_confirmed: "Fay dëgg na. Sa jàpp dëgg na.",
  receipt_line: "Commande {number} — {amount} {currency}",
  receipt_unavailable: "Fay antu na, waaye reçu bi génneewul.",
  payment_failed: "Fay gi antuwul",
  payment_expired: "Waxtu u fay jeex na.",
  payment_refused: "Fay gi bañ na walla commande bi jeex na.",
  order_create_failed: "Commande bi mënul sosu. Jéemaatal ci kanam.",
  footer_secure: "Ville Dakar — fay bu wóor",
  purchase_title: "Jënd — Dakar WiFi",
  free: "Ci neen",
  day: "bés",
  days: "bés",
  hour: "waxtu",
  hours: "waxtu",
  minute: "miniti",
  minutes: "miniti",
  megabyte: "Mo",
  gigabyte: "Go",
};

const TABLES: Record<Locale, Partial<typeof FR>> = { fr: FR, en: EN, wo: WO };

export type MessageKey = keyof typeof FR;

function isLocale(value: string | null | undefined): value is Locale {
  if (!value) return false;
  return (LOCALES as readonly string[]).includes(value.toLowerCase());
}

export function resolveLocale(input: {
  search?: string | null;
  stored?: string | null;
  languages?: readonly string[];
}): Locale {
  if (isLocale(input.search)) return input.search.toLowerCase() as Locale;
  if (isLocale(input.stored)) return input.stored.toLowerCase() as Locale;
  for (const language of input.languages ?? []) {
    const prefix = language.slice(0, 2).toLowerCase();
    if (isLocale(prefix)) return prefix;
  }
  return "fr";
}

function interpolate(template: string, vars?: Record<string, string | number>): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(vars[name] ?? `{${name}}`));
}

export function translate(
  locale: Locale,
  key: MessageKey,
  vars?: Record<string, string | number>,
): string {
  const template = TABLES[locale][key] ?? FR[key] ?? key;
  return interpolate(template, vars);
}

export function persistLocale(locale: Locale): void {
  if (typeof localStorage === "undefined") return;
  localStorage.setItem(STORAGE_KEY, locale);
}

export function localeFromWindow(win: {
  location: { search: string };
  localStorage: { getItem(key: string): string | null };
  navigator: { languages?: readonly string[]; language?: string };
}): Locale {
  const search = new URLSearchParams(win.location.search).get("lang");
  const languages =
    win.navigator.languages ?? (win.navigator.language ? [win.navigator.language] : []);
  return resolveLocale({
    search,
    stored: win.localStorage.getItem(STORAGE_KEY),
    languages,
  });
}

export function applyTranslations(root: ParentNode, locale: Locale): void {
  if (typeof document !== "undefined") {
    document.documentElement.lang = locale;
  }
  for (const node of root.querySelectorAll<HTMLElement>("[data-i18n]")) {
    const key = node.dataset.i18n as MessageKey | undefined;
    if (!key) continue;
    node.textContent = translate(locale, key);
  }
  for (const node of root.querySelectorAll<HTMLElement>("[data-i18n-aria]")) {
    const key = node.dataset.i18nAria as MessageKey | undefined;
    if (!key) continue;
    const text = translate(locale, key);
    if (node instanceof HTMLImageElement) {
      node.alt = text;
    } else {
      node.setAttribute("aria-label", text);
    }
  }
  for (const node of root.querySelectorAll<HTMLElement>("[data-i18n-placeholder]")) {
    const key = node.dataset.i18nPlaceholder as MessageKey | undefined;
    if (!key) continue;
    node.setAttribute("placeholder", translate(locale, key));
  }
  const titled = root.querySelector<HTMLElement>("[data-i18n-title]");
  if (titled?.dataset.i18nTitle) {
    document.title = translate(locale, titled.dataset.i18nTitle as MessageKey);
  }
}

export function languageHref(search: string, locale: Locale): string {
  const params = new URLSearchParams(search);
  params.set("lang", locale);
  const query = params.toString();
  return query ? `?${query}` : `?lang=${locale}`;
}
