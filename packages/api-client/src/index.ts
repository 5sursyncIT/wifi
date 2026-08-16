/**
 * Typed client for the Dakar WiFi business API.
 *
 * Types come from `src/schema.d.ts`, generated from `docs/api/openapi.yaml`.
 * Never edit the generated file by hand: run `pnpm api-client:generate`.
 */
import type { paths } from "./schema";

type Json<T> = T extends { content: { "application/json": infer B } } ? B : never;

export type HealthResponse = Json<paths["/api/v1/health"]["get"]["responses"]["200"]>;
export type PortalContext = Json<paths["/api/v1/portal/context"]["get"]["responses"]["200"]>;
export type PortalPlans = Json<paths["/api/v1/portal/plans"]["get"]["responses"]["200"]>;
export type PublicSites = Json<paths["/api/v1/public/hotspots"]["get"]["responses"]["200"]>;
export type ApiErrorBody = Json<paths["/api/v1/portal/context"]["get"]["responses"]["404"]>;
export type TokenPair = Json<paths["/api/v1/auth/otp/verify"]["post"]["responses"]["200"]>;
export type Terms = Json<paths["/api/v1/portal/terms"]["get"]["responses"]["200"]>;
export type Entitlement = Json<paths["/api/v1/portal/free-access"]["post"]["responses"]["201"]>;
export type Entitlements = Json<paths["/api/v1/me/entitlements"]["get"]["responses"]["200"]>;

export type PlanOffer = PortalContext["plans"][number];
export type PublicSite = PublicSites["sites"][number];

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** Stable machine-readable code from the API (§10.4), when the body carried one. */
    readonly code?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export function createApiClient({ baseUrl, fetchImpl = fetch }: ApiClientOptions) {
  let accessToken: string | null = null;

  interface RequestOptions {
    query?: Record<string, string>;
    body?: unknown;
    method?: string;
  }

  const request = async <T>(path: string, options: RequestOptions = {}): Promise<T> => {
    const url = new URL(`${baseUrl}${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value) url.searchParams.set(key, value);
    }

    const headers: Record<string, string> = { Accept: "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    if (accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    const response = await fetchImpl(url, {
      credentials: "include",
      method: options.method ?? (options.body === undefined ? "GET" : "POST"),
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });

    // 202 and 204 carry no body by design; returning early keeps callers from
    // having to guard against a parse that was never going to succeed.
    if (response.status === 202 || response.status === 204) {
      if (!response.ok) throw new ApiError(`Request to ${path} failed`, response.status);
      return undefined as T;
    }

    // The health probe answers 503 with a full body, and portal errors carry a
    // machine-readable code: read the body before deciding.
    const body = (await response.json().catch(() => null)) as T | null;

    if (body === null) {
      throw new ApiError(`Invalid response from ${path}`, response.status);
    }
    if (!response.ok) {
      const error = body as ApiErrorBody;
      throw new ApiError(error?.message ?? `Request to ${path} failed`, response.status, error?.code);
    }
    return body;
  };

  return {
    /** Attach a citizen access token to every following call. */
    setAccessToken(token: string | null) {
      accessToken = token;
    },

    /** Service health. Answers 200 when healthy, 503 when a dependency is down. */
    health: () => request<HealthResponse>("/api/v1/health"),

    /**
     * Portal context for a hotspot. The zone is resolved server-side from
     * `nasId`; anything else the browser might claim is ignored (§8.2).
     */
    portalContext: (nasId: string, redirectUrl?: string) =>
      request<PortalContext>("/api/v1/portal/context", {
        query: { nas_id: nasId, redirect_url: redirectUrl ?? "" },
      }),

    portalPlans: (nasId: string) =>
      request<PortalPlans>("/api/v1/portal/plans", { query: { nas_id: nasId } }),

    /** Public map of access points. Carries no equipment identifier. */
    publicHotspots: () => request<PublicSites>("/api/v1/public/hotspots"),

    /** Documents the citizen must accept before an account is opened (§8.1). */
    terms: () => request<Terms>("/api/v1/portal/terms"),

    /** Ask for a code. Always answers the same way, known number or not. */
    requestOtp: (phone: string) =>
      request<void>("/api/v1/auth/otp/request", { body: { phone } }),

    /** Verify the code and open a session, recording the accepted terms. */
    verifyOtp: (phone: string, code: string, acceptedTerms: string[]) =>
      request<TokenPair>("/api/v1/auth/otp/verify", {
        body: { phone, code, accepted_terms: acceptedTerms },
      }),

    /** Claim the free allowance of the zone the hotspot resolves to (§8.4). */
    claimFreeAccess: (nasId: string) =>
      request<Entitlement>("/api/v1/portal/free-access", { body: { nas_id: nasId } }),

    myEntitlements: () => request<Entitlements>("/api/v1/me/entitlements"),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
