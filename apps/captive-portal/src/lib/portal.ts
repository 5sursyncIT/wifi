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
  type TicketCategory,
} from "@dakar-wifi/api-client";

import { formatDuration, formatPrice, formatVolume } from "./format";
import { localeFromWindow, translate, type Locale, type MessageKey } from "./i18n";
import { toE164 } from "./phone";

const REFUSAL_KEYS = [
  "cooldown",
  "outside_hours",
  "not_offered_here",
  "no_free_offer",
  "activation_failed",
  "too_many_devices",
  "account_unusable",
  "voucher_not_found",
  "voucher_expired",
  "voucher_revoked",
  "voucher_exhausted",
  "voucher_already_used",
  "voucher_zone_mismatch",
  "voucher_campaign_inactive",
  "rate_limited",
] as const satisfies readonly MessageKey[];

const TICKET_CATEGORIES: [TicketCategory, MessageKey][] = [
  ["connexion", "ticket_connexion"],
  ["otp", "ticket_otp"],
  ["paiement", "ticket_paiement"],
  ["quota", "ticket_quota"],
  ["qualite", "ticket_qualite"],
  ["autre", "ticket_autre"],
];

function locale(): Locale {
  return localeFromWindow(window);
}

function t(key: MessageKey, vars?: Record<string, string | number>): string {
  return translate(locale(), key, vars);
}

function refusalMessage(code: string | undefined): string | undefined {
  if (!code) return undefined;
  if ((REFUSAL_KEYS as readonly string[]).includes(code)) {
    return t(code as MessageKey);
  }
  return undefined;
}

const ACCESS_TOKEN_KEY = "dakar-wifi:access-token";

export function createPortalClient(apiBaseUrl: string): ApiClient {
  const client = createApiClient({ baseUrl: apiBaseUrl });
  client.setAccessToken(sessionStorage.getItem(ACCESS_TOKEN_KEY));
  return client;
}

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
    error: "panel-error",
    success: "panel-ok",
    info: "panel-info",
  }[tone];
  const section = element("section", `rounded-xl p-4 ${palette}`);
  section.setAttribute("role", "status");
  section.append(element("h2", "font-bold", title), element("p", "mt-1 text-sm", message));
  return section;
}

function primaryButton(label: string): HTMLButtonElement {
  // Large tap target and strong contrast: this is used outdoors, one-handed (§12.1).
  const button = element(
    "button",
    "w-full rounded-xl bg-brand px-4 py-3.5 text-base font-bold text-white shadow-[0_4px_12px_rgba(0,64,144,0.22)] disabled:opacity-50",
    label,
  );
  button.type = "button";
  return button;
}

function purchaseUrl(nasId: string, offer: PlanOffer): string {
  return `/achat?${new URLSearchParams({
    nas_id: nasId,
    offre: offer.plan_version_id,
  }).toString()}`;
}

function offerCard(
  offer: PlanOffer,
  nasId: string,
  onChoose: (offer: PlanOffer) => void,
): HTMLElement {
  const card = element(
    "li",
    "rounded-xl border border-black/8 bg-white p-4 shadow-[0_4px_16px_rgba(0,45,102,0.08)]",
  );

  const header = element("div", "flex items-baseline justify-between gap-3");
  header.append(
    element("h3", "text-lg font-bold", offer.name),
    element(
      "p",
      "shrink-0 text-lg font-bold text-brand",
      formatPrice(offer.price_xof, locale()),
    ),
  );
  card.append(header);

  if (offer.description) {
    card.append(element("p", "mt-1 text-sm text-muted", offer.description));
  }

  // Price, duration, volume and speed must all be visible before validating (§12.1).
  const facts = [
    formatDuration(offer.connection_seconds, locale()),
    formatVolume(offer.quota_total_bytes, locale()),
    offer.bandwidth_down_kbps ? `${Math.round(offer.bandwidth_down_kbps / 1024)} Mb/s` : null,
    offer.max_simultaneous_sessions > 1
      ? t("devices", { count: offer.max_simultaneous_sessions })
      : null,
  ].filter((fact): fact is string => fact !== null);

  if (facts.length > 0) {
    const list = element("ul", "mt-3 flex flex-wrap gap-2");
    for (const fact of facts) {
      list.append(element("li", "rounded bg-black/5 px-2 py-1 text-sm", fact));
    }
    card.append(list);
  }

  const action = primaryButton(
    offer.type === "free" ? t("connect_free") : t("buy_offer", { name: offer.name }),
  );
  action.classList.add("mt-4");
  if (offer.type === "free") {
    action.addEventListener("click", () => onChoose(offer));
  } else {
    action.addEventListener("click", () => {
      if (sessionStorage.getItem(ACCESS_TOKEN_KEY)) {
        window.location.assign(purchaseUrl(nasId, offer));
        return;
      }
      onChoose(offer);
    });
  }
  card.append(action);
  return card;
}

