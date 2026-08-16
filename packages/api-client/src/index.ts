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
  const request = async <T>(path: string, query?: Record<string, string>): Promise<T> => {
    const url = new URL(`${baseUrl}${path}`);
    for (const [key, value] of Object.entries(query ?? {})) {
      if (value) url.searchParams.set(key, value);
    }

    const response = await fetchImpl(url, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });

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
    /** Service health. Answers 200 when healthy, 503 when a dependency is down. */
    health: () => request<HealthResponse>("/api/v1/health"),

    /**
     * Portal context for a hotspot. The zone is resolved server-side from
     * `nasId`; anything else the browser might claim is ignored (§8.2).
     */
    portalContext: (nasId: string, redirectUrl?: string) =>
      request<PortalContext>("/api/v1/portal/context", {
        nas_id: nasId,
        redirect_url: redirectUrl ?? "",
      }),

    portalPlans: (nasId: string) =>
      request<PortalPlans>("/api/v1/portal/plans", { nas_id: nasId }),

    /** Public map of access points. Carries no equipment identifier. */
    publicHotspots: () => request<PublicSites>("/api/v1/public/hotspots"),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
