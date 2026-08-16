/**
 * Typed client for the Dakar WiFi business API.
 *
 * Types come from `src/schema.d.ts`, generated from `docs/api/openapi.yaml`.
 * Never edit the generated file by hand: run `pnpm api-client:generate`.
 */
import type { paths } from "./schema";

export type HealthResponse =
  paths["/api/v1/health"]["get"]["responses"]["200"]["content"]["application/json"];

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
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
  const request = async <T>(path: string, init?: RequestInit): Promise<T> => {
    const response = await fetchImpl(`${baseUrl}${path}`, {
      credentials: "include",
      headers: { Accept: "application/json" },
      ...init,
    });

    // The health probe answers 503 with a full body: read it before deciding.
    const body = (await response.json().catch(() => null)) as T | null;

    if (body === null) {
      throw new ApiError(`Invalid response from ${path}`, response.status);
    }
    return body;
  };

  return {
    /** Service health. Answers 200 when healthy, 503 when a dependency is down. */
    health: () => request<HealthResponse>("/api/v1/health"),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