function voucherForm(session: Session): HTMLElement {
  const form = element("form", "mt-2 flex flex-col gap-3 rounded-xl border border-black/8 bg-white p-4");
  form.append(element("h2", "text-base font-bold", t("voucher_title")));
  const input = element(
    "input",
    "rounded-xl border-2 border-black/15 bg-white px-3 py-3 text-base tracking-widest",
  );
  input.id = "voucher";
  input.name = "voucher";
  input.autocomplete = "off";
  input.placeholder = "XXXX-XXXX-XXXX";
  input.required = true;
  const error = element("p", "text-sm font-medium text-red-700");
  error.setAttribute("role", "alert");
  const submit = primaryButton(t("voucher_use"));
  submit.type = "submit";
  form.append(input, error, submit);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    error.textContent = "";
    const code = input.value.trim();
    if (!code) {
      return;
    }
    if (sessionStorage.getItem(ACCESS_TOKEN_KEY)) {
      submit.disabled = true;
      session.client
        .redeemVoucher(session.nasId, code, crypto.randomUUID())
        .then((entitlement) => renderGranted(session, entitlement.ends_at))
        .catch((cause) => {
          submit.disabled = false;
          error.textContent =
            refusalMessage(cause instanceof ApiError ? cause.code : undefined) ??
            t("voucher_rejected");
        });
      return;
    }
    session.pendingVoucher = code;
    const fallbackOffer = session.context.plans[0];
    if (!fallbackOffer) {
      error.textContent = t("identify_first");
      return;
    }
    renderIdentification(session, fallbackOffer);
  });
  return form;
}

function helpForm(session: Session): HTMLElement {
  const form = element("form", "mt-4 flex flex-col gap-3 rounded-xl border border-black/8 bg-white p-4");
  form.append(element("h2", "text-base font-bold", t("help_title")));
  const select = document.createElement("select");
  select.className = "rounded-xl border-2 border-black/15 bg-white px-3 py-3 text-base";
  select.name = "category";
  select.required = true;
  for (const [value, label] of TICKET_CATEGORIES) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = t(label);
    select.append(option);
  }
  const textarea = document.createElement("textarea");
  textarea.className = "rounded-xl border-2 border-black/15 bg-white px-3 py-3 text-base";
  textarea.name = "message";
  textarea.required = true;
  textarea.minLength = 10;
  textarea.rows = 3;
  textarea.placeholder = t("help_placeholder");
  const error = element("p", "text-sm font-medium text-red-700");
  error.setAttribute("role", "alert");
  const success = element("p", "text-sm font-medium text-green-800");
  const submit = primaryButton(t("help_send"));
  submit.type = "submit";
  form.append(select, textarea, error, success, submit);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    error.textContent = "";
    success.textContent = "";
    submit.disabled = true;
    session.client
      .createTicket(session.nasId, select.value as TicketCategory, textarea.value.trim())
      .then((ticket) => {
        success.textContent = t("help_opened", { number: ticket.ticket_number });
        textarea.value = "";
      })
      .catch((cause) => {
        error.textContent =
          cause instanceof ApiError && cause.code === "rate_limited"
            ? t("help_rate_limited")
            : t("help_failed");
      })
      .finally(() => {
        submit.disabled = false;
      });
  });
  return form;
}

interface Session {
  target: HTMLElement;
  client: ApiClient;
  nasId: string;
  context: PortalContext;
  phone: string;
  pendingVoucher?: string;
}

