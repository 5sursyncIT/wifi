/**
 * Client logic of the captive portal.
 *
 * Three screens at most between arriving and being online (§12.1): offers, code,
 * confirmation. The zone is whatever the API resolves from the gateway's network
 * identifier — this code never decides which offers to show, and never trusts a
 * zone, a price or an offer coming from the URL (§8.2).
 */
import {
  ApiError,
  createApiClient,
  type ApiClient,
  type PlanOffer,
  type PortalContext,
} from "@dakar-wifi/api-client";

import { formatDuration, formatPrice, formatVolume } from "./format";

const FALLBACK_MESSAGES: Record<string, string> = {
  zone_inactive: "Ce point d’accès est momentanément fermé. Réessayez plus tard.",
  no_offer_available: "Aucune offre n’est disponible ici pour l’instant.",
};

const REFUSAL_MESSAGES: Record<string, string> = {
  cooldown: "Vous avez déjà utilisé l’accès gratuit récemment. Choisissez un forfait.",
  outside_hours: "L’accès gratuit n’est pas disponible à cette heure.",
  not_offered_here: "L’accès gratuit n’est pas proposé sur ce point d’accès.",
  no_free_offer: "Aucune offre gratuite sur ce point d’accès.",
  activation_failed: "L’activation a échoué. Réessayez dans un instant.",
  account_unusable: "Ce compte ne peut pas être utilisé. Contactez la Ville.",
};

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className: string,
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function notice(tone: "info" | "error" | "success", title: string, message: string): HTMLElement {
  const palette = {
    error: "border-red-600 bg-red-50 text-red-900",
    success: "border-[var(--color-brand)] bg-[color-mix(in_srgb,var(--color-brand)_8%,white)]",
    info: "border-amber-500 bg-amber-50 text-amber-900",
  }[tone];
  const section = element("section", `rounded-lg border-2 p-4 ${palette}`);
  section.setAttribute("role", "status");
  section.append(element("h2", "font-bold", title), element("p", "mt-1 text-sm", message));
  return section;
}

function primaryButton(label: string): HTMLButtonElement {
  // Large tap target and strong contrast: this is used outdoors, one-handed (§12.1).
  const button = element(
    "button",
    "w-full rounded-lg bg-[var(--color-brand)] px-4 py-3 text-base font-bold text-white disabled:opacity-50",
    label,
  );
  button.type = "button";
  return button;
}

function offerCard(offer: PlanOffer, onChoose: (offer: PlanOffer) => void): HTMLElement {
  const card = element("li", "rounded-lg border border-black/15 p-4");

  const header = element("div", "flex items-baseline justify-between gap-3");
  header.append(
    element("h3", "text-lg font-bold", offer.name),
    element(
      "p",
      "shrink-0 text-lg font-bold text-[var(--color-brand)]",
      formatPrice(offer.price_xof),
    ),
  );
  card.append(header);

  if (offer.description) {
    card.append(element("p", "mt-1 text-sm text-[var(--color-muted)]", offer.description));
  }

  // Price, duration, volume and speed must all be visible before validating (§12.1).
  const facts = [
    formatDuration(offer.connection_seconds),
    formatVolume(offer.quota_total_bytes),
    offer.bandwidth_down_kbps ? `${Math.round(offer.bandwidth_down_kbps / 1024)} Mb/s` : null,
    offer.max_simultaneous_sessions > 1 ? `${offer.max_simultaneous_sessions} appareils` : null,
  ].filter((fact): fact is string => fact !== null);

  if (facts.length > 0) {
    const list = element("ul", "mt-3 flex flex-wrap gap-2");
    for (const fact of facts) {
      list.append(element("li", "rounded bg-black/5 px-2 py-1 text-sm", fact));
    }
    card.append(list);
  }

  const action = primaryButton(offer.type === "free" ? "Se connecter gratuitement" : "Choisir");
  action.classList.add("mt-4");
  if (offer.type === "free") {
    action.addEventListener("click", () => onChoose(offer));
  } else {
    action.disabled = true;
    card.append(action);
    card.append(
      element(
        "p",
        "mt-2 text-center text-xs text-[var(--color-muted)]",
        "Paiement disponible en phase 4",
      ),
    );
    return card;
  }
  card.append(action);
  return card;
}

