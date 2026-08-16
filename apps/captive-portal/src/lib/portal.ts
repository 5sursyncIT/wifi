/**
 * Client logic of the captive portal.
 *
 * The zone is whatever the API resolves from the gateway's network identifier.
 * This code never decides which offers to show, and never trusts a zone, a price
 * or an offer coming from the URL (§8.2).
 */
import { ApiError, createApiClient, type PlanOffer, type PortalContext } from "@dakar-wifi/api-client";

import { formatDuration, formatPrice, formatVolume } from "./format";

const FALLBACK_MESSAGES: Record<string, string> = {
  zone_inactive: "Ce point d’accès est momentanément fermé. Réessayez plus tard.",
  no_offer_available: "Aucune offre n’est disponible ici pour l’instant.",
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

function notice(tone: "info" | "error", title: string, message: string): HTMLElement {
  const palette =
    tone === "error"
      ? "border-red-600 bg-red-50 text-red-900"
      : "border-amber-500 bg-amber-50 text-amber-900";
  const section = element("section", `rounded-lg border-2 p-4 ${palette}`);
  section.setAttribute("role", "status");
  section.append(element("h2", "font-bold", title), element("p", "mt-1 text-sm", message));
  return section;
}

function offerCard(offer: PlanOffer): HTMLElement {
  const card = element("li", "rounded-lg border border-black/15 p-4");

  const header = element("div", "flex items-baseline justify-between gap-3");
  header.append(
    element("h3", "text-lg font-bold", offer.name),
    element("p", "shrink-0 text-lg font-bold text-[var(--color-brand)]", formatPrice(offer.price_xof)),
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

  const action = element("button", "mt-4 w-full rounded-lg bg-[var(--color-brand)] px-4 py-3 text-base font-bold text-white disabled:opacity-50", "Choisir");
  action.type = "button";
  action.disabled = true;
  card.append(action);
  card.append(
    element("p", "mt-2 text-center text-xs text-[var(--color-muted)]", "Paiement disponible en phase 4"),
  );

  return card;
}

function renderContext(target: HTMLElement, context: PortalContext): void {
  const fragment = document.createDocumentFragment();

  const heading = element("section", "");
  heading.append(element("h2", "text-lg font-bold", context.zone.label));
  heading.append(
    element("p", "text-sm text-[var(--color-muted)]", `${context.site.name} — ${context.site.organization}`),
  );
  if (context.zone.welcome_message) {
    fragment.append(heading, element("p", "text-base", context.zone.welcome_message));
  } else {
    fragment.append(heading);
  }

  if (context.fallback.active) {
    fragment.append(
      notice(
        "info",
        "Point d’accès en cours de configuration",
        FALLBACK_MESSAGES[context.fallback.reason] ?? "Ce point d’accès n’est pas prêt.",
      ),
    );
    target.replaceChildren(fragment);
    return;
  }

  const list = element("ul", "flex flex-col gap-3");
  for (const offer of context.plans) {
    list.append(offerCard(offer));
  }
  fragment.append(list);
  target.replaceChildren(fragment);
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

  try {
    const context = await createApiClient({ baseUrl: apiBaseUrl }).portalContext(nasId);
    renderContext(target, context);
  } catch (error) {
    const message =
      error instanceof ApiError && error.code === "unknown_hotspot"
        ? "Ce point d’accès n’est pas reconnu. Signalez-le à un agent de la Ville."
        : "Service momentanément indisponible. Réessayez dans un instant.";
    target.replaceChildren(notice("error", "Connexion impossible", message));
  }
}