function renderOffers(session: Session): void {
  const fragment = document.createDocumentFragment();
  const { context } = session;

  const heading = element("section", "");
  heading.append(element("h2", "text-lg font-bold", context.zone.label));
  heading.append(
    element(
      "p",
      "text-sm text-muted",
      `${context.site.name} — ${context.site.organization}`,
    ),
  );
  fragment.append(heading);

  if (context.mocks.network || context.mocks.payment) {
    fragment.append(notice("info", t("demo_title"), t("demo_body")));
  }

  if (context.zone.welcome_message) {
    fragment.append(element("p", "text-base", context.zone.welcome_message));
  }

  if (context.fallback.active) {
    fragment.append(
      notice(
        "info",
        t("fallback_title"),
        t(
          context.fallback.reason === "zone_inactive" ||
            context.fallback.reason === "no_offer_available"
            ? context.fallback.reason
            : "fallback_generic",
        ),
      ),
    );
    session.target.replaceChildren(fragment);
    return;
  }

  const list = element("ul", "flex flex-col gap-3");
  for (const offer of context.plans) {
    list.append(
      offerCard(offer, session.nasId, (selected) => renderIdentification(session, selected)),
    );
  }
  fragment.append(list);
  fragment.append(voucherForm(session));
  fragment.append(helpForm(session));
  session.target.replaceChildren(fragment);
}

function renderIdentification(session: Session, offer: PlanOffer): void {
  const form = element("form", "flex flex-col gap-4");
  form.append(element("h2", "text-lg font-bold", t("phone_title")));

  const label = element("label", "flex flex-col gap-1 text-sm font-medium");
  label.htmlFor = "phone";
  label.append(document.createTextNode(t("phone_label")));
  const input = element("input", "rounded-xl border-2 border-black/15 bg-white px-3 py-3 text-base");
  input.id = "phone";
  input.name = "phone";
  input.type = "tel";
  input.autocomplete = "tel";
  input.inputMode = "tel";
  input.placeholder = "77 123 45 67";
  input.required = true;
  label.append(input);
  form.append(label);

  const consentRow = element("div", "flex items-start gap-3");
  const consent = element("input", "mt-1 size-5 shrink-0");
  consent.id = "consent";
  consent.type = "checkbox";
  consent.required = true;
  const consentLabel = element("label", "text-sm", t("consent"));
  consentLabel.htmlFor = "consent";
  consentRow.append(consent, consentLabel);
  form.append(consentRow);

  const error = element("p", "text-sm font-medium text-red-700");
  error.setAttribute("role", "alert");
  form.append(error);

  const submit = primaryButton(t("receive_code"));
  submit.type = "submit";
  form.append(submit);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    error.textContent = "";
    const phone = toE164(input.value);
    if (!phone) {
      error.textContent = t("phone_invalid");
      return;
    }
    if (!consent.checked) {
      error.textContent = t("consent_required");
      return;
    }

    submit.disabled = true;
    submit.textContent = t("sending");
    session.client
      .requestOtp(phone)
      .then(() => renderCodeEntry({ ...session, phone }, offer))
      .catch((cause) => {
        submit.disabled = false;
        submit.textContent = t("receive_code");
        error.textContent =
          cause instanceof ApiError && cause.code === "otp_rate_limited"
            ? t("otp_rate_limited")
            : t("send_failed");
      });
  });

  session.target.replaceChildren(form);
  input.focus();
}