interface Session {
  target: HTMLElement;
  client: ApiClient;
  nasId: string;
  context: PortalContext;
  phone: string;
}

function renderOffers(session: Session): void {
  const fragment = document.createDocumentFragment();
  const { context } = session;

  const heading = element("section", "");
  heading.append(element("h2", "text-lg font-bold", context.zone.label));
  heading.append(
    element(
      "p",
      "text-sm text-[var(--color-muted)]",
      `${context.site.name} — ${context.site.organization}`,
    ),
  );
  fragment.append(heading);

  if (context.zone.welcome_message) {
    fragment.append(element("p", "text-base", context.zone.welcome_message));
  }

  if (context.fallback.active) {
    fragment.append(
      notice(
        "info",
        "Point d’accès en cours de configuration",
        FALLBACK_MESSAGES[context.fallback.reason] ?? "Ce point d’accès n’est pas prêt.",
      ),
    );
    session.target.replaceChildren(fragment);
    return;
  }

  const list = element("ul", "flex flex-col gap-3");
  for (const offer of context.plans) {
    list.append(offerCard(offer, () => renderIdentification(session)));
  }
  fragment.append(list);
  session.target.replaceChildren(fragment);
}

function renderIdentification(session: Session): void {
  const form = element("form", "flex flex-col gap-4");
  form.append(element("h2", "text-lg font-bold", "Votre numéro de téléphone"));

  const label = element("label", "flex flex-col gap-1 text-sm font-medium");
  label.htmlFor = "phone";
  label.append(document.createTextNode("Numéro au format international"));
  const input = element(
    "input",
    "rounded-lg border-2 border-black/20 px-3 py-3 text-base",
  );
  input.id = "phone";
  input.name = "phone";
  input.type = "tel";
  input.autocomplete = "tel";
  input.inputMode = "tel";
  input.placeholder = "+221771234567";
  input.required = true;
  label.append(input);
  form.append(label);

  const consentRow = element("div", "flex items-start gap-3");
  const consent = element("input", "mt-1 size-5 shrink-0");
  consent.id = "consent";
  consent.type = "checkbox";
  consent.required = true;
  const consentLabel = element(
    "label",
    "text-sm",
    "J’accepte les conditions d’utilisation et la politique de confidentialité.",
  );
  consentLabel.htmlFor = "consent";
  consentRow.append(consent, consentLabel);
  form.append(consentRow);

  const error = element("p", "text-sm font-medium text-red-700");
  error.setAttribute("role", "alert");
  form.append(error);

  const submit = primaryButton("Recevoir un code");
  submit.type = "submit";
  form.append(submit);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    error.textContent = "";
    const phone = input.value.trim().replace(/\s/g, "");
    if (!/^\+[1-9]\d{7,14}$/.test(phone)) {
      error.textContent = "Entrez un numéro au format international, par exemple +221771234567.";
      return;
    }
    if (!consent.checked) {
      error.textContent = "Vous devez accepter les conditions pour continuer.";
      return;
    }

    submit.disabled = true;
    submit.textContent = "Envoi…";
    session.client
      .requestOtp(phone)
      .then(() => renderCodeEntry({ ...session, phone }))
      .catch((cause) => {
        submit.disabled = false;
        submit.textContent = "Recevoir un code";
        error.textContent =
          cause instanceof ApiError && cause.code === "otp_rate_limited"
            ? "Trop de demandes. Patientez quelques minutes."
            : "Envoi impossible. Réessayez dans un instant.";
      });
  });

  session.target.replaceChildren(form);
  input.focus();
}