function renderCodeEntry(session: Session, offer: PlanOffer): void {
  const form = element("form", "flex flex-col gap-4");
  form.append(element("h2", "text-lg font-bold", t("code_title")));
  form.append(
    element("p", "text-sm text-muted", t("code_sent", { phone: session.phone })),
  );

  const label = element("label", "sr-only", t("code_label"));
  label.htmlFor = "code";
  const input = element(
    "input",
    "rounded-xl border-2 border-black/15 bg-white px-3 py-3 text-center text-2xl tracking-[0.4em]",
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

  const submit = primaryButton(t("validate"));
  submit.type = "submit";
  form.append(submit);

  const back = element("button", "text-sm underline", t("change_number"));
  back.type = "button";
  back.addEventListener("click", () => renderIdentification(session, offer));
  form.append(back);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    error.textContent = "";
    submit.disabled = true;
    submit.textContent = t("verifying");

    session.client
      .terms()
      .then((terms) =>
        session.client.verifyOtp(
          session.phone,
          input.value.trim(),
          terms.terms.map((document) => document.id),
        ),
      )
      .then(async (tokens) => {
        sessionStorage.setItem(ACCESS_TOKEN_KEY, tokens.access);
        session.client.setAccessToken(tokens.access);
        if (session.pendingVoucher) {
          const code = session.pendingVoucher;
          session.pendingVoucher = undefined;
          const entitlement = await session.client.redeemVoucher(
            session.nasId,
            code,
            crypto.randomUUID(),
          );
          renderGranted(session, entitlement.ends_at);
          return;
        }
        if (offer.type !== "free") {
          window.location.assign(purchaseUrl(session.nasId, offer));
          return;
        }
        const entitlement = await session.client.claimFreeAccess(session.nasId);
        renderGranted(session, entitlement.ends_at);
      })
      .catch((cause) => {
        submit.disabled = false;
        submit.textContent = t("validate");
        const refused = refusalMessage(cause instanceof ApiError ? cause.code : undefined);
        if (refused) {
          error.textContent = refused;
          return;
        }
        error.textContent =
          cause instanceof ApiError && cause.code === "invalid_code"
            ? t("invalid_code")
            : t("verify_failed");
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
      t("connected"),
      endsAt
        ? t("access_until", {
            time: new Date(endsAt).toLocaleTimeString(locale() === "en" ? "en-GB" : "fr-FR", {
              hour: "2-digit",
              minute: "2-digit",
            }),
          })
        : t("access_active"),
    ),
  );

  if (session.context.redirect_url) {
    const link = element(
      "a",
      "block w-full rounded-xl bg-brand px-4 py-3.5 text-center text-base font-bold text-white shadow-[0_4px_12px_rgba(0,64,144,0.22)]",
      t("continue"),
    );
    link.href = session.context.redirect_url;
    fragment.append(link);
  }

  if (sessionStorage.getItem(ACCESS_TOKEN_KEY)) {
    fragment.append(accountActions(session));
  }
  fragment.append(helpForm(session));
  session.target.replaceChildren(fragment);
}

function accountActions(session: Session): HTMLElement {
  const box = element("div", "mt-4 flex flex-col gap-2");
  const status = element("p", "text-sm font-medium");
  status.setAttribute("role", "status");

  const disconnect = element("button", "text-sm underline text-left", t("disconnect_network"));
  disconnect.type = "button";
  disconnect.addEventListener("click", () => {
    disconnect.disabled = true;
    session.client
      .mySessions()
      .then((body) => {
        const open = body.sessions.filter((item) => item.ended_at === null);
        return Promise.all(open.map((item) => session.client.disconnectSession(item.id)));
      })
      .then(() => {
        status.className = "text-sm font-medium text-green-800";
        status.textContent = t("session_closed");
      })
      .catch(() => {
        disconnect.disabled = false;
        status.className = "text-sm font-medium text-red-700";
        status.textContent = t("disconnect_failed");
      });
  });

  const download = element("button", "text-sm underline text-left", t("download_data"));
  download.type = "button";
  download.addEventListener("click", () => {
    session.client
      .exportAccount()
      .then((payload) => {
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "dakar-wifi-export.json";
        link.click();
        URL.revokeObjectURL(url);
      })
      .catch(() => {
        status.className = "text-sm font-medium text-red-700";
        status.textContent = t("export_failed");
      });
  });

  const remove = element("button", "text-sm underline text-left text-red-800", t("delete_account"));
  remove.type = "button";
  let armed = false;
  remove.addEventListener("click", () => {
    if (!armed) {
      armed = true;
      remove.textContent = t("confirm_delete");
      return;
    }
    remove.disabled = true;
    session.client
      .deleteAccount()
      .then(() => {
        sessionStorage.removeItem(ACCESS_TOKEN_KEY);
        session.client.setAccessToken(null);
        status.className = "text-sm font-medium text-green-800";
        status.textContent = t("account_deleted");
        disconnect.remove();
        download.remove();
        remove.remove();
      })
      .catch(() => {
        remove.disabled = false;
        status.className = "text-sm font-medium text-red-700";
        status.textContent = t("delete_failed");
      });
  });

  box.append(disconnect, download, remove, status);
  return box;
}

export async function mountPortal(target: HTMLElement, apiBaseUrl: string): Promise<void> {
  const nasId = new URLSearchParams(window.location.search).get("nas_id");

  if (!nasId) {
    target.replaceChildren(notice("info", t("missing_nas_title"), t("missing_nas_body")));
    return;
  }

  const client = createPortalClient(apiBaseUrl);
  try {
    const context = await client.portalContext(nasId, undefined, locale());
    renderOffers({ target, client, nasId, context, phone: "" });
  } catch (error) {
    const message =
      error instanceof ApiError && error.code === "unknown_hotspot"
        ? t("unknown_hotspot")
        : t("service_unavailable");
    target.replaceChildren(notice("error", t("connection_impossible"), message));
  }
}