function renderCodeEntry(session: Session): void {
  const form = element("form", "flex flex-col gap-4");
  form.append(element("h2", "text-lg font-bold", "Code reçu par SMS"));
  form.append(
    element(
      "p",
      "text-sm text-[var(--color-muted)]",
      `Un code à six chiffres a été envoyé au ${session.phone}.`,
    ),
  );

  const label = element("label", "sr-only", "Code à six chiffres");
  label.htmlFor = "code";
  const input = element(
    "input",
    "rounded-lg border-2 border-black/20 px-3 py-3 text-center text-2xl tracking-[0.4em]",
  );
  input.id = "code";
  input.name = "code";
  input.type = "text";
  input.inputMode = "numeric";
  input.autocomplete = "one-time-code";
  input.maxLength = 6;
  input.required = true;
  form.append(label, input);

  const error = element("p", "text-sm font-medium text-red-700");
  error.setAttribute("role", "alert");
  form.append(error);

  const submit = primaryButton("Valider");
  submit.type = "submit";
  form.append(submit);

  const back = element("button", "text-sm underline", "Modifier le numéro");
  back.type = "button";
  back.addEventListener("click", () => renderIdentification(session));
  form.append(back);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    error.textContent = "";
    submit.disabled = true;
    submit.textContent = "Vérification…";

    session.client
      .terms()
      .then((terms) =>
        session.client.verifyOtp(
          session.phone,
          input.value.trim(),
          terms.terms.map((document) => document.id),
        ),
      )
      .then((tokens) => {
        session.client.setAccessToken(tokens.access);
        return session.client.claimFreeAccess(session.nasId);
      })
      .then((entitlement) => renderGranted(session, entitlement.ends_at))
      .catch((cause) => {
        submit.disabled = false;
        submit.textContent = "Valider";
        if (cause instanceof ApiError && cause.code && REFUSAL_MESSAGES[cause.code]) {
          error.textContent = REFUSAL_MESSAGES[cause.code];
          return;
        }
        error.textContent =
          cause instanceof ApiError && cause.code === "invalid_code"
            ? "Code incorrect. Vérifiez et réessayez."
            : "Vérification impossible. Réessayez dans un instant.";
      });
  });

  session.target.replaceChildren(form);
  input.focus();
}

function renderGranted(session: Session, endsAt: string | null): void {
  const fragment = document.createDocumentFragment();
  fragment.append(
    notice(
      "success",
      "Vous êtes connecté",
      endsAt
        ? `Votre accès est actif jusqu’à ${new Date(endsAt).toLocaleTimeString("fr-FR", {
            hour: "2-digit",
            minute: "2-digit",
          })}.`
        : "Votre accès est actif.",
    ),
  );

  if (session.context.redirect_url) {
    const link = element(
      "a",
      "block w-full rounded-lg bg-[var(--color-brand)] px-4 py-3 text-center text-base font-bold text-white",
      "Continuer",
    );
    link.href = session.context.redirect_url;
    fragment.append(link);
  }

  session.target.replaceChildren(fragment);
}

export async function mountPortal(target: HTMLElement, apiBaseUrl: string): Promise<void> {
  const nasId = new URLSearchParams(window.location.search).get("nas_id");

  if (!nasId) {
    target.replaceChildren(
      notice(
        "info",
        "Identifiant de borne absent",
        "Cette page s’ouvre normalement automatiquement à la connexion au réseau. " +
          "En développement, ajoutez ?nas_id=demo-nas-001 à l’adresse.",
      ),
    );
    return;
  }

  const client = createApiClient({ baseUrl: apiBaseUrl });
  try {
    const context = await client.portalContext(nasId);
    renderOffers({ target, client, nasId, context, phone: "" });
  } catch (error) {
    const message =
      error instanceof ApiError && error.code === "unknown_hotspot"
        ? "Ce point d’accès n’est pas reconnu. Signalez-le à un agent de la Ville."
        : "Service momentanément indisponible. Réessayez dans un instant.";
    target.replaceChildren(notice("error", "Connexion impossible", message));
  }
}
